# INDICATOR_SSOT.md — 指標算式 / 門檻 / 缺值行為 SSOT

> **產出日**：2026-09-15 ｜ **性質**：唯讀盤點 + 實測查證，**未修改任何 repo 檔案**
> **repo 座標**：`/home/user/my-stock-dashboard`，分支 `claude/stock-dashboard-handoff-g9dtm0`，
> HEAD `fab88a7`，`git status --porcelain` 空（開工與收工皆實測）
> **紀律**：`CLAUDE.md §1 Fail Loud`（查不到一律寫「查不到」，不以常識補標準式）；
> `§-2 規則 6`（全稱句一律自標「單組結論、未複驗」）
> **合規**：本文件**不產生任何買賣建議**。文中出現的「買進 / 減碼 / 加碼 / 停利」字樣
> **全部是現行 code 的原文引用**，一律以 `引用` 標明，屬稽核軌跡，非本文件的建議。

---

## 0. 這份文件怎麼讀

### 0.1 範圍與邊界

| 問題 | 誰回答 |
|---|---|
| 這個數字**從哪來**（endpoint / 單位 / 發布延遲 / fallback 鏈） | **`DATA_LINEAGE.md`**（另一組），本檔**不重寫** |
| 這個數字**怎麼算**、**門檻是多少**、**那個門檻住哪個檔** | **本檔** |
| 畫面上該講什麼話 | `S1-6_COMPLIANCE_COPY_GUIDE.md` |

本檔每個指標的「輸入」欄只寫**輸入項的名字 + 產生它的函式**，不寫來源 endpoint ——
要追來源請走 `DATA_LINEAGE.md`。

### 0.2 三個閱讀約定

1. **門檻常數欄一律寫 `檔案:符號名`，不寫行號。**
   理由：`CLAUDE.md §8.2.A.0 規則 1` —— 行號在任何一次重構後就失效，是「保證會過期的資訊」。
2. **🔴 標紅有兩種意思，不要混**：
   - 🔴 **`inline`** = 這個數字寫死在程式裡、沒走 SSOT 常數（違 `CLAUDE.md §3.3`）
   - 🔴 **`回 0`** = 缺值時回 0 / 給中性分 / 落進某個結論分支（違客戶紅線「缺失值不得填 0」）
3. **判定規則欄一律寫成可執行的 if-else 或評分表**，不寫「大致上如果…就…」。
   分支順序**即程式的實際順序**（順序會改變結果時已標明）。

### 0.3 缺值語彙（全站六態 + 財報三態）

**`shared/station_specs.py`（L0）** 定義六個缺值原因常數，附「該怎麼辦」文案：

| 常數 | 值 | 語意 | 使用者該做什麼（`station_specs:MISS_TEXT` 原文） |
|---|---|---|---|
| `MISS_FETCH_FAILED` | `"fetch_failed"` | 整檔抓取失敗 | 看該列錯誤訊息，多半是代號或來源問題 |
| `MISS_CONTRACT_DRIFT` | `"contract_drift"` | 有值但形態不對 | 重跑不會好，是程式要修的訊號 |
| `MISS_NOT_ENOUGH` | `"not_enough"` | 有資料但筆數不夠算 | 新上市／剛納入，**等時間累積**（重跑無用） |
| `MISS_NO_VARIATION` | `"no_variation"` | 整段零波動、分母為 0 | 停牌或極低流動性，等有價格變動 |
| `MISS_NO_INPUT` | `"no_input"` | 該項輸入沒抓到 | 上游這輪失敗，**可以重跑一次** |
| `MISS_NOT_APPLICABLE` | `"n/a"` | 這類持股不適用 | 不是壞掉 |

**優先序** `station_specs:MISS_PRIORITY`（同一盞燈多個原因時取排前者）：
`FETCH_FAILED > CONTRACT_DRIFT > NOT_ENOUGH > NO_VARIATION > NO_INPUT > NOT_APPLICABLE`，
仲裁函式 `station_specs:most_fundamental_miss`。

**財報三態** `src/services/financial_health_engine.py`：`FIELD_ABSENT` / `FIELD_ZERO` / `FIELD_VALUE`。
⚠️ 該檔自陳：**`FIELD_ABSENT` 在現行 fetcher 契約下對 production 資料永遠不會發生**
（`financial_statements_fetcher._v()` 查無回 `0.0`、不回 None）。
⇒ **production 真正會觸發的是領域規則**（`_stmt_gap` / `oi_state != FIELD_VALUE` / `gp <= 0`），
本檔各節的「缺值行為」一律記錄**領域規則**那一條。

**⚠️ `⚪` 這個符號在本站被超載成兩種語意，是本次盤點發現的系統性混淆**：
- 語意 A「**未評估 / 資料不足**」：`dividend_station:Flag.level` 的 `⚪`、`'⚪ 未評估'`、`'⚪無股利'`、`'⬜'`
- 語意 B「**中性、有判讀結論**」：`shared/thresholds:classify_yield_zone` 回的 `'⚪ 中性持有'`（殖利率 5~7%）

同一個畫面同時出現這兩種 ⚪ 時，使用者無法分辨「沒資料」與「判了、結論是中性」。
（單組結論，未複驗；本檔只記錄事實，不提修法。）

### 0.4 本次查證方法（照 `§-2 規則 6` 揭露）

1. **讀既有材料**：`S1-2_METRIC_SSOT.md`（78KB）、`S1-1_DATA_WHITEPAPER.md`、`S2-ENG_SPEC.md`
2. **回 code 複驗**：對每一條宣稱重讀原始檔，**不引用轉述**
3. **執行探針**：`scratchpad/_probe_ind.py` / `_probe_unit.py`（唯讀，只 import L2 純函式印回傳值，
   不寫 repo、不打網路）—— 本檔凡標「**實測**」者皆出自這兩支
4. **關鍵字掃描**：`便宜|合理|昂貴|超貴|偏貴|極貴` 全 `src/` + `shared/` + `app.py`，
   以及 `SATELLITE_TAKE_PROFIT_PCT` / `SCREENER_MIN_FACTOR_COVERAGE_RATIO` / `valuation_level` 等具名符號

⚠️ **本檔為單組產出，未經第二組獨立複驗**（`§-2 規則 6`）。
⚠️ **涵蓋率不是 100%** —— 詳見 §9「我沒查到的」。**不要把本檔讀成全站指標清單。**


### 0.5 目錄

| 節 | 內容 | 客戶點名的已知問題落在哪 |
|---|---|---|
| **§1** | 門檻常數住哪 —— SSOT 檔案地圖 | — |
| **§2** | 估值類（357 / ETF 7% / PE / 河流圖） | **#1**（§2.6 字面複本）、**#2**（§2.7 emoji vs 中文）、**#4**（§2.3 PE） |
| **§3** | 燈號類（五桶 / 總經 / 235 / 健檢 ABCD / 3-3-3 / 狀態燈 / 綜合建議） | **#7**（§3.6 減碼燈）、**#8**（§3.4 235 燈名） |
| **§4** | 評分類（個股健康 / 基本面四維 / 財報體檢 / 獲利 5 指標 / ETF 綜合分 / 選股網） | **#5**（§4.6 涵蓋門檻）、**#6**（§4.4 獲利 5 指標） |
| **§5** | 風險與部位（Sharpe / MDD / 停損 / 油門 / 集中度 / 折溢價 / 流動性） | **#3**（§5.7 停利門檻） |
| **§6** | 技術指標 kernel（RSI / ATR / KD / 布林 / 乖離 / IBS / 量比 / VCP / RS / 出場三維） | — |
| **§7** | **已知問題總表**（客戶 8 項逐項複驗 + 本次新增 14 項） | 全部 |
| **§8** | 合規掃描（現行 code 的行動語，稽核軌跡） | — |
| **§9** | **我沒查到的**（涵蓋率 / 單組結論 / 沒追完的 / 唯讀紀律） | — |

**⚠️ 三個最需要優先複驗的新發現**（`§-2 規則 4`：調查／稽核須多組視角，不可自己查自己）：
**N-1**（§4.2 `calc_fundamental_score` 量綱錯誤，估值分與真實殖利率顛倒）、
**N-2**（§4.1 `calc_health_score` 缺值回 0 → 🔴 弱勢危險）、
**N-3**（§5.1 `calc_sharpe` 回 0.0 繞過 ETF rescale → 少一顆星、翻掉「留下/觀察」）。

---

## 1. 門檻常數住哪 — SSOT 檔案地圖

| 檔案（皆 L0） | 收什麼 | 本檔引用到的代表符號 |
|---|---|---|
| `shared/thresholds.py` | 357 殖利率三段 | `YIELD_HIGH/MID/LOW` + `_DEC` 三個 |
| `shared/signal_thresholds.py` | 語意常數大宗（`CLAUDE.md §3.3` 記 76 個） | `TRADING_DAYS_PER_YEAR` / `RSI_STRONG_LOW` / `KD_*_LEVEL` / `ETF_RATING_*` / `SCREENER_MIN_FACTOR_COVERAGE_RATIO` … |
| `shared/financial_health_thresholds.py` | 財報體檢 19 個 `FH_*` | `FH_GROSS_MARGIN_GOOD_PCT` / `FH_MOS_STRONG_PCT` / `FH_NET_MARGIN_PASS_PCT` … |
| `shared/health_thresholds.py` | 個股健康評分 A/B 分界 | `HEALTH_GRADE_A_MIN=80` / `HEALTH_GRADE_B_MIN=50` |
| `shared/dividend_station_thresholds.py` | 存股戰情室（235 / 3-3-3 / 健檢 / 80-20） | `VIX_LIGHT1/2/3` / `Z_LIGHT1/2/3` / `SATELLITE_TAKE_PROFIT_PCT` … |
| `shared/macro_buckets.py` | 五桶 16 個 `DangerSpec` | `BUCKET_DANGER_SPECS` / `SPECS_BY_KEY` / `classify_danger` |
| `shared/etf_recommendation_thresholds.py` | ETF 留/觀察/換 | `KEEP_COMPOSITE_MIN` / `SELL_COMPOSITE_MAX` / `SIGMA_Z_*` |
| `shared/stock_buckets.py` | PB 河流圖產業分帶 | `PB_BANDS_FINANCIAL/GROWTH/MFG` / `get_pb_bands` / `classify_pb_level` |
| `shared/station_specs.py` | 缺值原因 + 235 判斷軸 | `MISS_*` / `LIGHT235_AXES` / `MISS_PRIORITY` |
| `src/config/config.py` | 全域舊常數 | `RSI_OVERBOUGHT=70` / `RSI_OVERSOLD=30` / `ANNUAL_MA=240` / `EXPOSURE_*` / `MAX_PORTFOLIO_DRAWDOWN` |
| `src/data/macro/macro_core.py`（**L1**） | `MACRO_THRESHOLDS` 10 項 | VIX / CPI / PMI / US10Y / DXY … |

**⚠️ `MACRO_THRESHOLDS` 的鏡像關係**：`macro_core.MACRO_THRESHOLDS` 在 **L1**，`shared/macro_buckets.py` 在 **L0**
（L0 不得 import L1，`CLAUDE.md §8.2` 硬規則 3）。
⇒ `macro_buckets` 內以 `_VIX_YELLOW = 22.0` 等**私有鏡像常數**重寫一份，
由 `tests/test_macro_buckets.py::test_mirror_matches_macro_core` 斷言兩份相等。
**這是刻意的第二份，不是漂移**；但它也代表「改 `MACRO_THRESHOLDS` 必須同步改鏡像，否則 CI 紅燈」。

**唯二有使用者／設定檔覆寫路徑的門檻**（實測 `macro_thresholds.json` 全檔只有這兩個 key）：
`HEALTH_DEFENSE_THRESHOLD`（=35）、`BULL_MIN_SCORE`（=4）。
該檔 `last_calibrated: null` / `method: "default (uncalibrated)"` —— **自陳未校準**。
**其餘所有門檻（含 `SATELLITE_TAKE_PROFIT_PCT`）皆無任何使用者設定路徑**（見 §5.7）。

---

## 2. 估值類指標

### 2.1 357 殖利率估值（個股）

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面「💰 B. 357殖利率評價」／程式 `classify_stock_357_price`（L0 判定）＋ `calc_357_valuation`（L2 文案） |
| **算式** | `est_yield_pct = avg_div_twd ÷ price × 100`<br>三檔**分界價**（**反推**；程式內欄名 `targets`，原碼稱「目標價」—— 引用）：<br>　`P_cheap = avg_div_twd ÷ YIELD_HIGH_DEC`（＝ ÷0.07）<br>　`P_fair　= avg_div_twd ÷ YIELD_MID_DEC`（＝ ÷0.05）<br>　`P_dear　= avg_div_twd ÷ YIELD_LOW_DEC`（＝ ÷0.03） |
| **輸入** | `price`（現價，元）← 日線 close；`avg_div_twd`（**近 5 個日曆年度每年現金股利加總後取算術平均**，元/股）← `src/data/stock/app_stock_fetchers.py` 的 `avg_div` |
| **單位** | `price` 元；`avg_div_twd` **元/股**；`est_yield` **%**；三檔分界價 **元** |
| **門檻常數** | `shared/thresholds.py:YIELD_HIGH=7.0` / `YIELD_MID=5.0` / `YIELD_LOW=3.0`（**%**）<br>`shared/thresholds.py:YIELD_HIGH_DEC/MID_DEC/LOW_DEC`（**小數**，由 `%` 版 `/100` 推導） |
| **判定規則** | `shared/thresholds.py:classify_stock_357_price(price, avg_div)`：<br>`if price is None or avg_div is None or price<=0 or avg_div<=0: → 'na', {}`<br>`elif price <= P_cheap: → 'cheap'`<br>`elif price <= P_fair:　→ 'fair'`<br>`elif price <= P_dear:　→ 'dear'`<br>`else: → 'overpriced'` |
| **缺值行為** | ✅ **正確**。`'na'` → `v5_modules.calc_357_valuation` 回 `{"est_yield": None, "signal": "⚪ 未評估", "msg": "…（不以 0% 代替，避免誤判為超貴）"}`。**明文拒絕用 0% 頂替**（該檔 docstring 原文：`§1：不可回 0 —— 0% 會被判成「超貴」，那是拿缺資料當看空結論`） |
| **合理範圍** | `est_yield` 理論 (0, ∞)；`CLAUDE.md §3.2` 未收此項。**無上界 sanity 檢查** —— 若 `avg_div` 單位錯亂會直接算出荒謬殖利率（歷史案例：`section_health_score.py` 檔內註記 2330 曾實機顯示 0.01%、真值 0.59%，因除以股價兩次；v19.179 B1-b 已修 `calc_dividend_yield_357`） |
| **已知問題** | ① 字面複本 15 份（§2.6）；② `_DEC` 量綱雙胞胎（下段）；③ **不是母法定義的「近一年累計已除息總額」**，分子是 5 年平均（`S1-2 §1.4` 已記，本次複驗仍然如此） |

**`YIELD_HIGH` 量綱雙胞胎（實測複驗）**
```python
YIELD_HIGH: float = 7.0           # 百分比版 — 用於「比較」
YIELD_HIGH_DEC: float = YIELD_HIGH / 100   # 0.07 — 只當「分母反推目標價」   ← 註解為原碼引用
```
✅ `_DEC` 版**由百分比版推導**，不是第二份獨立寫死的數字 → **不會漂移**。
⚠️ 殘留風險是**命名**不是值：兩個常數名只差 `_DEC` 四字元，且函式簽章不編碼單位
（`CLAUDE.md §4.1` 的 `rate_pct` / `rate_ratio` 命名規範**沒有套用在這裡**）。

**📌 `classify_yield_zone` 的燈色順序（本次更正 `S1-2 §1.5` 的一處誤判）**

實測 `shared/thresholds.py:classify_yield_zone`：

| `cur_yield` | 回傳 |
|---|---|
| 8.0 / 7.0 | `('🟢 強烈買進', 'strong_buy')` |
| 6.0 | `('⚪ 中性持有', 'neutral')` |
| 5.0 / 4.0 | `('🟡 適度減碼', 'reduce')` |
| 3.0 / 2.0 / 0.0 | `('🔴 獲利了結', 'sell')` |
| `None` | `('—', 'na')` |

`S1-2 §1.5` 寫「**燈色嚴重度順序與數值順序相反**」。
**本次複驗：該判定不成立。** 殖利率越低＝越貴＝越差，燈色 🟢→⚪→🟡→🔴 **是單調正確的**。
⚠️ **但另一個問題是真的**：中間段用 `⚪`，而 `⚪` 在本站別處代表「資料不足」（§0.3）—— 那是**符號超載**，不是順序錯。

---

### 2.2 ETF 7% 估值（`valuation_zone`）

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面欄「7%估值」（`shared/etf_ui_labels.py:'valuation_zone'→'7%估值'`）／程式 `etf_helpers.yield_valuation_zone` |
| **算式** | 不自算，**delegate 給** `shared/thresholds:classify_yield_zone(cur_yield, avg_yield)`；額外前置條件：ETF 場景必須有 5 年平均殖利率才給結論 |
| **輸入** | `cur_yield` ← `etf_calc.calc_current_yield(df, divs)`；`avg_yield` ← `etf_calc.calc_avg_yield(df, divs, years=5, require_full_years=True)` |
| **單位** | 兩者皆 **%** |
| **門檻常數** | 同 §2.1（`shared/thresholds.py:YIELD_HIGH/MID/LOW`） |
| **判定規則** | `if avg_yield is None: → '—'`<br>`elif avg_yield <= 0: → '—'`（由 `classify_yield_zone` 內層擋）<br>`else: → classify_yield_zone(cur_yield, avg_yield)` 的 label |
| **缺值行為** | ✅ 回 `'—'`，不落結論。`build_etf_score_row` 的 row 預設值即 `'valuation_zone': '—'` |
| **合理範圍** | 未設 sanity 上下界 |
| **已知問題** | 下游 `etf_recommendation` 用 **emoji** 讀這一欄 → §2.7（已知問題 #2） |

---

### 2.3 本益比 PE（已知問題 #4）

| 欄 | 內容 |
|---|---|
| **指標名** | 選股網「估值分」（`pe_low` 因子）／`src/data/stock/yield_pe_fetcher.py:fetch_pe_name_maps` |
| **算式** | ⚠️ **本站不自己算 PE。** `fetch_pe_name_maps` **直接取用交易所公告值**（上市 TWSE `PEratio`、上櫃 TPEX `PriceEarningRatio`），合併規則 `setdefault`（上市先填，`CLAUDE.md §2.1` 上層先填者贏、不平均）。<br>**沒有 EPS 這個輸入** ⇒ 無法區分「虧損」與「來源空值」 |
| **輸入** | TWSE / TPEX 公告 PE（來源細節見 `DATA_LINEAGE.md`） |
| **單位** | **倍** |
| **門檻常數** | 取數層**無門檻**；下游河流圖門檻見 §2.4 |
| **判定規則** | 取數層（`fetch_pe_name_maps` 迴圈內，**實際原碼**）：<br>`try: _pe = float(_v)`<br>`except (TypeError, ValueError): continue`<br>`if _pe != _pe or _pe <= 0: continue`　← **NaN 與 ≤0 走同一條路**<br>`else: pe_map.setdefault(_c, _pe)` |
| **缺值行為** | 「不放進 `pe_map`」。⚠️ **畫面上「來源沒給」與「PE ≤ 0（虧損）」長得一模一樣** —— 兩者都是「這檔沒有本益比」。**沒有 `N/A（虧損）` 這個標籤。**<br>✅ 兩個端點都失敗 → `pe_map = {}`，UI 顯示「本輪拿到的本益比對照表是空的」（誠實） |
| **合理範圍** | 實作只保證 `> 0`，**無上界**（`CLAUDE.md §3.2` 未收 PE） |
| **已知問題** | ① 上述 NaN/≤0 合流；② **缺 PE 會讓整檔出局**，見 §4.7；③ ✅ 有一個**正確**的防禦：該檔 docstring 明寫「pe_low 因子是『值越小分越高』，若讓 0／負數進榜，**虧損股會被排成全市場最便宜**」—— 這條擋住了 |

---

### 2.4 PE 河流圖 / PB 河流圖 / 殖利率河流圖

三張圖同在 `src/ui/tabs/stock_sections/section_357_valuation.py`，**門檻來源三種不同標準**：

| 圖 | 算式 | 門檻常數 | 缺值行為 |
|---|---|---|---|
| **殖利率河流** | `P_band = avg_div ÷ YIELD_*_DEC`（逐日序列） | ✅ `shared/thresholds.py:YIELD_HIGH/MID/LOW_DEC` | 無配息 → 不繪 |
| **PE 河流** | `P_band = TTM_EPS_series × PE_multiple`，其中 `TTM_EPS = rolling(4, min_periods=4).sum()` 於季 EPS 上；公告生效日＝**季末 + 60 天**（防 lookahead） | 🔴 **inline** —— `section_357_valuation.py:_PE_BANDS` 是**寫在 UI 檔內的 dict**：`{'通用 10/15/20': (10,15,20), '保守 8/12/16（景氣循環股）': (8,12,16), '成長 12/18/25': (12,18,25)}`。**沒有走任何 L0 SSOT** | 🔴 `_p_lo = float(...iloc[-1]) if not ....empty else 0` —— **序列全空時回 `0`**，不是 None |
| **PB 河流** | `P_band = BPS × PB_multiple` | ✅ `shared/stock_buckets.py:PB_BANDS_FINANCIAL=(0.5,0.9,1.2)` / `PB_BANDS_GROWTH=(1.5,2.5,4.0)` / `PB_BANDS_MFG=(0.8,1.5,2.5)`，由 `get_pb_bands(industry)` 依產業選帶 | `classify_pb_level` → `pb<=0` 回 `'—'` ✅ |

**⚠️ 三張圖的不一致（本次盤點新記錄，單組結論）**：
- **PB 有產業分帶（金融 / 成長 / 製造三組），PE 沒有** —— PE 用一個使用者下拉選單選 preset，預設「通用 10/15/20」。
  同一家金融股，PB 會自動用 `(0.5,0.9,1.2)`，PE 卻用製造業通用的 `(10,15,20)`。
- **PE 的三組 preset 是 UI 檔內的 inline dict**，PB 的三組住 L0 → 改 PE 帶要改 UI 檔（違 `CLAUDE.md §3.3`）。

**`classify_pb_level` 判定規則**（`shared/stock_buckets.py`）：
```
if pb_value is None or pb_value <= 0: → '—'
elif pb_value < low:  → '🟢 便宜'
elif pb_value < mid:  → '🟢 合理'
elif pb_value < high: → '🟡 偏貴'
else:                 → '🔴 超貴'
```
⚠️ **`'🟢 便宜'` 與 `'🟢 合理'` 同為綠燈** —— 四級標籤只有三種顏色。

---

### 2.5 河流圖「現價落在哪一區」（三份逐字複本）

`section_357_valuation.py` 內**三段結構完全相同、字面完全相同**的 zone 判定：

```
_cur_zone    = ('🟢 便宜區' if _cur_price_riv < _p7r else '🟡 合理區' if ... else '🔴 昂貴區' if ... else '⛔ 超昂貴')
_cur_zone_pe = ('🟢 便宜區' if _cur_price_pe  < _p_lo else ... '⛔ 超昂貴')
_cur_zone_pb = ('🟢 便宜區' if _cur_price_pb  < _b_lo_pb else ... '⛔ 超昂貴')
```
🔴 **三份 inline 複本**，無 SSOT 函式。⚠️ 注意這一家用的是 **`⛔ 超昂貴`**，
而同檔另一處用 `🔴超過昂貴`、組合頁用 `🔴超貴` —— **三個不同字面指同一件事**（§2.6）。

---

### 2.6 ⚠️ 已知問題 #1 — 估值字面複本表（**實測 15 個 family，比回報的 7 份更多**）

**掃描方法**：`grep -rnoE "'[^']*(便宜|合理|昂貴|超貴|偏貴|極貴)[^']*'"` 全 `src/` + `shared/` + `app.py`，
去重後歸併為「同一產生點的一組標籤」＝ 1 個 family。
⚠️ **單組窮舉、未複驗**（`§-2 規則 6`）；下表是**歸併後**的結果，不是原始命中數。

| # | 產生點（`檔案:符號`） | 層 | 標籤字面 | 被當控制流？ |
|---|---|---|---|---|
| F1 | `shared/thresholds.py:classify_yield_zone` | L0 | `🟢 強烈買進` / `⚪ 中性持有` / `🟡 適度減碼` / `🔴 獲利了結` / `—` | **是**（`etf_recommendation` 讀它的 **emoji**）→ §2.7 |
| F2 | `shared/thresholds.py:classify_stock_357_price` | L0 | **code**：`cheap`/`fair`/`dear`/`overpriced`/`na` | **是，且這是唯一正確的做法**（下游比對 code 不比對中文） |
| F3 | `shared/stock_buckets.py:classify_pb_level` | L0 | `🟢 便宜` / `🟢 合理` / `🟡 偏貴` / `🔴 超貴` / `—` | 未發現 |
| F4 | `src/compute/strategy/v5_modules.py:calc_357_valuation` `signal` | L2 | `🟢 甜甜價（7%+近5年年年配）` / `🟢 高殖利率（穩定性待確認）` / `🟡 合理（5~7%）` / `🔴 昂貴（3~5%）` / `🔴 超貴（<3%）` / `⚪ 未評估` | 未發現 |
| F5 | `src/compute/risk/risk_radar.py` 參數 `valuation_level` | L2 | `便宜` / `合理` / `偏貴` / `極貴`（裸字，無 emoji） | **是（`==` 全等比對）—— 但實測為死碼**，見下 |
| F6 | `src/compute/scoring/scoring_helpers.py:calc_fundamental_score` 估值 checks | L2 | `便宜區 >7%` / `合理 5~7%` / **`合理 3~5%`** / `偏貴 <3%` | 否（只顯示） |
| F7 | `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py` `val4` | L5 | `🟢便宜` / `🟡合理` / `🔴昂貴` / `🔴超貴` / `⚪無股利`（**emoji 後無空格**） | **是**（3 個消費端）→ 見下 |
| F8 | `section_357_valuation.py:_BOX_LABELS` | L5 | `🟢便宜價 — 積極買進` / `🟡合理價 — 可分批布局` / `🔴昂貴價 — 謹慎操作` / `🔴超過昂貴 — 避免追高` | 否 |
| F9 | `section_357_valuation.py:_TEACHER_LABELS` | L5 | 整句散文（`…積極買進區` / `…在合理區…` / `…在昂貴區…` / `…嚴禁追高`） | 否 |
| F10 | `section_357_valuation.py` 三張河流圖 zone（×3 複本） | L5 | `🟢 便宜區` / `🟡 合理區` / `🔴 昂貴區` / **`⛔ 超昂貴`** | 否 |
| F11 | `section_357_valuation.py` 河流圖色帶 legend | L5 | `7%便宜` / `PE{n}便宜` / `PB{n}便宜:{價}` … | 否 |
| F12 | `src/ui/tabs/tab_stock.py` `_zone2`（組 AI context 字串用） | L5 | `便宜` / `合理` / `昂貴` / `超過昂貴`（裸字） | 否（但餵給 LLM） |
| F13 | `src/ui/tabs/tab_stock.py` `_valuation_simple` | L5 | `昂貴` / `偏貴` / `None` | **是** → 已知問題 #7，§3.6 |
| F14 | `src/ui/tabs/tab_stock_picker.py` PE 河流分級 | L5 | `✅ 便宜 {pe}` / `✅ 合理 {pe}` / `❌ 昂貴 {pe}` / `❌ 超昂貴 {pe}` | 否 |
| F15 | `src/data/core/data_registry.py` 教學對照表 | L1 | `🟢 便宜價／強烈買進（357 殖利率估值法則）` / `⚪ 合理價／中性持有` / `🟡 昂貴，適度減碼` | 否 |

**沒有任何兩個 family 的字面形狀相同。** 差異軸有四條：
(a) emoji 後**有無空格**（F1 有、F7 無）；
(b) 最貴那一級叫 **`超貴` / `超昂貴` / `超過昂貴` / `極貴`** 四種寫法；
(c) 有無 `價` 字尾（`便宜` vs `便宜價`）；
(d) 有無附帶動作語（F8 帶「— 積極買進」、F1 直接就是動作語）。

#### 被當控制流的地方（實測逐一確認）

| # | 消費點 | 比對方式 | 影響 |
|---|---|---|---|
| C1 | `src/ui/tabs/tab_helpers.py:final_recommendation` | `if '便宜' in val: pts += 2` / `elif '合理' in val: pts += 1` | 改 F7 字面 → **綜合建議燈變色** |
| C2 | `src/ui/tabs/tab_helpers.py:classify_stock_status_lamp` | `if '昂貴' in str(label) or '超貴' in str(label)` | 改 F7/F13 字面 → **操作狀態燈變色** |
| C3 | `src/compute/screener/scorability.py:summarize_candidates` | `if health < health_min or (expensive_marker and expensive_marker in _val_txt)`，其中 `EXPENSIVE_VALUATION_MARKER = "超貴"` | 改 F7 的 `超貴` → **汰弱清單變動** |
| C4 | `src/services/app_ai_service.py`（4 處） | `if score>=85 and '便宜' in val and '多頭' in trend` / `elif score>=75 and '便宜' in val` / `if '便宜' in val` / `elif '昂貴' in val or '超貴' in val` | 改字面 → **AI 摘要結論變動** |
| C5 | `src/compute/risk/risk_radar.py:_apply_third_axis_overlay` | `if valuation_level == "極貴"` / `elif valuation_level == "便宜"`（**全等**，不是 `in`） | ⚠️ **實測為死碼** —— 見下 |

**✅ C3 是全表唯一做對一半的**：它把比對字串抽成具名常數 `EXPENSIVE_VALUATION_MARKER`
並在註解裡寫明產生端（`# 產生端：section_batch_fetcher 的 val4 = '🔴超貴'`）。
⚠️ **但仍是字面耦合** —— 常數存的是 `"超貴"` 這個**中文子字串**，不是 code。
且它**接不住其他 family**：`'⛔ 超昂貴'`（F10）、`'🔴超過昂貴'`（F8）都**不含**子字串 `超貴` → 不會被汰弱。

**⚠️ C5 是死碼（本次新發現，實測）**：
`risk_radar.synthesize_dual_verdict(..., *, valuation_level: str | None = None, ...)` —— 
`grep -rn "valuation_level\s*=" --include=*.py .` 在 **production code 0 命中**，
唯一傳值的是 `tests/test_dual_verdict_ui.py`（5 處）。
⇒ **`== "極貴"` / `== "便宜"` 兩個分支在 production 永遠不會執行。**
⚠️ 這正是 `CLAUDE.md §-2` 點名的 `db4c139` 型態（「看起來有守衛、實際不觸發」）——
留著會讓下一個人以為「估值疊加已接線」。
（**單組 grep 結論，未複驗**。）

**✅ 全表唯一做對的樣板：`src/ui/tabs/stock_sections/section_psy_checklist.py`**
```python
_code357, _ = classify_stock_357_price(price, avg_div)
...
('💎 非357昂貴區',
 None if _code357 == 'na' else (_code357 in ('cheap', 'fair')),
 '無配息資料,357 不適用'),
```
比對的是 **F2 的 code**，不是中文；缺值回 **`None`**（第三態），不是 `False`。
該檔 docstring 自陳這是修一個舊 bug 的結果：原本讀 `t2_data['val']` 這個**全站沒有寫入點的幽靈 key**，
`'昂貴' not in ''` 恆為 True ⇒ **這一項對每一檔股票恆綠**。
⇒ **這段歷史正是「字面耦合會怎麼壞」的實證**，建議其餘消費點沿用本樣板。

---

### 2.7 ⚠️ 已知問題 #2 — 同一支函式兩種字串耦合（emoji vs 中文）

**位置**：`src/compute/etf/etf_recommendation.py:recommend_etf_action`

```python
liquidity  = str(_row.get('liquidity_level') or '')
div_health = str(_row.get('dividend_health') or '')
...
if '🔴' in liquidity:              # ← emoji
    red_flags.append('流動性高風險(量小/規模小,不易進出)')
if '吃本金' in div_health:          # ← 中文
    red_flags.append('配息吃本金(含息報酬 < 殖利率)')
...
val = str(_row.get('valuation_zone') or '')
_cheap = ('🟢' in val) or (sigma_z is not None and sigma_z <= SIGMA_Z_CHEAP)   # ← emoji
_rich  = ('🔴' in val) or (sigma_z is not None and sigma_z >= SIGMA_Z_RICH)    # ← emoji
```

**三個欄位、兩種標準，全在同一支函式內。**

**實測反例（`_probe_ind.py`）—— 改一個字就改行為**：

| 輸入 | 輸出 |
|---|---|
| `valuation_zone='🟢 強烈買進'` | `reasons=['綜合分 0.70(≥0.65)體質佳', '價位偏低,分批加碼時機較佳']` |
| `valuation_zone='綠 強烈買進'`（只換 emoji） | `reasons=['綜合分 0.70(≥0.65)體質佳']` ← **註解靜默消失** |
| `dividend_health='🔴 吃本金 -2.0pp'` | `verdict=觀察`、`red_flags=['配息吃本金(含息報酬 < 殖利率)']` |
| `dividend_health='🔴 侵蝕本金 -2.0pp'`（只換中文措辭） | `verdict=留下`、`red_flags=[]` ← **紅旗消失、結論從「觀察」翻成「留下」** |

⇒ **改一句文案就會翻掉一檔 ETF 的結論**，而且 emoji 沒變、紅底沒變，畫面上看不出來。

**為什麼 emoji 那條特別危險**：`'🔴'` 這個字元在本站同時代表
「危險」（`liquidity_level`）、「貴」（`valuation_zone`）、「吃本金」（`dividend_health`）三種語意。
`_rich = ('🔴' in val)` 只在 `val` 剛好是 `valuation_zone` 時才對 —— 這個正確性**靠呼叫端傳對欄位**維持，
**沒有任何型別或命名保證**。

**門檻常數（這部分 ✅ 全走 SSOT）**：
`shared/etf_recommendation_thresholds.py:KEEP_COMPOSITE_MIN=0.65` / `SELL_COMPOSITE_MAX=0.35` /
`SIGMA_Z_CHEAP=-1.0` / `SIGMA_Z_RICH=1.0` / `REDUNDANCY_MIN_PEERS=2` /
`VERDICT_KEEP="留下"` / `VERDICT_WATCH="觀察"` / `VERDICT_SWITCH="考慮換"` / `VERDICT_NA="資料不足"`
＋ `shared/signal_thresholds.py:ETF_TRACKING_ERROR_MAX_PCT=1.5`

**判定規則（`recommend_etf_action`，分支順序即程式順序）**：
```
# ── 階段 0：擋掉不可評估 ──
if row['error']:                    → verdict='資料不足', reasons=['抓取失敗,無法評估']
if composite is None:               → verdict='觀察',     reasons=['缺關鍵指標,綜合分無法計算 —— 先觀察']

# ── 階段 1：綜合分分級 ──
if   composite >= 0.65:             base='留下'
elif composite <  0.35:             base='考慮換'
else:                               base='觀察'

# ── 階段 2：紅旗降級（留下→觀察→考慮換，考慮換維持）──
red_flags = []
if '🔴' in liquidity_level:                                     red_flags += ['流動性高風險']
if '吃本金' in dividend_health:                                  red_flags += ['配息吃本金']
if tracking_error > 1.5 and tracks_tw50_index(ticker):          red_flags += ['追蹤誤差…']
if red_flags and base=='留下':   verdict='觀察'
elif red_flags and base=='觀察': verdict='考慮換'
else:                            verdict=base

# ── 階段 3：位階註解（只加註解，不改 verdict）──
if verdict in ('留下','觀察'):
    if   ('🟢' in valuation_zone) or (sigma_z <= -1.0): reasons += ['價位偏低,分批加碼時機較佳']
    elif ('🔴' in valuation_zone) or (sigma_z >=  1.0): reasons += ['價位偏高,續抱可、暫緩加碼']
```
⚠️ **追蹤誤差紅旗有一道刻意的閘門**（該檔註解原文）：只對「**本就該追 0050 那支指數**」的 ETF
（`etf_categories.tracks_tw50_index` → 0050 / 006208）生效。高股息 / 主題 / 債券 ETF 追不同指數，
TE vs 0050 天生偏高，強制降級會誤殺（`CLAUDE.md §-1`）。**✅ 這是本檔做得好的一處防禦。**

**缺值行為**：✅ `composite is None` → `'觀察'` + 明說「缺關鍵指標」，**不落「留下」也不落「考慮換」**。
⚠️ 但 `'觀察'` 同時也是「綜合分中等」的結論 —— **「算不出來」與「中等」在 verdict 欄同形**，
只能靠 `reasons` 分辨（消費端若只讀 verdict 就分不出）。

---

## 3. 燈號類

### 3.1 五桶 16 盞燈（`classify_danger`）

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面「五桶」／程式 `shared/macro_buckets.py:classify_danger(value, spec)` |
| **算式** | 無算式 —— 純門檻分級。每盞燈一個 `DangerSpec(key, label, bucket, unit, direction, yellow, red, [yellow_lo, red_lo], decimals, note, source)` |
| **輸入** | 各燈一個純量，由 `macro_helpers.compute_five_bucket_summary` 的 values dict 供給 |
| **單位** | **逐燈不同**，寫在 `DangerSpec.unit`：`""`（無量綱）/ `"%"` / `"億"` / `"口"` / `"分"` / `"則"` / `"TWD/USD"` |
| **門檻常數** | `shared/macro_buckets.py:BUCKET_DANGER_SPECS`（16 個，**唯一清單**）；查表用 `SPECS_BY_KEY` |
| **判定規則** | 見下方三個 direction |
| **缺值行為** | ✅ **正確**：`value is None` 或 `float()` 失敗 → `"gray"`（⬜）。檔內明文「**不偽綠**」。<br>✅ **gray 不參與 worst 彙總** —— `LEVEL_RANK` 只有 green/yellow/red |
| **合理範圍** | 部分燈有 `valid_min` / `valid_max`（`us10y` [0,20]、`dxy` [70,130]，對齊 `CLAUDE.md §3.2`）；其餘無 |

```
def classify_danger(value, spec) -> 'green'|'yellow'|'red'|'gray':
    if value is None:                      return 'gray'
    try: v = float(value)
    except (TypeError, ValueError):        return 'gray'

    if spec.direction == 'high_bad':       # 值越高越危險
        if v >= spec.red:                  return 'red'
        if v >= spec.yellow:               return 'yellow'
        return 'green'

    if spec.direction == 'low_bad':        # 值越低越危險
        if v <= spec.red:                  return 'red'
        if v <= spec.yellow:               return 'yellow'
        return 'green'

    # direction == 'band'：高低兩側皆有危險帶
    if (spec.red_lo    is not None and v <= spec.red_lo)    or v >= spec.red:    return 'red'
    if (spec.yellow_lo is not None and v <= spec.yellow_lo) or v >= spec.yellow: return 'yellow'
    return 'green'
```

**16 盞燈的門檻表**（值與 `source` 欄逐字取自 `shared/macro_buckets.py:BUCKET_DANGER_SPECS`）

| 桶 | key | 畫面名 | 單位 | direction | yellow | red | 門檻出處（`DangerSpec.source` 原文） |
|---|---|---|---|---|---|---|---|
| long | `health` | 總經健康評分 | — | low_bad | 50 | 35 | `SSOT`（`_HEALTH_YELLOW` / `_HEALTH_RED`） |
| long | `ndc_signal` | NDC 景氣對策燈號 | 分 | **band** | 32 / lo 23 | 38 / lo 16 | `DESIGN:NDC 燈號 9藍-45紅` |
| long | `m1b_m2_gap` | M1B-M2 資金動能 | % | low_bad | 1.0 | 0.0 | `DESIGN:資金動能交叉慣例` |
| mid | `ism_pmi` | 台灣 PMI | — | low_bad | 50.0 | 46.0 | `SSOT:MACRO_THRESHOLDS.PMI` |
| mid | `us_core_cpi` | 美國核心 CPI YoY | % | high_bad | 3.5 | 4.0 | `SSOT:MACRO_THRESHOLDS.CPI` |
| mid | `tw_export` | 台灣出口訂單 YoY | % | low_bad | 0.0 | −5.0 | `SSOT:tab_macro 出口否決權 -5%` |
| mid | `bias_240` | 年線乖離率 BIAS240 | % | high_bad | 10.0 | 20.0 | `SSOT:macro_helpers ±20 + DESIGN(10)` |
| mid | `us10y` | 10Y 公債殖利率 | % | high_bad | 4.5 | 5.0 | `SSOT:MACRO_THRESHOLDS.US10Y` |
| mid | `dxy` | 美元指數 DXY | — | high_bad | 105.0 | 110.0 | `SSOT:MACRO_THRESHOLDS.DXY` |
| short | `vix` | VIX 恐慌指數 | — | high_bad | 22.0 | 30.0 | `SSOT:MACRO_THRESHOLDS.VIX` |
| short | `adl` | ADL 漲跌家數比 | % | low_bad | 50.0 | 🔴 **35.0 inline** | `SSOT:MARKET_BREADTH_NEUTRAL_PCT(50)+DESIGN(35)` |
| short | `fut_net` | 外資期貨淨口 | 口 | low_bad | −10000 | −20000 | `SSOT:FOREIGN_FUTURES_*_LOTS` |
| chips | `margin` | 融資餘額 | 億 | high_bad | 2500 | 3400 | `SSOT:MARGIN_BALANCE_OVERHEAT(3400)+WARN(2500)` |
| chips | `jingqi` | 旌旗指數（上漲佔比 5 日均 %） | % | low_bad | 🔴 **60.0 inline** | 🔴 **40.0 inline** | `DESIGN:廣度佔比經驗切點(60/40)` |
| chips | `foreign_net` | 外資現貨淨買賣 | 億 | low_bad | 0.0 | −200.0 | `DESIGN:外資現貨流向` ⚠️ **`wired=False`** |
| news | `news_systemic` | 系統性風險新聞數 | 則 | high_bad | 1 | 2 | `DESIGN:命中則數規則` |

**＋1 盞「參考走勢」不計入分母**：`usdtwd`（新台幣匯率，`REFERENCE_BUCKET`）——
`DangerSpec.note` 原文自陳「**參考走勢：不計入 16 盞燈的分母、不進五桶彙總**」。

**⚠️ 三盞燈檔內自陳有結構問題（逐字引用，非本檔推論）**：
1. **`foreign_net` 從未亮過**：`wired=False`，`unwired_reason` 原文 ——
   「FinMind inst net 單位未確認（股 / 千股 / 億元）—— §4.1。確認前填值會直接誤判紅綠燈，
   故決策端刻意回 None（§1 寧缺勿錯）」。⇒ **這盞燈自註冊以來恆灰**，而 `wired` 旗標讓它可被程式識別。✅ 正確處置。
2. **`margin` 燈號恆紅**：`note` 原文 ——「本項用的是**絕對金額門檻，未隨市場總市值成長調整** ——
   目前餘額已長期高於兩條線，燈號會持續偏紅」。`shared/macro_buckets.py` 另一處註解自陳實測 5,148 億「已同時穿透兩線」。
   ⇒ **鑑別力接近零**，但門檻未動（改門檻屬行為變更）。
3. **`health` 名不副實**：`note` 原文 ——「此分只有 2 個輸入 … 實質是『趨勢廣度分數』；
   不含融資／外資期貨／年線乖離／NDC／M1B-M2／VIX／PMI／CPI／出口／ADL／新聞」。見 §3.2。

---

### 3.2 總經健康評分（`health`）與總經紅綠燈

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面「總經健康評分」／程式 `src/compute/macro/macro_helpers.py:calc_traffic_light` 的 `health` 欄 |
| **算式** | `score_pct = min(score ÷ max_score × 100, 100)`　（`max_score` 缺 → 預設 4.0）<br>`parts = [(jqavg, 0.6)] if jqavg is not None else []`　`+ [(score_pct, 0.4)] if score_pct is not None else []`<br>`w_sum = Σ wᵢ`<br>`health = round( Σ(vᵢ·wᵢ) ÷ w_sum + fnet_bonus , 1)`　if `w_sum > 0`<br>`fnet_bonus = HEALTH_FNET_BONUS if (fnet is not None and fnet > 0) else 0` |
| **輸入** | `jqavg`（旌旗指數＝**上漲家數佔比的 5 日均**，%）← `src/services/jingqi_calc.py`；`score` / `max_score` ← `market_strategy.market_regime()`；`fnet`（外資現貨淨額）← 三大法人 |
| **單位** | `health` **無量綱分數 0~100**；`jqavg` **%**；`score` **分**；`max_score` **分** |
| **門檻常數** | 權重 `shared/signal_thresholds.py:HEALTH_WEIGHT_JQ=0.6` / `HEALTH_WEIGHT_SCORE=0.4` / `HEALTH_FNET_BONUS=0`<br>燈號切點 `macro_thresholds.json:HEALTH_DEFENSE_THRESHOLD=35` / `BULL_MIN_SCORE=4`（**唯二有設定檔覆寫路徑者**） |
| **判定規則** | `if jqavg is None and score_pct is None: health = None` → arbiter 回 `UNLOADED_VERDICT`（⬜ 總經未評估）<br>`elif jqavg is None: health = score_pct`（分母 0.4 重新歸一化），`health_partial = True`<br>`elif score_pct is None: health = jqavg`（分母 0.6 重新歸一化），`health_partial = True`<br>`else: health = jqavg×0.6 + score_pct×0.4`，`health_partial = False` |
| **缺值行為** | ✅ **本站做得最好的一處**。兩條腿都缺 → `health = None`。檔內原文：「誠實說『算不出來』，**不是 0 分（0 分會被判成最強利空），也不是 🟡（🟡 是一個市場判斷）**」。<br>✅ 單腿缺 → **權重重新歸一化**（v19.177 P1-B），**不用中性值頂替**；缺項列進 `missing_sources`、回 `health_partial=True` 供畫面標示 |
| **合理範圍** | [0, 100]（`CLAUDE.md §3.2`「健康評分 [0,100]」）。⚠️ 實際值域被壓縮 —— 見下 |
| **對帳** | `health_reconcile.reconcile_health_score`（Method A ↔ Method B），**僅輸入齊全時才跑**，走 stderr log，不改 UI（`CLAUDE.md §4.3` 雙演算法對帳） |

**⚠️ 三個檔內自陳的結構問題（逐字引用）**：
1. **`shared/position_throttle.py` 自陳**：`jqavg`（σ=3.32）在數學上是個**準常數 ≈ +29.8**，
   對 health 變異只貢獻 2.8%，`corr(health, score_pct) = 0.987`
   ⇒ **`health ≡ 29.8 + 0.4 × score_pct`，實際值域被壓成 [21.6, 78.1]**。
   ⇒ 名義「0.6 廣度 + 0.4 評分」在實務上**幾乎純粹是 score_pct 的仿射變換**。
   ⇒ **合理範圍雖宣告 [0,100]，實際永遠碰不到兩端。**
2. **`HEALTH_FNET_BONUS = 0`** → `fnet_bonus` 恆為 0 ⇒ **該項為 dead term**
   （`macro_thresholds.json` 註解自陳這是 v19.102 校準後的「明示歸零，有 AUC 佐證，非漏寫」，但「已是 dead term、可讀性差」）。
3. **切點未校準**：`macro_thresholds.json` 的 `last_calibrated: null` / `method: "default (uncalibrated)"`；
   該檔註解自陳「權重端用 AUC 最佳化、切點端憑直覺，**等於把 ROC 曲線畫出來了卻隨手挑一個 operating point，兩端證據等級不對等**」。

---

### 3.3 ⚠️ `max_score` 恆為 None（本次複驗：**問題仍在**）

**四段證據，全部本次實測**：

1. `src/compute/macro/macro_helpers.py` 全檔 `grep max_score` → **只有 4 個命中**：
   `:370`（註解）、`:372`（`_max_score = float(_mkt.get('max_score') or 4.0)`）、
   `:374`（算 `_score_pct`）、`:425`（傳給對帳函式）。
   **`calc_traffic_light` 的 return dict 內 0 命中** ⇒ 讀進來、用掉、**不輸出**。
2. `src/compute/macro/macro_forward_test.py:build_signal_row` 確實在讀它：
   `'max_score': _opt_float(tl.get('max_score'))` —— 用 `.get()` 不是 `[...]` ⇒ **不會 KeyError，只會靜默回 None**。
3. `shared/macro_forward_test_schema.py` 對該欄的註解逐字寫：
   `"max_score",  # float 當日實際分母(會隨選填腿在/不在浮動 —— 必存)`
   ⇒ **schema 自己宣告「必存」。**
4. **production parquet 實測**（`data_cache/macro_forward_test/signals.parquet`，量測日 2026-09-15）：
   `rows = 16`、**`max_score notna = 0 / 16`**、`score sample = [2.5, 2.5, 2.5, 1.5, 3.5]`。

**為什麼這件事比「一個欄位是空的」嚴重**：
`max_score` **會浮動**（基本 4，`ad_ratio` / `m1b_m2` 腿有傳才升 5/6）。
實測 parquet 裡 `score = 3.5`，配上未知分母 —— 可能是 3.5/4（87.5%）也可能是 3.5/6（58.3%），
**`score_pct` 語意完全不同** ⇒ **前進式驗證的 parquet 無法重建當日的 health**。
而那是本專案唯一零 lookahead 的驗證資料集（`CLAUDE.md §2.3`）。

📌 **與 `S1-2 §2.2` 的差異（本次複驗更新）**：S1-2 記錄 12 列、`score` 為整數 `[4.0, 3.0, 5.0]`；
現為 **16 列**、`score` 為 **0.5 級距** `[2.5, 1.5, 3.5]`。
⇒ 新增的 4 列**仍然沒有 `max_score`**；`score` 改成小數這件事**本次未追原因**（見 §9）。

---

### 3.4 235 加碼燈（已知問題 #8）

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面「235 燈號」／程式 `src/compute/etf/dividend_station.py:light_235` |
| **算式** | 無單一算式 —— **三軸取最嚴重**。三軸＝ VIX / 週線 / 20 週布林 z。<br>`z = (週收 − MA20週) ÷ std20週(ddof=0)`（`bollinger_z`）<br>`weekly_close` 由 `weekly_closes(daily_close)` 以 `"W-SUN"` resample 得出 |
| **輸入** | `vix`（點數）、`weekly_close`（**最新週收純量**）、`ma4w` / `ma13w` / `ma52w`（週均線）、`z`（σ 位階） |
| **單位** | `vix` **點數（非 %）**；`weekly_close` / `ma*w` **元**；`z` **標準差倍數（σ）**；`deploy_pct` **%** |
| **門檻常數** | `shared/dividend_station_thresholds.py`：<br>`VIX_LIGHT1=20.0` / `VIX_LIGHT2=25.0` / `VIX_LIGHT3=30.0`<br>`Z_LIGHT1=-1.0` / `Z_LIGHT2=-2.0` / `Z_LIGHT3=-3.0`<br>`Z_TAKE_PROFIT_PARTIAL=2.0` / `Z_TAKE_PROFIT_FORCE=3.0`<br>`MA_MONTH_WEEKS=4` / `MA_QUARTER_WEEKS=13` / `MA_YEAR_WEEKS=52`<br>`DEPLOY_LIGHT1_PCT=20.0` / `DEPLOY_LIGHT2_PCT=30.0` / `DEPLOY_LIGHT3_PCT=50.0`<br>`BOLL_PERIOD_WEEKS=20` / `MIN_WEEKS_FOR_BOLL=20` / `MIN_WEEKS_FOR_YEAR_LINE=52` |
| **缺值行為** | ✅ **逐軸判可用性**（2026-08-25 稽核後改）。`_ok(v) = (v is not None and math.isfinite(v))` —— **NaN 也擋掉**。<br>三軸全不可用 → `miss_reason = MISS_NO_INPUT`，且 reasons 寫「**…3 個判斷依據都沒有資料 —— 不是「都沒觸發」，是沒東西可以判**」<br>⚠️ **但燈號仍是 `LIGHT_CRUISE`（⚪ 巡航）** —— 檔內明文：「本欄**不改判燈結果**，只讓消費端能把這種 cruise 跟『真的很平靜』的 cruise 分開顯示」 |
| **合理範圍** | `z` 無理論界；`vix` `CLAUDE.md §3.2` 記 [5,100]（此處未套用 sanity） |

**判定規則（分支順序即程式順序，順序會改變結果）**：
```
# 步驟 1：逐軸可用性
axes_used = []
if _ok(vix):                                            axes_used += ['vix']
if _ok(weekly_close) and any(_ok(m) for m in (ma4w, ma13w, ma52w)):  axes_used += ['weekly']
if _ok(z):                                              axes_used += ['boll']
miss = '' if axes_used else MISS_NO_INPUT

# 步驟 2：蒐集所有觸發條件（可多個）
conds = []
# 燈三
if vix >= 30.0:                                          conds += [(LIGHT_3, 'VIX≥30')]
if weekly_close < ma52w and z < -2.0:                    conds += [(LIGHT_3, '週收<年線且布林<-2σ')]
if z < -3.0:                                             conds += [(LIGHT_3, '布林<-3σ')]
# 燈二
if 25.0 <= vix < 30.0:                                   conds += [(LIGHT_2, 'VIX 25~30')]
if weekly_close < ma13w:                                 conds += [(LIGHT_2, '週收<季線')]
if z < -2.0:                                             conds += [(LIGHT_2, '布林<-2σ')]
# 燈一
if 20.0 <= vix < 25.0:                                   conds += [(LIGHT_1, 'VIX 20~25')]
if weekly_close < ma4w:                                  conds += [(LIGHT_1, '週收<月線')]
if z < -1.0:                                             conds += [(LIGHT_1, '布林<-1σ')]
（每個 if 都另帶 `is not None` 前置檢查，缺值不觸發該條件）

# 步驟 3：停利軸優先（與加碼互斥；先 return）
if z > 3.0:   return 停利(force)   # 💰
if z > 2.0:   return 停利(partial) # 💰

# 步驟 4：三取一取最嚴重
if conds: best = max(conds, key=_SEVERITY)   # cruise0 < light1 < light2 < light3
else:     best = LIGHT_CRUISE

# 步驟 5：深水防守註記（不改燈，只加一行字）
if weekly_close < ma52w:
    if   ma13w is not None and weekly_close >= ma13w: note='已站回 13 週季線 → 留意落底回升訊號'
    elif z is not None and z >= -2.0:                 note='週收破年線但布林未達 -2σ → 等共伴確認,先別重壓'
```

**燈號 → 動用比例評分表**（`shared/dividend_station_thresholds.py:LIGHT_META`）：

| 常數 | icon | label（**原文**） | `deploy_pct` |
|---|---|---|---|
| `LIGHT_CRUISE` | ⚪ | `巡航（定期定額）` | 0.0 |
| `LIGHT_1` | 🟢 | `小跌加碼` | 20.0 |
| `LIGHT_2` | 🟡 | `急跌加碼` | 30.0 |
| `LIGHT_3` | 🔴 | `崩盤/深水加碼` | 50.0 |
| `LIGHT_TAKE_PROFIT` | 💰 | `停利警示` | 0.0 |

**⚠️ 已知問題 #8 — 燈的名字本身帶動作語**（合規待處理）：
`小跌加碼` / `急跌加碼` / `崩盤/深水加碼` / `停利警示` —— 四個 label 有三個含「**加碼**」、一個含「**停利**」。
`deploy_pct` 更直接給出「動用閒置加碼金 20/30/50%」的**比例數字**。
依客戶合規判準（缺項填補測試）：從「VIX 25、跌破季線」走到「動用 30% 資金」，
中間必須代入**只有使用者才知道的變數**（可動用資金、風險承受度、既有部位），而這裡**替他填了**
⇒ 依該判準這是建議。
⚠️ **本項不是本文件的用語，是現行 code 的 label 常數**，要改**只能改 code**（v1 凍結中，本階段唯讀）。

**⚠️ 一段已被修掉的死碼，值得記錄為前例**（`light_235` docstring 逐字引用）：
> 原本只在「vix / z / weekly_close **三個都是 None**」時才標缺資料，那個條件在 production **永遠為 False**：
> 唯一的呼叫端 `assess_holding` 會先把空序列 raise 掉 …
> **實測 21,168 組真實輸入，`miss_reason` 無一非空 = 整段防護等於不存在。**
> 另外 `NaN` 也躲得過：`float("nan") is not None` 為真，但 NaN 與任何門檻比較都是 False → 該軸**靜默失效**卻不算缺資料。

⇒ 這是 `CLAUDE.md §-2` 的 `db4c139` 前例在本模組的同型事故，**已修**（改逐軸 `_ok`）。
⇒ **本檔 §2.6 的 C5（`risk_radar.valuation_level` 死碼）是同一型態、尚未處理。**

---

### 3.5 存股健檢 A / B / C / D

四盞燈同在 `src/compute/etf/dividend_station.py`，回傳 `Flag(level, msg, miss_reason)`。
**這是全站缺值語義化做得最完整的一組** —— `Flag` 帶 `miss_reason` 欄位，
檔內理由原文：「解析 msg 字串太脆弱 —— **改一個字就壞**」。（正是 §2.6 那個病的正解。）

| 燈 | 算式 | 單位 | 門檻常數 | 判定規則 | 缺值行為 |
|---|---|---|---|---|---|
| **A 不吃本金** | 比較 `total_return_1y_pct` vs `annual_yield_pct`<br>`annual_yield_pct = ttm_dividend ÷ price × 100`<br>`total_return_pct = (end_close ÷ start_close − 1) × 100`（**用還原價 → 已含息**） | 兩者皆 **%** | 無門檻常數（直接比大小） | `if 兩者皆 None: ⚪`<br>`elif total_return is None: ⚪`<br>`elif annual_yield is None: ⚪`<br>`elif total_return < annual_yield: 🔴 賺息賠本`<br>`else: 🟢 未吃本金` | ✅ **兩個輸入的缺法分開標**：缺總報酬 → `MISS_NOT_ENOUGH`（日線不足一年＝新上市，**重跑無用**）；缺配息率 → `MISS_NO_INPUT`（抓取失敗，**重跑有機會**）；皆缺 → `most_fundamental_miss` 取較根本者 |
| **B 夏普** | `sharpe_weekly(weekly_close, min_weeks=13, rf_pct)`<br>`= (mean(週報酬) − rf_pct/100/52) ÷ std(週報酬, ddof=1) × √52` | **無量綱比值**；`rf_pct` **%** | `shared/dividend_station_thresholds.py:SHARPE_NEG_THRESHOLD=0.0`<br>`MA_QUARTER_WEEKS=13`（min_weeks）<br>rf 來源 `shared/signal_thresholds.py:ETF_SHARPE_RF_FALLBACK_PCT=5.33` | `if sharpe is None: ⚪`<br>`elif sharpe < 0.0: 🔴 承擔風險卻無超額報酬`<br>`else: 🟢` | ✅ `None` → ⚪ + `MISS_NOT_ENOUGH`。檔內明文更正：三條 None 路徑（週數不足／報酬筆數不足／波動≈0）**都是「有資料但算不出來」**，沒有一條是抓取失敗 ⇒ 標「可以重跑」對新上市 ETF 是**錯誤指引** |
| **C 趨勢防守** | `ma13 = week_ma(weekly, 13)`；`slope = week_ma_slope(weekly, 13)` | 元 / 斜率 | `MA_QUARTER_WEEKS=13`（訊息文字亦走 SSOT 插值，門檻改了訊息跟著改） | `if ma13 is None or slope is None: ⚪`<br>`elif close < ma13 and slope < 0: 🟡 趨勢轉弱`<br>`else: 🟢 趨勢守穩` | ✅ ⚪ + `MISS_NOT_ENOUGH` |
| **D 折溢價** | `calc_premium_discount(info, df, ticker)` → `premium_pct`（官方 iNAV 同日 inner-join + 3 守門員 G1/G2/G3 + sanity 上限） | **%** | `shared/dividend_station_thresholds.py:PREMIUM_ALERT_PCT=1.5` | `if premium_pct is None: ⚪`<br>`elif premium_pct > 1.5: 🟡 高溢價`<br>`else: 🟢 正常` | ✅ `stale_nav` / `premium_pct=None` → **不填** `m["premium_pct"]` → 標「無折溢價資料」，**不假判**。<br>📌 歷史教訓：末端 fallback 到 yfinance `navPrice` 會回「最後已公告淨值」被硬戳今日 → **假溢價觸發假 🟡**（v18.442 修的 0050 假 +5.07%） |

**四燈彙總** `_worst_level(*flags)` → 取最嚴重那一級。
⚠️ 該函式 docstring 自陳的限制（逐字）：「這個彙總**天生會丟掉「為什麼」**：四盞燈都 ⚪ 時回一個裸 ⚪，
原因（四種，處置各不同）全部消失。**刻意不在這裡合併原因**」。

**⚠️ B 燈的 Sharpe 與 ETF 綜合分的 Sharpe 不是同一支**（§5.1）：
B 燈吃 `sharpe_weekly`（週×√52，缺值回 `None` ✅）；
ETF 綜合分吃 `etf_calc.calc_sharpe`（日×252，缺值 🔴 **回 `0.0`**）。**同一檔 ETF 兩個 Sharpe。**

---

### 3.6 操作狀態燈（已知問題 #7 — **本次複驗，客戶陳述需要更正**）

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面「狀態燈」／「操作狀態」欄／程式 `src/ui/tabs/tab_helpers.py:classify_stock_status_lamp` |
| **算式** | 無算式 —— 四維度合議的 if-else 串 |
| **輸入** | `health_score`（0-100）、`trend_label`（字串）、`bias_pct`（MA20 乖離 %）、`vol_ratio`（當日量÷20日均量）、`valuation_label`（**字串**） |
| **單位** | `health_score` 分；`bias_pct` **%**；`vol_ratio` **倍**；其餘字串 |
| **門檻常數** | `shared/health_thresholds.py:HEALTH_GRADE_A_MIN=80`<br>`shared/signal_thresholds.py:GRP_VOL_SHRINK_RATIO=0.7` / `GRP_NEAR_MA20_BIAS_PCT=3.0` / `GRP_BIAS_OVERHEAT_WARN_PCT=25.0` |
| **判定規則** | 見下（**順序即程式順序，前面命中就 return**） |
| **缺值行為** | 全部輸入皆 None → 落 `return '⚪'`。⚠️ **`⚪` 同時代表「中性」與「資料不足」**（§0.3 符號超載）—— docstring 自陳「`⚪ 中性:其餘 / 資料不足`」，**兩種語意明文共用一個符號** |

```
if (health_score is not None and health_score >= 80
        and trend_label and '多頭' in str(trend_label)
        and vol_ratio is not None and vol_ratio < 0.7
        and bias_pct is not None and abs(bias_pct) < 3.0):
    return '🔵 加碼'                                    # 引用：現行 code 的 label
if bias_pct is not None and bias_pct > 25.0:
    return '🟡 警示'
if valuation_label and ('昂貴' in str(valuation_label) or '超貴' in str(valuation_label)):
    return '🟠 減碼'                                    # 引用：現行 code 的 label
return '⚪'
```

**⚠️ 兩個呼叫端傳的 `valuation_label` 來自不同 family（本次實測）**

| 呼叫端 | 傳什麼 | 可能值 |
|---|---|---|
| **個股頁** `src/ui/tabs/tab_stock.py` `_valuation_simple` | 由 `classify_yield_zone(cur_yield)` 的 **code** 再映射 | `'昂貴'`（code=`sell`，殖利率 ≤3%）／`'偏貴'`（code=`reduce`，3<殖利率≤5%）／`None`（其餘） |
| **組合頁** `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py` `val4` | F7 family | `'🟢便宜'` / `'🟡合理'` / `'🔴昂貴'`（3~5% 帶）/ `'🔴超貴'`（<3%）/ `'⚪無股利'` |

**實測結果（`_probe_ind.py`）**：

| 傳入 label | 回傳 |
|---|---|
| 個股頁 `'偏貴'` | **`⚪`** ← 不觸發 |
| 個股頁 `'昂貴'` | `🟠 減碼` |
| 組合頁 `'🔴昂貴'` | `🟠 減碼` |
| 組合頁 `'🔴超貴'` | `🟠 減碼` |

**📌 客戶陳述的更正**：客戶記「**個股頁那段可能永遠點不亮**」（並自標未複驗）。
**本次複驗：不是永遠點不亮，是「半盲」。**

- **殖利率 ≤ 3%**：兩頁**都**點得亮 🟠
- **3% < 殖利率 ≤ 5%**：**組合頁點得亮、個股頁點不亮** ← 這才是實際的落差帶
- **`'偏貴'` 這個字面在全站沒有任何消費端會匹配** ⇒ 它是**被算出來、被傳進去、然後被丟掉**的死值

**根因**：`'偏貴'` 既不含子字串 `昂貴`，也不含 `超貴`。
⇒ 同一檔股票、同一個殖利率，在兩個分頁會看到**不同的操作狀態燈**。

---

### 3.7 個股最終綜合建議（評分表）

| 欄 | 內容 |
|---|---|
| **指標名** | 組合頁「綜合建議」欄／程式 `src/ui/tabs/tab_helpers.py:final_recommendation` |
| **算式** | 四項加分累計 `pts`（見下表），再分三級 |
| **輸入** | `row['_health']`（0-100）、`score_map[sid]['total']`（多因子總分 0-100）、`row['_val']`（**F7 字面**）、`row['_trend']`（字串） |
| **單位** | 前兩者 **分**；後兩者 **字串** |
| **門檻常數** | `shared/health_thresholds.py:HEALTH_GRADE_A_MIN=80` / `HEALTH_GRADE_B_MIN=50`<br>🔴 **其餘全為 inline**：`75` / `55`（多因子切點）、加分權重 `3/1/3/1/2/1/1`、分級線 `7` / `4` |
| **合理範圍** | `pts` 理論 [0, 9]（3+3+2+1） |

**評分表**（`_` = 不加分）

| 維度 | 條件 | 加分 | 門檻出處 |
|---|---|---|---|
| 健康度 | `health >= 80` | +3 | ✅ `HEALTH_GRADE_A_MIN` |
| 健康度 | `80 > health >= 50` | +1 | ✅ `HEALTH_GRADE_B_MIN` |
| 多因子 | `mf_total >= 75` | +3 | 🔴 **inline 75**（⚠️ `shared/signal_thresholds.py:MULTIFACTOR_GRADE_A_MIN=75.0` **存在但沒被引用**） |
| 多因子 | `75 > mf_total >= 55` | +1 | 🔴 **inline 55**（⚠️ 同上，`MULTIFACTOR_GRADE_B_MIN=55.0` 存在未引用） |
| 估值 | `'便宜' in _val` | +2 | 🔴 **字面耦合**（§2.6 C1） |
| 估值 | `'合理' in _val` | +1 | 🔴 同上 |
| 趨勢 | `'多頭' in _trend` | +1 | 🔴 **字面耦合** |

**分級**：`if pts >= 7: '🟢 積極'` ／ `elif pts >= 4: '🟡 觀察'` ／ `else: '🔴 等待'`（皆 🔴 inline）

**⚠️ 缺值行為（🔴 客戶紅線）**：
```python
health   = row.get('_health', 0)      # ← 缺 → 0
mf_total = score_map.get(...).get('total', 0)   # ← 缺 → 0
val      = row.get('_val', '')        # ← 缺 → 空字串 → 兩個 in 都 False → +0
trend    = row.get('_trend', '')      # ← 同上
```
🔴 **四個輸入全部 `default 0` / `default ''`，缺值一律當「最差」計分。**
實測 `section_batch_fetcher.py` 的錯誤列寫 `{'_health': 0, '_val': '-', '_trend': '-'}`
⇒ **一檔抓取失敗的股票會拿到 `pts=0` → `'🔴 等待'`**，
而畫面上它與「真的四項都很差」的股票**長得一模一樣**。
⚠️ **沒有 `⚪ 未評估` 這一級**（對照 §3.5 的 `Flag` 有 `⚪` + `miss_reason`）。

---

### 3.8 3-3-3 挑三原則

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面「3-3-3」欄／程式 `src/compute/etf/dividend_station.py:screen_333` |
| **算式** | 三個子項布林 AND |
| **輸入** | `inception_years`（`(as_of − 最早資料日) ÷ 365.25`）、`ann_return_3y_pct`、`cum_return_3y_pct`、`peer_ranks: dict[月數, 百分位]`（0=最強、1=最弱） |
| **單位** | `inception_years` **年**；兩個 return **%**；`peer_ranks` **百分位（0~1 比例，非 %）** |
| **門檻常數** | `shared/dividend_station_thresholds.py`：`MIN_INCEPTION_YEARS=3.0` / `MIN_ANN_RETURN_3Y_PCT=7.0` / `MIN_CUM_RETURN_3Y_PCT=21.0` / `PEER_TOP_FRACTION=1/3` / `PEER_WINDOWS_MONTHS=(3,6,12)` / `PEER_MIN_GROUP_SIZE=3` |
| **判定規則** | `inception_ok = None if inception_years is None else (inception_years >= 3.0)`<br>`return_ok = None if (兩個 return 皆 None) else ((ann >= 7.0) or (cum >= 21.0))`<br>`peer_ok = None; if peer_ranks and all(peer_ranks.get(m) is not None for m in (3,6,12)): peer_ok = all(v <= 1/3 for v in vals)`<br>`passed = bool(inception_ok and return_ok and peer_ok)` |
| **缺值行為** | ⚠️ **兩層設計，要分開看**：<br>✅ **三個 `*_ok` 旗標是三態**（`True` / `False` / `None`），`detail` 字串顯示 `✅` / `❌` / **`❔`**，且 `miss_reasons` dict 逐項記原因<br>🔴 **但 `passed` 欄是兩態** —— `bool(None and ...)` → `False`。**「未判定」與「未通過」在 `passed` 欄同形**（docstring 自陳「任一不可判定 → passed=False（§1 不足不放行）」＝**刻意 fail-closed**）<br>⇒ 消費端**只讀 `passed` 就分不出** ❔ 與 ❌；要分必須讀 `detail` / `miss_reasons` |
| **缺值原因指派** | `inception_ok is None` → `MISS_NO_INPUT`（上游沒給成立日）<br>`return_ok is None` → `MISS_NOT_ENOUGH`（日線不足 3 年）<br>`peer_ok is None` → `MISS_NOT_ENOUGH`（**檔內自陳這是取捨**：主因是同類 ETF < 3 檔，少數是抓取失敗；L2 手上只有一個 dict 分不出，選 `NOT_ENOUGH` 因為 `NO_INPUT` 的文案「可以重跑一次」對主因是**錯的指引**。**已知代價**：少數真抓取失敗會被標成資料不足） |

---

## 4. 評分類

### 4.1 個股健康評分（6 因子，0~100）— 🔴 **缺值直接變 0 分**

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面「🏥 A. 個股健康度評分（0~100）」／程式 `src/compute/scoring/scoring_helpers.py:calc_health_score` |
| **算式** | `score = Σ(各因子得分)`，**上限 `min(score, 100)`**。**分母恆為 100，不隨缺項調整。** |
| **輸入** | `df`（日線，需 `MA20`/`MA100` 欄）、`rsi`、`ibs`、`vr`（量比）、`k_val`、`d_val`、`bb`（布林 dict） |
| **單位** | `score` **無量綱分數 0~100**；`rsi` / `ibs` 0~100 與 0~1；`vr` **倍**；`k/d` 0~100 |
| **合理範圍** | [0, 100]（`CLAUDE.md §3.2`「健康評分 [0,100]」）。實作以 `min(score,100)` 保證上界；下界由 `score=0` 起算保證 |
| **等第門檻** | `shared/health_thresholds.py:HEALTH_GRADE_A_MIN=80` / `HEALTH_GRADE_B_MIN=50` |

**評分表（滿分 100 = 30+20+15+10+15+10）**

| 因子 | 滿分 | 條件 → 得分 | 門檻出處 |
|---|---|---|---|
| **趨勢** | 30 | `price > ma20 > ma100` → 30（多頭排列）<br>`price > ma100 and price > ma20` → 18（多箱整理）<br>`price > ma20 and price < ma100` → 10（短線反彈）<br>`price < ma20 and price > ma100` → 8（整理中）<br>`else` → 0（空頭排列）<br>🔴 **`ma20` 或 `ma100` 缺 → +15（「無MA數據」）** | 🔴 全部 inline |
| **RSI** | 20 | `50 <= rsi <= 70` → 20<br>`40 <= rsi < 50` → 12<br>`30 <= rsi < 40` → 8<br>`rsi < 30` → 14（超賣反彈機會）<br>`rsi > 70` → 8 | ✅ `signal_thresholds:RSI_STRONG_LOW=50.0` / `RSI_NEUTRAL_WEAK_LOW=40.0`；`config:RSI_OVERBOUGHT=70` / `RSI_OVERSOLD=30`。🔴 得分 20/12/8/14/8 inline |
| **量比** | 15 | `vr > 3.0` → 12（主力介入）<br>`1.5 <= vr <= 3.0` → 15（異常放量）<br>`1.0 <= vr < 1.5` → 10<br>`0.5 <= vr < 1.0` → 5<br>`else` → 2 | ✅ `signal_thresholds:VOLUME_RATIO_SURGE_HIGH=3.0` / `SURGE=1.5` / `MILD=1.0` / `DRY=0.5` |
| **IBS** | 10 | `ibs <= 0.2` → 10<br>`ibs >= 0.8` → 2<br>`else` → 6 | ✅ `signal_thresholds:IBS_OVERSOLD_THRESHOLD=0.2` / `IBS_OVERBOUGHT_THRESHOLD=0.8` |
| **KD** | 15 | `k>d and k<80` → 15（黃金交叉）<br>`k>d and k>=80`：頂背離→5／高檔鈍化→15／其餘→8<br>`k<d and k>20` → 5（死亡交叉）<br>`else`（低檔死叉）：底背離→13／其餘→10 | ✅ `signal_thresholds:KD_OVERBOUGHT_LEVEL=80.0` / `KD_OVERSOLD_LEVEL=20.0`；背離旗標由 `tech_indicators.analyze_kd_state` 供給 |
| **布林** | 10 | `bb['near_upper']` → 8<br>`bb['price'] > bb['ma']` → 6<br>`bb['bw'] < bb['bw_mean'] × 0.7` → 9（帶寬極度收縮）<br>`else` → 3 | ✅ `signal_thresholds:BB_BW_SHRINK_WARN_RATIO=0.7` |

**等第映射** `health_grade(score)`：
```
if score >= 80: → ('優質優良', 綠, 'health-A', '🟢')
if score >= 50: → ('震盪盤整', 黃, 'health-B', '🟡')
else:           → ('弱勢危險', 紅, 'health-C', '🔴')
```

**🔴 缺值行為 — 客戶紅線的直接違反（本次實測，非推論）**

每個因子的 gate 都是 `if <輸入> is not None:`（或 `if df is not None and not df.empty:`）。
**輸入為 None → 整段 skip → 該因子貢獻 0 分，但 100 分的分母不變。**

實測（`scratchpad/_probe_ind.py`）：
```
calc_health_score(None, None, None, None, None, None, None)
  → score = 0   details = {}   grade = ('弱勢危險', '#ef4444', 'health-C', '🔴')

calc_health_score(df(有 close 無 MA 欄), None, None, None, None, None, None)
  → score = 15  details = {'趨勢': ('無MA數據', 15, 30)}   grade = ('弱勢危險', ..., '🔴')
```

⇒ **一檔什麼都沒抓到的股票，畫面顯示「健康度 0 分 · 🔴 弱勢危險」**，
與「真的技術面極弱」完全同形。**沒有 `None` / `⚪ 未評估` 這條路。**

⚠️ **對比組（同 repo 內的正確做法）**：`macro_helpers.calc_traffic_light` 的總經健康評分
**兩條腿都缺就回 `None`**，檔內原文「**不是 0 分（0 分會被判成最強利空）**」（§3.2）。
⇒ **同一個 repo、同一個叫「健康評分」的東西，兩種標準。**

⚠️ **第二個缺值問題**：`'無MA數據' → +15` 是**給一半的中性分**。
依 `CLAUDE.md §1`「任何填補必須(1)顯式呼叫(2)寫入 log(3)在輸出帶旗標」——
這裡 (1) 有（分支明寫）、(2) **無**、(3) **無**（`details['趨勢']` 的 tuple 與正常路徑同型，
消費端拿到 `('無MA數據', 15, 30)` 才知道，但 `score` 這個數字本身不帶旗標）。

⚠️ **下游影響**：`health_score` 是 §3.6 操作狀態燈、§3.7 綜合建議、
`scorability.summarize_candidates` 汰弱門檻（`health < HEALTH_GRADE_B_MIN` → eliminated）的輸入。
⇒ **抓取失敗的股票會被「汰弱」，理由寫成「健康度不足」。**
📌 ✅ 但 `scorability` 自己有防：`_as_float(r.get("健康度")) is None` → 進 `health_unknown_ids`，
「**既不算 kept 也不算 eliminated（不預設 100 也不預設 0）**」。
⇒ **防線在 `scorability`，不在 `calc_health_score`** —— 只要 `calc_health_score` 回的是 `0` 而不是 `None`，
`_as_float(0)` 會回 `0.0`（不是 None）⇒ **那道防線接不到這個案例。**（單組推導，未跑端到端反例。）

---

### 4.2 基本面四維評分 — 🔴 **實測發現量綱錯誤（本次新增，不在既有材料中）**

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面「💰 獲利 / 📈 成長 / 🎁 股利 / ⚖️ 估值」四張小卡（各 0~3 分）／程式 `src/compute/scoring/scoring_helpers.py:calc_fundamental_score` |
| **渲染** | `src/ui/render/app_render.py:render_health_score` 的 `fund_html` 區塊 —— 顯示**分數（0-3）+ 每項 check 的名稱 + ✓/✗**（⚠️ `checks` tuple 的第二元素 `cv`（值字串）**被 unpack 但沒有渲染**） |
| **呼叫端** | `src/ui/tabs/stock_sections/section_health_score.py`：`calc_fundamental_score(qtr2, yearly2, avg_div2)` |
| **單位** | 四維分數各 **0~3 分（整數）** |

#### 🔴 量綱錯誤：`avg_div` 收到的是「元/股」，函式當「%」用

**證據鏈（三段，全部實測）**

**① 呼叫端傳的是元。**
`section_health_score.py` 檔內註解逐字寫：「直接餵已在手的 **avg_div2（元）**＋ yearly2（近 5 年配息）」。
上游 `src/data/stock/app_stock_fetchers.py`：
```python
ddf['cash'] = pd.to_numeric(ddf[cash_col], errors='coerce').fillna(0)
yr = ddf.groupby('year')['cash'].sum().reset_index().tail(5)
avg_div = float(yr['cash'].mean()) if len(yr) > 0 else 0
```
⇒ `avg_div` ＝ **近 5 個日曆年度、每年現金股利（元/股）加總後取算術平均** ＝ **元/股**。
（`section_357_valuation` / `v5_modules` 都正確當元用：`avg_div ÷ YIELD_HIGH_DEC` → 分界價。）

**② 函式內部當百分比用。**
```python
# 股利維度
if avg_div and avg_div > 0:
    ok = avg_div >= 4
    result['dividend']['score'] += 2 if avg_div >= 4 else (1 if avg_div >= 2 else 0)
    result['dividend']['checks'].append(('平均殖利率', f'{avg_div:.1f}%', ok))   # ← 元，印成 %
# 估值維度
if avg_div and avg_div > 0:
    if   avg_div >= YIELD_HIGH: sc, lb = 3, '便宜區 >7%'    # YIELD_HIGH = 7.0（%）
    elif avg_div >= YIELD_MID:  sc, lb = 2, '合理 5~7%'
    elif avg_div >= YIELD_LOW:  sc, lb = 1, '合理 3~5%'
    else:                       sc, lb = 0, '偏貴 <3%'
```
⇒ check 名稱叫「**平均殖利率**」、值印成「`18.0%`」、門檻拿 `YIELD_HIGH/MID/LOW`（**百分比常數**）比。
⇒ **`price` 根本不是這個函式的輸入** —— 估值分完全與股價無關。

**③ 實測反例（`scratchpad/_probe_unit.py`）**

| 情境 | 真實殖利率 | 🎁 股利分 | ⚖️ 估值分 | 估值 check 顯示 |
|---|---|---|---|---|
| `avg_div=18.0` 元、現價 1000 元 | **1.80%** | 2/3 ✓ | **3/3 ✓** | `18.0% 便宜區 >7%` |
| `avg_div=2.0` 元、現價 20 元 | **10.00%** | 1/3 ✗ | **0/3 ✗** | `2.0% 偏貴 <3%` |
| `avg_div=7.5` 元、現價 300 元 | **2.50%** | 2/3 ✓ | **3/3 ✓** | `7.5% 便宜區 >7%` |

⇒ **兩者完全顛倒**：真實殖利率 1.8% 的拿滿分「便宜區」，真實殖利率 10% 的拿 0 分「偏貴」。
⇒ 估值分實際上是 **`avg_div_twd` 的單調函式**，與便宜貴無關。

**畫面上會看到什麼（precision：不要過度宣稱）**
- ✅ **會看到**：「⚖️ 估值 **3**」+「✓ 357殖利率估值」、「🎁 股利 **2**」+「✓ 平均殖利率」
- ❌ **不會看到**那個 `18.0%` 字串 —— `render_health_score` 的迴圈 `for cn, cv, cp in ...` **只渲染 `cn` 與 `cp`，不渲染 `cv`**
⇒ **錯的是分數與 ✓/✗，不是一個印出來的數字。**（這反而更難被使用者發現。）

**📌 這是同一個 repo 已經修過一次的同型 bug**（`section_health_score.py:406` 檔內註解逐字）：
> 舊碼第 3 個位置參數傳 `avg_div2 / max(price2, 1)` —— 那是**殖利率**，但函式契約要的是**配發率**，
> 函式內再 `eps × payout / price` ⇒ **除以股價兩次** ⇒ 2330 實機顯示 0.01%（真值 0.59%），並被判成「🔴 超貴」。

⇒ v19.179 B1-b 修好了 `calc_dividend_yield_357`，**但同一個 `avg_div2` 餵給 `calc_fundamental_score` 這條沒修**。
⚠️ **本項為單組實測 + 單組推導，未經第二組複驗**（`§-2 規則 6`）。
⚠️ **本檔不提修法**（唯讀階段，且修法屬行為變更需走 `CLAUDE.md §8` 流程）。

#### 其他缺值問題（同一支函式）

| 位置 | 原碼 | 問題 |
|---|---|---|
| 獲利 · 近4季EPS | `es = to_numeric(qtr_df[eps_c].tail(4)).dropna()`<br>`sm = float(es.sum()) if len(es)>=2 else 0`<br>`ok = sm >= 1` | 🔴 **標籤寫「近4季EPS」，門檻卻是 `len(es)>=2`** ⇒ 只有 2 季也照樣加總並標成「近 4 季」<br>🔴 **`else 0`** ⇒ 季數 < 2 時 sum 記為 0 → `ok = False` ⇒ **缺資料被記成「不及格 ✗」** |
| 獲利 · 淨利率 / 營益率 | `ok = v is not None and v >= 5`（/ `>= 10`）<br>`checks.append((..., f'{v:.1f}%' if v else 'N/A', ok))` | 🔴 `v is None` → `ok=False` ⇒ **缺值記成 ✗ 不及格**（不是「未評估」）<br>🔴 **`if v` 不是 `if v is not None`** ⇒ **真實的 `0.0%` 淨利率會顯示成 `'N/A'`**（一個真觀測被講成沒資料） |
| 成長 · 營收季增 / EPS年增 | `ok = v1 and v2 and v1>v2` | 🔴 同上，缺 → `ok=False` 記成 ✗；且 `v1 and v2` 用真值測試 ⇒ **`v=0.0` 會被當缺值** |
| 全函式 | `except Exception as _e: print(f'[calc_fundamental_score] {_e}')` | ⚠️ 例外後**回傳已累積的部分結果**（不是 raise、不是回 None）⇒ **半份計算被當完整結果用**，且無旗標 |
| 門檻 | `>= 1`（EPS）/ `>= 5`（淨利率）/ `>= 10`（營益率）/ `>= 20`（毛利率）/ `>= 4`、`>= 2`（股利） | 🔴 **全部 inline**，未走 SSOT（`CLAUDE.md §3.3` 記「❌ 標記 0 項」—— 該宣稱與本處不符，見 §9） |

**🔴 標籤矛盾**：`avg_div` 落在 `[3, 5)` 時本函式標「**合理 3~5%**」，
而 `classify_stock_357_price` 對同一區間回 `'dear'` → `section_357_valuation` 顯示「**🔴昂貴價**」。
⇒ **同一個殖利率帶，同一個畫面上，一張卡說「合理」、另一張卡說「昂貴」。**

---

### 4.3 財報體檢分數與等第

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面「財報體檢」總評／程式 `src/services/financial_health_engine.py:no_ai_overall_verdict` |
| **算式** | `valid = [(n,s) for n,s in checks if s != "N/A"]`（11 項 checks）<br>`total_pts = Σ _pts(s) for s in valid`<br>`max_pts = len(valid) × 2`<br>`score_pct = round(total_pts ÷ max_pts × 100)` if `max_pts > 0` else 50<br>`pass_items = [n for n,s in valid if _pts(s) >= 2]`<br>`fail_items = [n for n,s in valid if _pts(s) < 0]` |
| **輸入** | 六大模組的 `Status` 欄（survival / profitability / financial_structure / solvency / advanced_diagnostic） |
| **單位** | `score_pct` **%（0~100）**；`total_pts` / `max_pts` **分** |
| **合理範圍** | `score_pct` [−100, 100]（`_pts` 最低 −2、最高 +2 ⇒ 理論下界 −100）。⚠️ **`CLAUDE.md §3.2` 未收此項**，且**沒有 assert 守住** |

**`_pts` 評分表**（`no_ai_overall_verdict._pts`）

| Status 字面 | 分 |
|---|---|
| `Pass` / `Good` / `Strong` | **+2** |
| `Acceptable` / `Exception_Pass` | **+1** |
| `Warning` / `Fail_Initial` / `Thin Profit` | **−1** |
| `Fail` | **−2** |
| **其他（含 `"N/A"`）** | **0**（`.get(str(s), 0)`） |

**11 項 checks**（名稱即畫面欄名）：
氣長 / 收現速度 / 100-100-10 / 毛利率 / 本業獲利 / ROE品質 / 負債比率 / 以長支長 / 流動比率 / 盈餘含金量 / 雙高危機

**等第決策樹（順序即優先序，前面命中就 return）**
```
# ── gate 1：整張表缺漏（2026-09-09 P0-B）──
if _stmt_gaps:                       # prof 或 fstr 掛了 Data_Gap 旗標
    → grade='N/A', score_pct=None, headline='⬜ 只拿到一半的財報，本輪不評等'
# ── gate 2：一項都算不出來 ──
if not valid:
    → grade='N/A', score_pct=None, headline='⬜ 財報資料不足，本輪不評等'
# ── 分級樹 ──
if is_dying or len(fail_items) >= 4: → 'F'  🔴 高危企業
elif len(fail_items) >= 2:           → 'C'  🟡 有明顯改善空間
elif len(fail_items) == 1:           → 'B+' 🟡 大致穩健
elif is_cashcow ('A+' in Business_DNA): → 'A+' 🟢 印鈔機
elif score_pct >= 70:                → 'A'  🟢 優質企業
else:                                → 'B'  🔵 財務穩定，中規中矩
# ── 揭露（不改等第）──
if _skipped: comment += f'⚠️ 本輪有 {len(_skipped)} 項未評估（…）—— 缺資料不計分，等級只反映算得出來的那幾項。'
```
🔴 **門檻 `>= 4` / `>= 2` / `== 1` / `>= 70` 全部 inline**（未走 SSOT）。

**缺值行為**
- ✅ **整張損益表 / 資產負債表缺 → 不評等**（`grade='N/A'`、`score_pct=None`），
  comment 原文「**本站不拿 0 頂替，也不會用剩下半份財報發一張體質等級**」
- ✅ **單格缺 → `_pts=0`**，不進 `pass_items` 也不進 `fail_items`，並在 comment 揭露「本輪有 N 項未評估」
- ✅ `fin_data` 含 `{"error": ...}` → `_FAIL_SAFE` 攔截
- 🔴 **`score_pct = ... else 50` 仍在**（第 1110 行）—— 但實測為**死碼**：
  `max_pts > 0` ⟺ `len(valid) > 0` ⟺ `valid` 為真，而 `if not valid:` 在其後 return `score_pct=None`
  ⇒ `else 50` 會被計算，但**永遠不會被輸出**。
  ⚠️ 同 `CLAUDE.md §-2` 的 `db4c139` 型態：**留著會讓下一個人以為「缺值會給 50 分」。**（單組推導。）

**⚠️ 樹本身的結構性弱點（檔內已識別並就地註明，但 **未修樹本身**；逐字引用）**
> 把「本業虧損」改成 N/A 之後，缺營收那一檔的 `fail_items` 會變空，於是同一份**半份財報**
> 從「體質 C 級」翻成「🟢 印鈔機！A+ 型企業」—— **假的正結論跟假的負結論一樣危險，而且更容易讓人買進。**
> … 把那兩格改成 N/A 之後**還是 A+**（實測），因為 `fail_items` 一樣是空的：
> **少評幾項不會讓等級變差，只會讓它變好。** 所以 gate 必須設在「整張表在不在」，不能只設在單格。

⇒ 解法是**在樹之前加 gate**，不是修樹。
⇒ **單格缺漏（不足以觸發整張表 gate）仍會讓等級偏好。** 這是**仍未解**的殘留風險。
⚠️ 本項為 `S1-2 §2.3` 的推論（U-10，自標「未跑反例驗證」），**本檔亦未跑反例**（見 §9）。

---

### 4.4 獲利能力 5 大指標（已知問題 #6）

**L3 產生端**：`src/services/financial_health_engine.py:_no_ai_profitability` → `Profitability_Module`

| # | 指標 | 算式 | 單位 | 門檻常數 | 判定規則 | 缺值行為 |
|---|---|---|---|---|---|---|
| ① | **毛利率** | 欄位自帶（**不經 rev 換算**） | % | `shared/financial_health_thresholds.py:FH_GROSS_MARGIN_GOOD_PCT=40.0` | `if gm_state==FIELD_ABSENT or (gm_state==FIELD_ZERO and _gap): Value=NA_…, Status='N/A'`<br>`elif gm >= 40.0: Status='Good'`<br>`else: Status='Average'` | ✅ `"N/A (損益表缺漏)"` / `"N/A (欄位缺漏)"`。檔內原文：「**rev 在手上而 gm 真的是 0（毛利＝成本）是一個真實觀測 → 照實顯示**」 |
| ② | **營業利益率** | `om = round(oi ÷ rev × 100, 1)` | % | 無門檻常數（判 `om > 0`） | `if _gap: 'N/A'`<br>`elif oi_state != FIELD_VALUE: 'N/A'`（領域規則）<br>`elif _bad_om: 'N/A (rev 單位異常)'`<br>`else: Core_Business_Profitable = 'Yes' if om > 0 else 'No'` | ✅ 三態。⚠️ 欄名是 **`Core_Business_Profitable`**（Yes/No/N/A），**不是 `Status`** |
| ③ | **安全邊際** | `mos = round(oi ÷ gp × 100, 1)` | % | `FH_MOS_STRONG_PCT=60.0` | `if _gap or oi_state != FIELD_VALUE or _bad_om: 'N/A'`<br>`elif gp <= 0: Value='N/A (毛利非正，安全邊際無意義)'`<br>`elif mos >= 60.0: 'Strong'`<br>`elif mos >= 0: 'Acceptable'`<br>`else: 'Weak'` | ✅ `gp <= 0` 專屬 sentinel。檔內原文：「原本回 0 會落在 `mos >= 0` 那一階 → **拿缺值換到一張及格證**」 |
| ④ | **稅後淨利率** | `nm = round(ni ÷ rev × 100, 1)` | % | `FH_NET_MARGIN_PASS_PCT=10.0` | `if _gap or ni_state != FIELD_VALUE or _bad_nm: 'N/A'`<br>`elif nm >= 10.0: 'Pass'`<br>`elif nm >= 0: 'Thin Profit'`<br>`else: 'Loss'` | ✅ 檔內原文：「**真的虧損（ni < 0）是 FIELD_VALUE，照常判 "Loss"** —— 這條只擋『讀到 0』，不擋負數」 |
| ⑤ | **ROE** | `roe = round((ni × 4) ÷ eq × 100, 1)`　**（單季 NI × 4 年化）** | % | `FH_ROE_LEVERAGE_CHECK_PCT=15.0`<br>`FH_DUPONT_LEVERAGE_DEBT_PCT=65.0` | `if _gap or ni_state != FIELD_VALUE: Value='N/A (…)', Leverage_Warning='None'`<br>`elif eq_state != FIELD_VALUE or eq <= 0: Value='N/A (股東權益缺漏)', Leverage_Warning='None'`<br>`else: Leverage_Warning = '槓桿膨脹警報' if (roe > 15.0 and debt > 65.0) else 'None'` | ✅ 缺值走 `Value`，`Leverage_Warning` **一律留 'None'**（檔內原文：在那裡塞第三個值「會把『沒有資料』變成『有警報』，**等於用 §1 的鏡像失效模式修 §1**」） |

**🔴 已知問題 #6 — 逐項複驗結果**

1. ✅ **客戶說「三率穿透實際是 5 個指標」— 正確。**
   L3 的 `Profitability_Module` 確實吐 5 個 slot；畫面標題也寫「**獲利能力診斷（5大指標）**」。
   ⚠️ 但 IA v2 的 `src/ui/views/page_inspect.py:load_profitability` **只取 3 格**
   （毛利率 / 營業利益率 / 安全邊際），docstring 原文「💰 獲利能力**三格**」。
   ⇒ **同一份 L3 產出，舊分頁 5 格、新頁 3 格。**

2. ✅ **客戶說「ROE 那格程式回的是槓桿警語不是判決」— 正確。**
   `"ROE": {"Value": roe_val, "Leverage_Warning": roe_warn}` —— **沒有 `Status` 欄**。
   其餘四格都有判決欄（`Status` ×3、`Core_Business_Profitable` ×1）。
   ⇒ UI 只好**自己從 `Value` 字串反解出數字再判正負**：
   ```python
   try:    _roe_f_num = float(str(_roe_f.get('Value','0')).replace('%','').strip())
   except (ValueError, AttributeError): _roe_f_num = None
   ```

3. ⚠️ **客戶說「淨利率與 ROE 沒有中文判讀語」— 需要拆開講。**
   - **淨利率：✅ 成立。** 兩個舊分頁都寫 `_nm_f_l = MISSING_LABEL if _nm_f_na else _nm_f_s`
     ⇒ **直接把英文 Status 原文印在畫面上**：`Pass` / `Thin Profit` / `Loss`。
   - **ROE：⚠️ 不完全成立。** UI **有**中文語：`⚠️ 高槓桿` / `✅ 真實獲利` / `❌ 本業虧損`。
     問題不是「沒有中文」，而是 **(a) 那是 UI 自己合成的、L3 沒給**；
     **(b) `❌ 本業虧損` 這句對 ROE 是語意錯的** —— ROE ≤ 0 代表**稅後淨利為負**，
     不是「本業虧損」（本業＝營業利益，是 ② 那一格的事）。**一家本業賺錢、業外大虧的公司會被標成「本業虧損」。**

**🔴 三個渲染端、三套標籤（本次新增發現）**

| Status | `page_inspect.py`（IA v2） | `section_financial_health.py`（組合頁） | `tab_stock.py`（個股頁） |
|---|---|---|---|
| 毛利率 `Good` | `好生意` | `好生意` | `好生意` |
| 毛利率 `Average` | **`普通`** | **`辛苦`** | **`辛苦生意`** |
| 營益率 `Yes` | `本業獲利` | `本業獲利✅` | `本業獲利✅` |
| 安全邊際 `Strong` | `抗震極強` | `抗震極強` | `抗震極強✅` |
| 安全邊際 `Acceptable` | **`抗震尚可`** | **`費用偏高`** | **`費用待改善`** |
| 安全邊際 `Weak` | **`抗震不足`** | **`費用偏高`**（與 Acceptable 同字） | **`費用待改善`**（同上） |
| 淨利率 | （不顯示） | 英文原文 | 英文原文 |
| ROE | （不顯示） | `⚠️ 高槓桿` / `✅ 真實獲利` / `❌ 本業虧損` | `⚠️ 高槓桿驅動` / `✅ 真實獲利` / `❌ 本業虧損` |

⚠️ **兩個舊分頁把 `Acceptable` 與 `Weak` 合併成同一句** ⇒ 三階門檻在畫面上只剩兩階。

**🔴 `tab_stock.py`（🔬 個股分頁）完全沒有缺值 gate —— PR #673 登記但未修，本次複驗仍在**

```python
_gm2_ok  = _gm2.get('Status','') == 'Good'                              # N/A → False
_om2_ok  = _om2.get('Core_Business_Profitable','No') == 'Yes'           # N/A → False
_mos2_ok = _mos2.get('Status','') == 'Strong'                           # N/A → False
```
⇒ `Value` 顯示 `"N/A (損益表缺漏)"`，但同一張卡的**底色是紅的、標籤寫「本業虧損❌」**。
⇒ **數字誠實、結論說謊。**
（`section_financial_health.py` 與 `page_inspect.py` **都有** `_is_missing` / `_MISSING_STATUSES` gate ✅ ——
**只有 `tab_stock.py` 這一份沒有。**）

---

### 4.5 ETF 綜合分 / 星等（7 維加權）

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面「綜合分」/「星等 ⭐」／程式 `src/compute/etf/etf_scoring_helpers.py:compute_etf_composite_score` |
| **算式** | 每維先線性標準化：`_norm(v, hi, lo) = clip((v − lo) ÷ (hi − lo), 0, 1)`<br>`composite = Σ(wᵢ · sᵢ) ÷ Σwᵢ`，**i ∈ {sᵢ is not None}**（缺項 **rescale 有效權重** ✅） |
| **單位** | `composite` **0~1 無量綱**；`stars` **1~5 顆** |
| **合理範圍** | `composite` ∈ [0, 1]（由 `_norm` 的 clip + 加權平均保證） |

**權重與標準化端點**（`etf_scoring_helpers.py:_WEIGHTS` / `_NORM`，🔴 **兩個 dict 皆 inline 在 L2，未走 L0 SSOT**）

| 維度 | 權重 | 滿分值 hi | 零分值 lo | 單位 |
|---|---|---|---|---|
| `total_ret_1y` | 0.25 | 10.0 | −5.0 | % |
| `cagr_3y` | 0.20 | 8.0 | 0.0 | % |
| `sharpe` | 0.15 | 1.0 | 0.2 | 無量綱 |
| `mdd` | 0.15 | −10.0 | −30.0 | %（負值） |
| `expense_ratio` | 0.12 | 0.003 | 0.015 | **比例（非 %）** |
| `aum` | 0.08 | 10.0 | 9.0 | **log10(元)** |
| `div_yield_cv` | 0.05 | （借用 `etf_quality` 的 `yield_cv` 子分，已是 0~1） | — | 無量綱 |

**星等門檻**（✅ `shared/signal_thresholds.py`）：
```
if   composite >= ETF_RATING_EXCELLENT_MIN (0.80): stars = 5
elif composite >= ETF_RATING_VERY_GOOD_MIN (0.65): stars = 4
elif composite >= ETF_RATING_GOOD_MIN      (0.50): stars = 3
elif composite >= ETF_RATING_FAIR_MIN      (0.35): stars = 2
else:                                              stars = 1
```

**缺值行為**
- ✅ **設計是對的**：`_norm(None, ...) → None` → 該維**不進分子也不進分母** → 有效權重 rescale
- ✅ 全部維度皆缺 → `_valid_w <= 0` → `return None, None`（不給分、不給星）
- 🔴 **但有一條旁路把它繞過** —— 見 §5.1（`calc_sharpe` 回 `0.0` 而非 `None`）

---

### 4.6 選股網綜合分與涵蓋門檻（已知問題 #5）

| 欄 | 內容 |
|---|---|
| **指標名** | 選股網「綜合分」欄／程式 `src/services/fundamental_screener_service.py`（`_rank_and_merge` 區段；對外入口 `get_ranked_picks`） |
| **算式** | 每個因子先轉**全市場百分位** `_percentile_scores(ids, value_map, higher_better)`<br>`_present = [各因子百分位 for 該股有資料的因子]`<br>`composite = round(mean(_present), 1)` **只在通過涵蓋門檻時** |
| **輸入** | 5 個因子：`pe_low`（估值分）/ `eps_high`（EPS分）/ `shortage`（缺貨分）/ `rs_leader`（RS分）/ `trend`（跨季分） |
| **單位** | 各因子分與綜合分皆 **百分位 0~100** |
| **門檻常數** | ✅ `shared/signal_thresholds.py:SCREENER_MIN_FACTOR_COVERAGE_RATIO = 0.5` |

**判定規則（涵蓋門檻，原碼）**
```
_effective_n = sum(1 for f in factors if _col_scores[f])   # 至少 1 檔有值的「勾選因子」數
_min_present = 0.5 × _effective_n
for i in ids:
    _present = [_col_scores[f][i] for f in factors if i in _col_scores[f]]
    if _present and len(_present) > _min_present:          # ← 嚴格 >
        composite[i] = round(sum(_present)/len(_present), 1)
    else:
        composite[i] = None
ranked = sorted(ids, key=lambda i: (composite[i] is None, -(composite[i] or 0)))
if drop_unscored:
    ranked = [i for i in ranked if composite[i] is not None]   # ← 整檔移除
```

**涵蓋門檻換算表**（嚴格 `>`，SSOT docstring 原文「3 勾需 ≥2、2 勾需 2、1 勾需 1」）

| 有效因子數 `_effective_n` | `_min_present` | 該股需要幾個因子有資料才進榜 |
|---|---|---|
| 5 | 2.5 | **≥ 3** |
| 4 | 2.0 | **≥ 3** |
| 3 | 1.5 | **≥ 2** |
| 2 | 1.0 | **= 2** |
| 1 | 0.5 | **= 1** |

**🔴 已知問題 #5 — 複驗確認並補強**

✅ 客戶說「缺 PE 會讓整檔**出局**，不是排後面」— **正確，且我確認了是哪一條路造成的**：
`get_ranked_picks`（`fundamental_screener_service.py`，檔內註解自陳是「**畫面 / 每月凍結 / MCP / 推播**四處同源」的入口）
**明確傳 `drop_unscored=True`** ⇒ `composite is None` 的檔**直接從 list 移除**。
（函式簽章預設是 `drop_unscored: bool = False`（排最後）—— **但 production 入口覆寫成 True**。）

⇒ 5 個因子全勾時，一檔股票缺 PE 且再缺任一因子（例如未進缺貨深掃的 50 檔）
→ 只剩 3 個 → 剛好 `3 > 2.5` 過關；**再缺一個就 `2 > 2.5` 為 False → 整檔消失**。

**✅ 可觀測性做得好的部分（三段 note，全部走 SSOT 插值）**
1. `（N 檔因「勾選因子涵蓋未過半」未列入綜合排序;需 >50% 勾選因子有資料…）`
2. `（因子實際覆蓋:估值分 A/B、缺貨分 C/D …—— 未覆蓋到的個股該因子不計分，**不是 0 分**。）`
3. 各因子欄缺料 → `out[欄] = None` ⇒ **畫面顯示空白，非 0**

**🔴 但仍有一個缺口**：被 `drop_unscored` 移除的檔，
**使用者在榜單上完全看不到它們**（只看得到一行「N 檔未列入」的數量）。
⇒ 「這檔沒上榜」與「這檔被資料缺口擋掉」在畫面上**無法分辨到個股層級**。

---

## 5. 風險與部位

### 5.1 夏普值 Sharpe — **三份實作，缺值行為不一致**

| # | 位置 | 算式 | 週期 | 報酬定義 | rf 來源 |
|---|---|---|---|---|---|
| **S-1** | `src/compute/etf/etf_calc.py:calc_sharpe` | `(mean(r)·252·100 − rf_pct) ÷ (std(r)·√252·100)` | **日** | 簡單報酬 `pct_change()` | 模組級 `_RF_PCT`（L3 注入的即時 FEDFUNDS；未注入時 fallback `ETF_SHARPE_RF_FALLBACK_PCT=5.33`） |
| **S-2** | `src/compute/etf/dividend_station.py:sharpe_weekly` | `(mean(r_w) − rf_pct/100/52) ÷ std(r_w, ddof=1) × √52` | **週** | 簡單報酬 | 由 caller 注入 `rf_pct` |
| **S-3** | 基金站（**不在本 repo**） | — | — | — | — |

**單位**：`sharpe` **無量綱比值**；`rf_pct` **年化 %**。
**門檻常數**：`shared/signal_thresholds.py:TRADING_DAYS_PER_YEAR=252` / `ETF_SHARPE_RF_FALLBACK_PCT=5.33`；
`shared/dividend_station_thresholds.py:SHARPE_NEG_THRESHOLD=0.0` / `MA_QUARTER_WEEKS=13`。
**合理範圍**：`CLAUDE.md §3.2` 未收；無 sanity 檢查。

#### 🔴 S-1 的缺值行為違反客戶紅線（本次實測）

```python
def calc_sharpe(df, rf=None) -> float:      # ← 回傳型別標註就是 float，不是 float|None
    if rf is None: rf = _RF_PCT
    try:
        ret = df['Close'].pct_change().dropna()
        if len(ret) < 20:  return 0.0                       # 🔴
        ...
        return round((ann_ret - rf) / ann_vol, 2) if ann_vol > 0 else 0.0   # 🔴
    except Exception as _e:
        print(f'[calc_sharpe] swallow: ...', file=sys.stderr)
        return 0.0                                          # 🔴（函式內自稱 swallow）
```
**三條路全部回 `0.0`，不是 `None`。** 而 Sharpe = 0 是一個**有意義的觀測**（報酬恰等於無風險利率），不是缺值。

實測：`calc_sharpe(df_10列)` → `0.0`，型別 `float`。

#### ✅ **S1-2 的 U-3 本次已追到底 —— 結論：0.0 會直接污染星等**

`build_etf_score_row` 寫 `_r['sharpe'] = calc_sharpe(df)` ⇒ **0.0 進 row**。
`compute_etf_composite_score` 的 rescale 機制**只認 `None`**（`_norm(None) → None` 才會被排除）。

實測（`_probe_ind.py`，其餘六維固定）：

| `row['sharpe']` | `_norm(v, hi=1.0, lo=0.2)` | composite | 星等 |
|---|---|---|---|
| **`0.0`**（資料不足的實際回傳） | **`0.0`**（進分母，權重 0.15） | **0.563** | **3 ★** |
| `None`（正確的缺值表達） | `None`（排除，rescale） | **0.669** | **4 ★** |

⇒ **一檔上市未滿 20 個交易日的 ETF，會因為「Sharpe 算不出來」被扣掉整整一顆星**，
而畫面上它與「Sharpe 真的很差」的 ETF 完全同形。
⇒ 星等再往下餵 `etf_recommendation`（§2.7）的 `composite` 門檻 `0.65` / `0.35`
⇒ **0.669（4★「留下」）↔ 0.563（3★「觀察」）剛好跨過 `KEEP_COMPOSITE_MIN=0.65`。**
⇒ **「留下」與「觀察」的差別，可以只是一檔 ETF 太年輕。**

⚠️ **這是設計良好的 rescale 機制被一個 `return 0.0` 從旁路繞過的案例** ——
`compute_etf_composite_score` 本身**沒有錯**（§4.5 ✅），錯在上游用 0 表達缺值。
⚠️ **單組實測 + 單組推導，未經第二組複驗。**

#### 📌 S-1 與 S-2 的其他不一致

| 軸 | S-1 | S-2 |
|---|---|---|
| 年化 | ×252（日） | ×√52（**週**） |
| σ 自由度 | `ret.std()`（pandas 預設 ddof=1） | 明寫 `ddof=1` |
| 樣本門檻 | `len(ret) < 20` | `len(weekly) < 13+1` 且 `len(rets) < 13` |
| 缺值回傳 | 🔴 `0.0` | ✅ `None` |
| σ≈0 | 🔴 `0.0` | ✅ `None`（`math.isclose(sd, 0, abs_tol=FLOAT_ABS_TOL)`） |
| 消費端 | ETF 綜合分 / 星等 / 多檔比較表 | 存股健檢 **B 燈** |

⇒ **同一檔 ETF 在「多檔比較」與「存股健檢 B」會看到兩個不同的 Sharpe**，而且缺值時一個給 0、一個給 ⚪。

---

### 5.2 最大回撤 MDD

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面「最大回撤 / MDD」／程式 `src/compute/etf/etf_calc.py:calc_mdd` |
| **算式** | `MDD% = min( (close − cummax(close)) ÷ cummax(close) × 100 )` |
| **輸入** | 日線 `Close` 序列 |
| **單位** | **%（恆 ≤ 0）** |
| **門檻常數** | 投組層級：`src/config/config.py:MAX_PORTFOLIO_DRAWDOWN = 0.15`（**比例**，非 %）→ `risk_control.update_drawdown` 對照<br>ETF 評分標準化端點：`etf_scoring_helpers.py:_NORM['mdd'] = (-10.0, -30.0)`（🔴 inline） |
| **判定規則** | 評分用（§4.5）：`_norm(mdd, hi=-10.0, lo=-30.0)` ⇒ `mdd >= -10%` → 1.0 分；`mdd <= -30%` → 0.0 分；線性內插 |
| **缺值行為** | ✅ `calc_mdd` 任何例外 → `return None` + stderr log。缺 `Close` 欄 → 落 except → `None` |
| **合理範圍** | 理論 [−100, 0]。`CLAUDE.md §3.2` 未收；**無 assert** |
| **量綱陷阱** | 🔴 **`MAX_PORTFOLIO_DRAWDOWN = 0.15` 是比例，`calc_mdd` 回的是百分比（−15.0）** —— 兩者差 100×。<br>比較時必須換算，`config.py` 的常數名**沒有編碼單位**（違 `CLAUDE.md §4.1` 命名規範） |

---

### 5.3 停損（三套門檻並存）

| 名稱 | 算式 | 單位 | 門檻常數 | 缺值行為 |
|---|---|---|---|---|
| **ATR 停損** | `Stop = Entry − multiplier × ATR14` | 元 | `src/compute/risk/risk_control.py:ATR_MULTIPLIER = 1.5`（🔴 **inline 在 L2，註解自陳「固定值，不對外暴露設定」**） | ⚠️ **刻意降級**：`df is None or len(df) < 14` → 回 `{'stop_loss': entry×(1 − ATR_STOP_FIXED_PCT/100), 'atr': None, 'method': 'fixed_8pct', 'error': None}`。<br>✅ `error=None` 表示**非異常路徑**；計算拋例外時 `error` 帶型別+訊息 ⇒ **兩種降級可分辨** |
| **固定停損（備援）** | `Stop = Entry × (1 − pct/100)` | 元 | `shared/signal_thresholds.py:ATR_STOP_FIXED_PCT = 8.0` / `STOP_LOSS_DEFAULT_PCT = 8.0` / `HARD_STOP_LOSS_PCT = 7.0`<br>另有 `src/config/config.py:STOP_LOSS_PCT = 0.08`（🔴 **比例版，與上面三個 % 版並存**） | — |
| **投組回撤煞車** | `drawdown vs MAX_PORTFOLIO_DRAWDOWN` | 比例 | `config.py:MAX_PORTFOLIO_DRAWDOWN = 0.15` | — |

🔴 **量綱雙胞胎**：`STOP_LOSS_DEFAULT_PCT = 8.0`（%）與 `STOP_LOSS_PCT = 0.08`（比例）
是**兩個獨立宣告的數字**（不像 `YIELD_HIGH_DEC` 是推導出來的）⇒ **會漂移**。
⚠️ 且 `HARD_STOP_LOSS_PCT = 7.0` 與 `STOP_LOSS_DEFAULT_PCT = 8.0` **不同值** ——
畫面 help 文字同時列出「`-7%／-8%`」兩條線（`section_when_buy_sell.py`），語意差別本次未追（見 §9）。

**唯一由使用者輸入的參數（全站唯一一處）**：
`src/ui/tabs/stock_sections/section_when_buy_sell.py` 的
`st.number_input('💰 你的總資金（元）— 填了才會算「建議買幾張 + 真 ATR 停損」', min_value=0, step=100000, key='_pos_capital')`
✅ 該處註解原文：「**資金因人而異 → UI 輸入 + session 記住，不寫死常數（§1 不造假假設）**」。
⇒ **這是本站唯一一個承認「這個數字只有使用者知道」的地方**，其餘門檻一律內建（見 §5.7）。

---

### 5.4 持股水位油門

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面標題「建議持股區間」（**引用：現行 UI 字串**）／程式 `shared/position_throttle.py:compute_position_throttle`；**全站唯一入口** `src/services/allocation_service.py:get_allocation()` |
| **算式** | 無算式 —— 分段查表 + regime 否決 |
| **輸入** | `health`（總經健康分 0~100，§3.2）、`regime`（`'bull'/'neutral'/'caution'/'bear'`）、`defense`（bool） |
| **單位** | `health` **分**；`lo_pct`/`hi_pct`/`mid_pct` **%（持股比例百分比）** |
| **門檻常數** | `shared/position_throttle.py:THROTTLE_HEALTH_A=70` / `THROTTLE_HEALTH_B=50` / `THROTTLE_HEALTH_DEF=35`；<br>`THROTTLE_TIERS`（持股帶）；`THROTTLE_VETO_REGIMES={'bear','caution'}`；`_DEFENSE_HI_PCT=20` |
| **合理範圍** | 輸入先 clamp：`_h = max(0.0, min(100.0, float(health)))` ✅ |

**評分表**（`THROTTLE_TIERS`，由上而下第一個命中就 break）

| `health ≥` | 持股下界 % | 持股上界 % | 姿態 | icon |
|---|---|---|---|---|
| 70 | 80 | 100 | `積極` | 🟢 |
| 50 | 50 | 70 | `中性偏多` | 🟡 |
| 35 | 30 | 50 | `轉守` | 🟠 |
| 0 | 0 | 20 | `防禦` | 🔴 |

**regime 否決**：
```
if (defense or regime in {'bear','caution'}) and hi > 20:
    lo, hi, icon = 0, 20, '🔴';  posture = '防禦(總經否決)';  regime_capped = True
```

**缺值行為**：`health = None` → `allocation_service` / arbiter 回 `UNLOADED_VERDICT`（⬜ 總經未評估），
`src/ui/tabs/macro/section_state.py` 明文「**不渲染建議持股油門**」✅。
⚠️ 但 `compute_position_throttle` 本身**若真被傳 `None` 會在 `float(health)` 拋 `TypeError`**
（fail loud，符合 `CLAUDE.md §1`；但呼叫端必須先擋）。

**⚠️ 三個切點的證據等級不同（檔內自陳，逐字引用）**
- ✅ `DEF = 35` **真對齊** `HEALTH_DEFENSE_THRESHOLD`（同尺度）
- ⛔ `A = 70` **禁止**對齊 `HEALTH_GRADE_A_MIN(=80)` —— 後者是**個股六因子**尺度。
  檔內原文：照 80 切會讓「積極」帶在 2007-2026 的 **4,769 個交易日裡一次都不觸發**。
  現值 70 來自總經 health 自身分布的 **P90**（n=4,789，腿停用後 P90=70.5）
- ⚠️ `B = 50` 與 `HEALTH_GRADE_B_MIN(=50)` 是**數值巧合，不是有效背書**；屬**未校準手訂值**

**🔴 量綱陷阱（檔內明文警告，逐字）**：
> `config.py` 那三個常數（`EXPOSURE_BULL/NEUTRAL/BEAR`）存的是**比例** `0.80/0.50/0.20`，
> 此處是**百分比** `80/50/20`，**差 100×**。要引用請自行 ×100，**別直接 import 混用**。

⚠️ 同檔另一警告：「別把『持股 %』與『health 切點』搞混：**同樣出現 80/50**，
但左欄是 health(0-100 **分**)，右邊兩欄是持股比例(**%**)」。

---

### 5.5 集中度（客戶詞對應到兩個不同的東西）

#### (A) 投組產業集中度 — `src/compute/risk/concentration.py`

| 欄 | 內容 |
|---|---|
| **算式** | 設已分類股票共 M 檔、分屬 K 個產業、產業 i 有 n_i 檔：<br>`w_i = n_i ÷ M`（`Σ w_i = 1`）<br>`Top1 = max_i w_i`<br>`Top3 = Σ_{i ∈ top-3} w_i`<br>`HHI = Σ w_i²`（`1/K ≤ HHI ≤ 1`）<br>`Neff = 1 ÷ HHI`（`1 ≤ Neff ≤ K`） |
| **輸入** | 產業別由 L3 `stock_grp_service.get_industry_category` **先查好傳入**（L2 不自己抓，✅ 合 `CLAUDE.md §8.2`） |
| **單位** | `w_i` / `Top1` / `Top3` / `HHI` **比例（0~1）**；`Neff` **檔數** |
| **門檻常數** | ❌ **刻意不提供**（user 2026-08-14 裁示）。檔內理由：DOJ 的 HHI 1500/2500 是衡量**產業市場結構**用的，套到投資組合沒有依據，**憑空定一個就是新的 magic number**（`CLAUDE.md §3.3`） |
| **判定規則** | **無燈號、無分級** —— 只回數值 + 假設旗標 |
| **缺值行為** | ✅ 回 `coverage_pct`；查不到產業別的檔**不歸入任何桶、不進分母** |
| **合理範圍** | `HHI ∈ [1/K, 1]`、`Neff ∈ [1, K]`（由算式保證） |

**⚠️ 兩個必須顯示給使用者的限制（檔內明文要求 UI 揭露）**
1. **等權假設**：`stock_watchlist` schema 只有 `['name','ticker','updated_at']`，
   **系統不知道實際部位大小**，一律以 `w = 1/N` 計算。回傳帶 `basis='equal_weight'`，**UI 必須顯示這個假設**。
2. **未分類不納入分母**：檔內說明為何不併桶 —— 併成一桶會**低估**集中度、
   併入最大桶是**直接捏造** ⇒ 選「排除 + 誠實揭露覆蓋率」。

#### (B) 籌碼集中度（近 20 日主力買賣超）— 消費端 `src/ui/views/page_inspect.py`

| 欄 | 內容 |
|---|---|
| **輸入** | 「外資＋投信淨買賣超」與「成交量」 |
| **缺值行為** | ✅ 檔內明文：「本站**不拿 0% 集中度頂替**（**0% 是『買賣超剛好抵銷』這個結論，不是缺值**）」 |
| **與異常值徽章的關係** | ✅ 檔內明文：「徽章與集中度**分別判、分別報，不互相背書**」—— 兩支吃的欄位不同，會出現「一支判得出、一支判不出」 |

**相關：三大法人單日買賣超 outlier 徽章** — `src/compute/risk/inst_sanity.py`
`is_inst_net_outlier`：`單日買賣超 > 該股 30D 均量 × INST_NET_OUTLIER_VOLUME_RATIO`
✅ 門檻 `shared/signal_thresholds.py:INST_NET_OUTLIER_VOLUME_RATIO = 5.0`。
（`CLAUDE.md §3.2` 記此項已 wire 進 `section_chips_20d`。）

---

### 5.6 折溢價 / 流動性 / 追蹤誤差

| 指標 | 算式 | 單位 | 門檻常數 | 判定規則 | 缺值行為 |
|---|---|---|---|---|---|
| **折溢價** | `premium_pct`（官方 iNAV 同日 inner-join + 3 守門員 G1/G2/G3 + sanity 上限）／`src/compute/etf/etf_calc.py:calc_premium_discount` | **%** | 健檢 D：`dividend_station_thresholds:PREMIUM_ALERT_PCT=1.5`<br>單檔頁四段：`signal_thresholds:ETF_PREMIUM_DEEP_DISCOUNT_PCT=-2.0` / `FAIR_DISCOUNT_PCT=-0.5` / `FAIR_PREMIUM_PCT=1.0` / `HIGH_PREMIUM_PCT=3.0` | 健檢 D 見 §3.5 | ✅ `stale_nav` 或 `premium_pct=None` → **不填該欄**，標「無折溢價資料」，不假判 |
| **流動性** | 取 20 日均量 + AUM 兩軸**取最嚴重**／`etf_calc.py:calc_liquidity_score` | 均量 **張**；AUM **元 → ÷1e8 換算成億** | `signal_thresholds:ETF_AVG_VOL_20D_LOW_LOTS=500` / `FAIR_LOTS=1000` / `ETF_AUM_LOW_YI=5.0` / `ETF_AUM_FAIR_YI=10.0` | `if avg_vol < 500: 🔴`<br>`elif avg_vol < 1000: 🟡`<br>`else: 🟢`<br>再套 AUM：`if aum億 < 5: 🔴`；`elif aum億 < 10 and level=='🟢': 🟡` | ✅ `calc_avg_volume_20d` 回 None → `{'level': '⚪', 'avg_vol_20d': None, 'reasons': ['資料不足']}`<br>🔴 **但 AUM 那段用 `except (TypeError, ValueError): pass`** —— AUM 型別異常被**靜默吞掉**，`level` 仍回量能單軸的結果，**無旗標**（違 `CLAUDE.md §1`「`except: pass` 一律違憲」） |
| **追蹤誤差** | 由 caller 注入（`build_etf_score_row(tracking_error=...)`），L2 不自算 | **%** | `signal_thresholds:ETF_TRACKING_ERROR_MAX_PCT=1.5` | `if te > 1.5 and tracks_tw50_index(ticker): 紅旗`（§2.7） | ✅ `te is None` → 不觸發紅旗 |

🔴 **AUM 單位陷阱**：`info['totalAssets']` 是**元**，門檻常數是**億**，
換算寫在 `calc_liquidity_score` 內的 `_aum_e = float(aum) / 1e8`（inline，未走 SSOT 換算函式）。
⚠️ 常數名 `ETF_AUM_LOW_YI` **有**編碼單位（`_YI`）✅，但被比較的變數 `aum` **沒有**（違 `§4.1` 命名規範）。

---

### 5.7 ⚠️ 已知問題 #3 — 停利門檻寫死、無任何使用者設定路徑

**實測 `grep -rn "SATELLITE_TAKE_PROFIT_PCT" --include=*.py .` 全命中（14 筆）分類：**

| 類別 | 位置 | 用途 |
|---|---|---|
| **定義（唯一）** | `shared/dividend_station_thresholds.py:SATELLITE_TAKE_PROFIT_PCT: float = 15.0` | 註解：「衛星嚴格停利：獲利達此 % → 停利滾回核心」 |
| **唯一控制流** | `src/services/dividend_station_service.py:flag_take_profit` | `if isinstance(_pnl,(int,float)) and _pnl >= T.SATELLITE_TAKE_PROFIT_PCT: _out.append(...)` |
| **顯示（5 處）** | `page_hold.py:2066`／`etf_tab_dividend_station.py` ×2（`st.info` 與說明文字）／`holdings_digest_message.py`／`dividend_station_service.py:build_summary_prompt` | 全部是 `f"…{T.SATELLITE_TAKE_PROFIT_PCT:.0f}%…"` **純插值顯示** |
| **測試（4 處）** | `test_p04_hold_view.py` ×2／`test_dividend_station_service.py`／`test_holdings_digest_message.py` | 斷言「文案走 SSOT，改門檻不漂移」 |
| **其他（3 處）** | `page_hold.py:324`（import）／`page_hold.py:1985`（註解）／`dividend_station_service.py:941`（docstring） | 非執行路徑 |

**合計 1 + 1 + 5 + 4 + 3 = 14**（＝ `grep` 全命中數，量測日 2026-09-15）。

**✅ 客戶說「唯二的 `st.*` 呼叫只是印出來」— 複驗正確**：
UI 側只有 `etf_tab_dividend_station.py` 的 `st.info(...)` 與 `page_hold.py` 的說明字串，
**沒有任何 `st.slider` / `st.number_input` / `st.selectbox` 綁定到這個常數。**

**✅ 客戶說「沒有任何使用者設定路徑」— 複驗正確，且我確認了全站的設定機制**：
本站**唯一**的門檻覆寫機制是 `macro_thresholds.json`，實測全檔只有兩個 key：
`HEALTH_DEFENSE_THRESHOLD` 與 `BULL_MIN_SCORE`。
`SATELLITE_TAKE_PROFIT_PCT` **不在其中**；`grep "st.slider\|st.number_input"` 全站 6 處，
**沒有一處**是門檻設定（見 §5.3 末段：唯一的使用者輸入是「總資金」）。

| 欄 | 內容 |
|---|---|
| **算式** | 無 —— 純門檻比較 |
| **輸入** | `r["損益%"]`（已算好的持股損益率），**且** `r["held"]` 為真、`r["種類"] == "個股"`、`r["_detail"]["error"]` 為空 |
| **單位** | **%** |
| **判定規則** | `for r in rows:`<br>　`if not r['held'] or r['_detail'].get('error'): continue`<br>　`if r['種類'] != '個股': continue`　← 衛星 ＝ 個股（80/20 近似）<br>　`_pnl = r['損益%']`<br>　`if isinstance(_pnl,(int,float)) and _pnl >= 15.0: 列入停利清單` |
| **缺值行為** | ✅ **正確**：`損益% is None`（無成本）→ `isinstance` 為 False → **不判、不列入**。<br>docstring 原文：「§1：**僅對 held 衛星(個股)且有損益%者判；無成本(損益%=None) → 不判、不捏造**」 |
| **合理範圍** | 無上下界檢查 |

**⚠️ 合規面（已知問題 #3 的另一半）**：
`SATELLITE_TAKE_PROFIT_PCT` 是一個**寫死的行動門檻**，而「15% 該不該停利」取決於
持有成本、稅負、其他部位、資金需求 —— **全部是只有使用者知道的變數**。
依客戶的缺項填補測試判準，**系統替使用者填了這些變數**。
該常數所在檔案的檔頭註解自己也寫（逐字）：
> ⚠️ 這些門檻是「以息養股存股法」的參數，**非本站發明；改動等於改策略，請審慎。**

⇒ **它是一個「引用他人策略的參數」而不是「本站的觀測門檻」，但畫面上沒有區分這兩者。**
⚠️ 本檔只記錄事實，**不提修法**。

---

## 6. 技術指標 kernel

**分層慣例**：kernel（純序列運算）住 `src/compute/scoring/scoring_engine.py`；
adapter（取最後一根 + round + guard）住 `src/compute/strategy/tech_indicators.py`。
✅ **除下述兩處外，所有 adapter 的缺值行為都是 `return None` / `(None, None)` + stderr log。**

| 指標 | 算式 | 單位 | 門檻常數 | 缺值行為 |
|---|---|---|---|---|
| **RSI** | kernel `scoring_engine.compute_rsi`：<br>`delta = close.diff()`<br>`gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()`<br>`loss = (−delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()`<br>`RSI = 100 − 100 ÷ (1 + gain ÷ (loss + 1e-10))`<br>**平滑法 = Wilder RMA**（α=1/period），v19.89 自 SMA 改 —— 理由：台股券商一律用 Wilder，改後 70/30 才可與券商對照 | **0~100 無量綱** | ✅ `src/config/config.py:RSI_OVERBOUGHT=70` / `RSI_OVERSOLD=30`；<br>✅ `shared/signal_thresholds.py:RSI_STRONG_LOW=50.0` / `RSI_NEUTRAL_WEAK_LOW=40.0`<br>`period` 預設 **14**（🔴 inline 預設參數） | ✅ `df is None or len(df) < period+1` → `None`；末值 `isna` → `None`；例外 → `None` + log<br>⚠️ `loss` 恆 0（全漲）→ `+1e-10` epsilon → RSI ≈ 100（**刻意映射，不 raise**；檔內自陳「極端全漲/全跌仍映射 ~100/~0」） |
| **ATR** | kernel `scoring_engine.compute_atr`：<br>`TR_t = max(High_t − Low_t, \|High_t − Close_{t−1}\|, \|Low_t − Close_{t−1}\|)`<br>`wilder=True`（預設）→ `tr.ewm(alpha=1/period, adjust=False).mean()`<br>`wilder=False` → `tr.rolling(period).mean()` | **元**（與價同單位） | `period` 預設 **14**（🔴 inline）；停損倍率 `risk_control.ATR_MULTIPLIER=1.5`（🔴 inline in L2） | 首根 `prev_close=NaN` → `max` skipna → `TR = High − Low` ✅<br>🔴 **缺 `high`/`low` 欄 → 靜默退回 `close`**（`TR` 退化為 `abs(ΔClose)`），**回傳型別與正常路徑相同、不帶旗標** —— 違 `CLAUDE.md §1`「任何填補必須在輸出帶旗標」。docstring 有寫「不炸」，但**呼叫端無從得知已降級** |
| **KD** | `tech_indicators.calc_kd`：<br>`low_n = low.rolling(period).min()`；`high_n = high.rolling(period).max()`<br>`RSV = (close − low_n) ÷ (high_n − low_n).replace(0, 1) × 100`<br>`K = RSV.ewm(com=2, adjust=False).mean()`（≡ α=1/3）<br>`D = K.ewm(com=2, adjust=False).mean()` | **0~100 無量綱** | ✅ `signal_thresholds:KD_OVERBOUGHT_LEVEL=80.0` / `KD_OVERSOLD_LEVEL=20.0`<br>`period` 預設 **9**（🔴 inline） | ✅ `len(df) < period` → `(None, None)`；`isna` → `(None, None)`；例外 → `(None, None)` + log<br>🔴 **`.replace(0, 1)` 是未標旗標的填補** —— 見下 |
| **布林** | `tech_indicators.calc_bollinger`：<br>`ma = close.rolling(20).mean()`；`std = close.rolling(20).std(ddof=0)`<br>`upper = ma + 2×std`；`lower = ma − 2×std`<br>`bw = (upper − lower) ÷ ma.replace(0, NaN) × 100` | `upper/lower/ma/price` **元**；`bw` **%** | ✅ `signal_thresholds:BB_BW_SHRINK_WARN_RATIO=0.7` / `BB_BW_SHRINK_ACTION_RATIO=0.6`；`BB_NEAR_UPPER_RATIO`<br>`window=20` / `mult=2`（🔴 inline 預設） | ✅ **本檔的正解樣板**：`ma.replace(0, float('nan'))` → 四個末值任一 `isna` → `return None`。<br>註解原文：「ma==0 時 Series 除法回 **inf**（不 raise，會穿過 except 與末值 isna 檢查**外流**）→ 顯式換 NaN」<br>📌 `ddof=0` 是**刻意**（v19.105：原 ddof=1 帶寬虛胖 ~2.6%），屬**已登記的例外** |
| **MA / 乖離** | SSOT `shared/calc_helpers.py:calc_bias_pct(price, ma)`：<br>`bias% = (price − ma) ÷ ma × 100`<br>MA 定義 `macro_helpers.compute_twii_bias`：`_maN = mean(tail(min(N, n)))`，N ∈ {20,60,120,240} | **%** | ✅ `src/config/config.py:ANNUAL_MA = 240`（**交易日**，非日曆日）<br>五桶 `bias_240` 門檻見 §3.1 | ✅ `calc_bias_pct`：`price is None or ma is None or ma <= 0` → `None`<br>✅ `compute_twii_bias`：全空 / 找不到 Close 欄 / dropna 後長度 0 → `None` + log<br>⚠️ **`n < 240` 不是 N/A** —— 見下 |
| **IBS** | `tech_indicators.calc_ibs` = `(close − low) ÷ (high − low)` | **0~1 比例（非 %）** | ✅ `signal_thresholds:IBS_OVERSOLD_THRESHOLD=0.2` / `IBS_OVERBOUGHT_THRESHOLD=0.8` | ✅ `df is None or df.empty` → `None`；例外 → `None` + log |
| **量比** | `tech_indicators.calc_volume_ratio(df, period=5)` = `今日量 ÷ 近 period 日均量` | **倍** | ✅ `signal_thresholds:VOLUME_RATIO_SURGE_HIGH=3.0` / `SURGE=1.5` / `MILD=1.0` / `DRY=0.5`<br>⚠️ **`period` 預設 5，但 §4.1 評分表的文案寫「20 日均量」** —— 兩個呼叫端用不同視窗（見 §9） | ✅ `len(df) < period+1` → `None`；均量為 0 → `None`；例外 → `None` + log |
| **VCP** | `tech_indicators.calc_vcp(df, n_swings=3)` — 找擺動高低點、判波幅是否收縮 | 無量綱 | `signal_thresholds` 的 `VCP_*` 前綴組 | ✅ `df is None or len(df) < 30` → `None`；例外 → `None` + log（v19.83 補的 try/except） |
| **RS 相對強度** | `scoring_engine.calc_rs_score` → 0~100 分；分級 `tab_helpers.classify_rs_zone` | **0~100 分** | ✅ `signal_thresholds:STOCK_RS_STRONG_MIN=75.0` / `STOCK_RS_NEUTRAL_MIN=50.0` | ✅ `rs_val = None` → `('⚪ 無資料', 黃)` —— **有專屬的未評估態** |

**RS 分級規則**（`classify_rs_zone`）：
```
if rs_val is None: → ('⚪ 無資料', TRAFFIC_YELLOW)
elif rs >= 75:     → ('🟢 強勢 {rs:.0f}分 {箭頭}', TRAFFIC_GREEN)
elif rs >= 50:     → ('🟡 中性 {rs:.0f}分 {箭頭}', TRAFFIC_YELLOW)
else:              → ('🔴 弱勢 {rs:.0f}分 {箭頭}', TRAFFIC_RED)
```
⚠️ **`⚪ 無資料` 與 `🟡 中性` 都是黃色** —— 顏色分不出「沒資料」與「中性」（§0.3 符號超載的顏色版）。

### 6.1 🔴 KD 的 `.replace(0, 1)` — 未標旗標的填補

```python
rsv = ((df['close'] - low_n) / (high_n - low_n).replace(0, 1)) * 100
```
`high_n == low_n`（period 內完全無波動，例如連續跌停鎖死）時，**分母 0 被換成 `1`**。
此時 `close == low_n == high_n` ⇒ `RSV = 0 ÷ 1 × 100 = 0` ⇒ K/D 向 0 收斂
⇒ 被讀成「**極度超賣**」（§4.1 的 KD 評分表會給 10~13 分、`section_when_buy_sell` 會列「✅ KD低檔 → 底部進場區」引用）。
**實際情況是「這段期間沒有價格資訊」。**

**⚠️ 同一個檔案裡有兩種標準**：
- `calc_kd`：`.replace(0, 1)` → 假 RSV=0（**錯**）
- `calc_bollinger`：`ma.replace(0, float('nan'))` → `isna` → `return None`（**對**）

⇒ 兩支函式面對**同一個問題**（分母為 0）用了**相反的處置**。
✅ 而 `shared/station_specs.py` 甚至已經有這個情況的專屬缺值原因常數
`MISS_NO_VARIATION = "no_variation"`（文案：「這段期間價格完全沒有波動（標準差為 0）… 不是抓取失敗，重跑不會改變；多半是停牌或極低流動性」）——
**KD 沒有用它。**

⚠️ **觸發頻率未實測**（連續 9 日 high==low 在台股是可能但罕見）—— 見 §9。

### 6.2 ⚠️ `bias_240` 在資料不足時不是年線乖離（repo 已自行揭露）

`compute_twii_bias` 的 `_maN = mean(tail(min(240, n)))` ——
**當 `n = 90` 時，`ma240` 實際是 MA90，`bias_240` 是「距 MA90 的乖離」。**

✅ 回傳帶 `is_estimated = (n < 240)` 與 `data_days`；文案 SSOT 在 `macro_helpers` 的 I2 區塊。
⚠️ 但該檔明文（逐字）：
> I2 **只做揭露**：燈號／門檻／桶判定**仍直接套用這個估算值**，尚未針對估算另設規則。

⚠️ 且 `macro_helpers.py` 另一處自陳（逐字）：
> 全 repo 讀 `bias_240` 的 **10 個消費點裡只有少數**帶揭露，其餘
> 「拿到的都是裸數字 —— 一個『距 90 日均線的乖離』被當成年線乖離講給人與 LLM 聽」。

⇒ **`bias_240` 是五桶 `mid` 桶的一盞燈**（§3.1，yellow=10 / red=20）
⇒ **一個 MA90 乖離會被拿去判「年線乖離過熱」。**

📌 **`S1-2 §2.10(b)` 的 `or 0` 問題 — 本次複驗維持該文件自己的修正結論**：
`macro_snapshot.py` 的 `'bias_240': calc_bias_pct(...) or 0` 看似把缺值壓成 0（＝價格恰在均線＝綠燈），
但 `calc_bias_pct` 只在 `ma <= 0` 時回 `None`，而該 caller 的 `ma` 來自台股指數收盤價的平均 ⇒ `ma > 0` 恆成立
⇒ **`or 0` 是死碼，不是活 bug**。
⚠️ **本檔沿用 S1-2 的推導（`close > 0 → mean > 0 → ma > 0`），同樣未跑反例實測**（見 §9）。
⚠️ 但**仍值得記錄** —— 理由同 `CLAUDE.md §-2` 的 `db4c139` 前例：**留著會讓下一個人以為「缺值已被處理」。**

### 6.3 出場訊號三維（`src/compute/scoring/exit_signals.py`）

📌 **路徑更正**：`CLAUDE.md §8.2` 的 L2 代表檔把它列在 `src/compute/strategy/`，
**實際在 `src/compute/scoring/exit_signals.py`**（本次 `find` 實測）。

| 欄 | 內容 |
|---|---|
| **指標名** | 畫面「出場點綜合提示」／程式 `evaluate_exit_signals` |
| **算式** | `score = Σ(三維各自命中與否)`，`score ∈ {0,1,2,3}` |
| **輸入** | `tech` ← `compute_tech_bearish(df, k, d)`；`chip_signal` ← `analyze_20d_chips_from_df` 的 `'signal'` 字串；`news` ← `judge_news_sentiment`（LLM 情緒判讀，6h 快取） |
| **單位** | `score` **命中維度數（0~3）**；`confidence` **0~100** |
| **門檻常數** | ✅ `shared/signal_thresholds.py:MA20_POSITIVE_DEVIATION_THRESHOLD_PCT`（月線正乖離）／`KD_OVERBOUGHT_LEVEL=80.0`<br>✅ `GRP_NEWS_BEARISH_CONFIDENCE_MIN=50.0`（＝`news_conf_threshold` 預設 50）<br>🔴 **inline**：MA 週期 `(5, 20, 60, 240)`、`len(df) < 20`、`len(reasons) >= 2`、MACD `fast=12/slow=26/signal=9` |

**三維判定規則**
```
news_hit = bool(news) and news['label']=='利空' and int(news.get('confidence',0)) >= 50
tech_hit = bool(tech) and tech['bearish']
chip_hit = '大戶倒貨' in (chip_signal or '')        # ← 🔴 字面耦合
score    = sum([news_hit, tech_hit, chip_hit])
```

**技術維 `compute_tech_bearish` 的內部評分**
```
reasons = []
if ma20 and ma60 and p < ma20 < ma60: reasons += ['空頭排列（股價<月線<季線）']; strong = True
elif ma60 and p < ma60:               reasons += ['跌破季線 MA60']
if ma240 and p < ma240:               reasons += ['跌破年線 MA240']
if bias_ma20 > MA20_POSITIVE_DEVIATION_THRESHOLD_PCT: reasons += ['月線正乖離過大 …']
if ma5 and p < ma5:                   reasons += ['跌破 5MA（短線轉弱）']
if k < d and k > 80:                  reasons += ['KD高檔死叉 …']
if _weekly_macd_turn_negative(close): reasons += ['週MACD翻負（中線轉弱）']; strong = True
bearish = strong or len(reasons) >= 2
```

**分數 → 燈號評分表**（`exit_signals._LEVELS`）

| `score` | icon | label（**引用：現行 code 原文**） | 顏色 |
|---|---|---|---|
| 3 | 🔴 | `強烈出場` | `TRAFFIC_RED` |
| 2 | 🟠 | `建議減碼` | `#f0883e`（🔴 inline hex） |
| 1 | 🟡 | `留意觀察` | `TRAFFIC_YELLOW` |
| 0 | 🟢 | `訊號清淡` | `TRAFFIC_GREEN` |

**🔴 缺值行為 —— 與 235 燈同型的問題，但這裡沒有修**

| 輸入 | 缺值時 | 後果 |
|---|---|---|
| `tech` | `tech=None` → `tech_hit = bool(None) and ... = False` | 計為「**未命中**」，不是「未評估」 |
| `tech` 內部 | `df is None or len(df) < 20 or 'close' 不在欄位` → **直接 `return {'bearish': False, 'reasons': [], 'hits': 0, 'strong': False}`** | 🔴 **資料不足回 `bearish=False`**，與「查過了、沒轉空」**完全同形、無旗標** |
| `news` | `news=None` → `news_hit=False`，但 `news_desc = '未掃描'` | ✅ **`dims` 那一格的說明字串誠實寫「未掃描」** |
| `chip_signal` | `''` → `chip_hit=False`，`chip_desc='—'` | 計為未命中 |

🔴 **headline 會說一句不成立的話**：
```python
headline += f'（{score}/3 維轉空：{"＋".join(hit_names)}）' if score else '（三維未轉空）'
```
⇒ 三維**全部沒有資料**時 `score = 0` ⇒ 畫面顯示 **`🟢 訊號清淡（三維未轉空）`**。
⇒ 「**三維未轉空**」宣稱的是「**我看過三個維度、三個都沒事**」，
實際上可能是「**一個維度都沒評估到**」。

⚠️ **這正是 `light_235` 已經修好的那個失效模式**（§3.4）——
235 現在會說「**{三個依據} 都沒有資料 —— 不是「都沒觸發」，是沒東西可以判**」，
而 `evaluate_exit_signals` **仍然只說「三維未轉空」**。
✅ 部分緩解：`dims` 的第三元素（說明字串）帶 `'未掃描'` / `'—'`，
**UI 若有展開 dims 就看得到**；但 `score` / `label` / `headline` 三個欄位**都不帶旗標**。
⚠️ **本項為單組推導 + 讀碼，未跑端到端**（見 §9 U-23）。

🔴 **字面耦合**：`chip_hit = '大戶倒貨' in chip_signal` —— 同 §2.6 的病，
改 `analyze_20d_chips_from_df` 的訊號措辭就會讓這一維靜默失效。


---

## 7. 已知問題總表

### 7.1 客戶點名 8 項 — 逐項複驗結果

| # | 客戶陳述 | 複驗結果 | 章節 |
|---|---|---|---|
| **1** | 同一組「便宜／合理／昂貴／超貴」字面**至少 7 份複本**，沒有兩份形狀相同；其中**四處**被當控制流（`if '昂貴' in val:`）—— 改字面就改行為 | ✅ **成立，且比回報的更多**。實測歸併出 **15 個 family**；被當控制流的**有 5 組消費點**（C1~C5），其中 **C5（`risk_radar`）實測為死碼**（production 從未傳 `valuation_level`）。⚠️ 唯一做對的是 `section_psy_checklist`（比對 **code** 不比對中文） | §2.6 |
| **2** | 殖利率四燈控制流鎖在 **emoji**（`etf_recommendation` 讀 `'🟢' in val`）；配息健康鎖**中文**（`'吃本金' in div_health`）—— 同一支函式兩種寫法 | ✅ **完全成立，且已跑出反例**：把 `'🔴 吃本金'` 改成 `'🔴 侵蝕本金'` → 紅旗消失、**verdict 從「觀察」翻成「留下」**；把 `'🟢'` 換成 `'綠'` → 估值註解靜默消失。另補：`liquidity_level` 也鎖 emoji ⇒ **三個欄位、兩種標準** | §2.7 |
| **3** | `SATELLITE_TAKE_PROFIT_PCT = 15.0` 是寫死常數，沒有任何使用者設定路徑；唯二 `st.*` 呼叫只是印出來 | ✅ **完全成立**。14 個命中逐一分類：1 定義 / 1 控制流 / 5 顯示 / 4 測試 / 3 其他。全站門檻覆寫機制只有 `macro_thresholds.json`（只 2 個 key），該常數不在其中 | §5.7 |
| **4** | PE 取數層 `if _pe != _pe or _pe <= 0: continue` 把 NaN 與 ≤0 丟進同一條路 ⇒ 分不出「來源沒給」與「非正值」；且本站**不自己算 PE** | ✅ **完全成立**（原碼逐字複驗）。補：該檔 docstring 有一條**正確**的防禦說明（擋住虧損股被排成「全市場最便宜」） | §2.3 |
| **5** | 缺 PE ⇒ 因子覆蓋率低於 `SCREENER_MIN_FACTOR_COVERAGE_RATIO=0.5` 會讓整檔**失去參賽資格**（出局，不是排後面） | ✅ **成立，並補上機制**：函式簽章預設 `drop_unscored=False`（排最後），**但 production 入口 `get_ranked_picks` 明確傳 `drop_unscored=True`** ⇒ 真的移除。附換算表（5 因子需 ≥3 個有資料） | §4.6 |
| **6** | 三率穿透實際是 **5 個指標**；淨利率與 ROE **沒有中文判讀語**；ROE 那格程式回的是**槓桿警語不是判決** | ⚠️ **三段要拆開**：<br>「5 個指標」✅ 成立（IA v2 新頁只顯示 3 格）<br>「ROE 回槓桿警語不是判決」✅ 成立（`ROE` slot 無 `Status` 欄）<br>「淨利率沒有中文」✅ 成立（畫面直接印 `Pass`/`Thin Profit`/`Loss`）<br>「**ROE 沒有中文**」⚠️ **不完全成立** —— UI 有中文，但**是 UI 自己合成的**，且 `❌ 本業虧損` 對 ROE **語意錯**（ROE≤0 是稅後淨利為負，不是本業虧損）<br>**另新增**：三個渲染端三套標籤；`tab_stock.py` **完全沒有缺值 gate**（PR #673 登記未修，本次複驗仍在） | §4.4 |
| **7** | 同一盞「減碼」燈，個股頁與組合頁觸發條件寬度不一樣 —— **個股頁那段可能永遠點不亮**（客戶自標未複驗） | ⚠️ **需要更正**：**不是永遠點不亮，是「半盲」**。實測：殖利率 ≤3% 兩頁都亮；**3%<殖利率≤5% 只有組合頁會亮**。根因是個股頁傳的 `'偏貴'` 既不含 `昂貴` 也不含 `超貴` ⇒ **該字面在全站沒有任何消費端會匹配，是死值** | §3.6 |
| **8** | `235 加碼燈` 的名字本身帶動作語 —— 屬合規待處理項（要改只能改 code，v1 凍結中） | ✅ **成立**。四個 label 三個含「加碼」、一個含「停利」；`deploy_pct` 更直接給出 20/30/50% 的**資金比例數字** | §3.4 |

### 7.2 本次新增發現（不在既有材料中）

| # | 發現 | 嚴重度判斷依據 | 章節 |
|---|---|---|---|
| **N-1** | 🔴 **`calc_fundamental_score` 量綱錯誤**：`avg_div`（**元/股**）被當**殖利率 %** 比對 `YIELD_HIGH/MID/LOW` ⇒ 估值分與真實殖利率**顛倒**。實測：真殖 1.80% → 估值 **3/3「便宜區 >7%」**；真殖 10.00% → 估值 **0/3「偏貴 <3%」** | **有畫面影響**（⚖️ 估值卡的分數與 ✓/✗）。同 repo 已修過同型 bug（v19.179 B1-b），**這條沒修** | §4.2 |
| **N-2** | 🔴 **`calc_health_score` 缺值直接回 0** ⇒ 什麼都沒抓到的股票顯示「0 分 · 🔴 弱勢危險」。同 repo 的總經健康評分**明文拒絕**這麼做 | 直接違反客戶紅線「缺失值不得填 0」；且 `health_score` 是三個下游判定的輸入 | §4.1 |
| **N-3** | 🔴 **`calc_sharpe` 回 `0.0` 繞過 ETF 綜合分的 rescale 機制** ⇒ 資料不足的 ETF **少一顆星**（實測 3★ vs 4★），且剛好跨過 `KEEP_COMPOSITE_MIN=0.65` ⇒ **「留下」翻「觀察」**。（＝ `S1-2` U-3 的解答） | 設計良好的缺值機制被上游一個 `return 0.0` 從旁路繞過 | §5.1 |
| **N-4** | 🔴 **`final_recommendation` 四個輸入全部 `default 0` / `default ''`** ⇒ 抓取失敗的股票拿 `pts=0` → 「🔴 等待」，與真的很差同形；**沒有 ⚪ 未評估這一級** | 同 N-2 家族 | §3.7 |
| **N-5** | 🔴 **`'合理 3~5%'` vs `'🔴昂貴價'` 標籤直接矛盾** —— 同一個殖利率帶、同一個畫面，一張卡說合理、另一張說昂貴 | 兩張卡在同一個分頁（🔬 個股）同時渲染 | §4.2 / §2.6 |
| **N-6** | ⚠️ **PE 河流圖三組 preset 是 UI 檔內的 inline dict**（`_PE_BANDS`），而 PB 河流圖走 L0 SSOT 且**有產業分帶**；PE **沒有** ⇒ 金融股的 PB 用金融帶、PE 用製造業通用帶 | 違 `CLAUDE.md §3.3`；且兩張並排的圖標準不一 | §2.4 |
| **N-7** | ⚠️ **`⚪` 符號超載**：同時代表「未評估」（`Flag.level`、`'⚪ 未評估'`）與「中性、有結論」（`classify_yield_zone` 的 `'⚪ 中性持有'`、`classify_stock_status_lamp` 的 `'⚪'`）。顏色版同病：`classify_rs_zone` 的 `⚪ 無資料` 與 `🟡 中性` **同為黃色** | 使用者無法分辨「沒資料」與「判了、結論中性」 | §0.3 / §3.6 / §6 |
| **N-8** | ⚠️ **`risk_radar` 的 `valuation_level` 估值疊加是死碼** —— production 0 個 caller 傳這個參數（只有測試傳）⇒ `== "極貴"` / `== "便宜"` 兩個分支永不執行 | 同 `CLAUDE.md §-2` 的 `db4c139` 型態：留著會讓人以為已接線 | §2.6 C5 |
| **N-9** | ⚠️ **`max_score` 仍未輸出**（本次複驗：parquet 16 列、`max_score notna = 0/16`），且 schema 註解自陳「**必存**」 ⇒ 前進式驗證資料集無法重建當日 health | 影響本專案唯一零 lookahead 的驗證資料集 | §3.3 |
| **N-10** | ⚠️ **`calc_liquidity_score` 的 AUM 段用 `except (TypeError, ValueError): pass`** —— AUM 型別異常被靜默吞掉，`level` 仍回量能單軸結果、無旗標 | `CLAUDE.md §1` 明文「`except: pass` 一律違憲」 | §5.6 |
| **N-11** | ⚠️ **停損門檻量綱雙胞胎**：`STOP_LOSS_DEFAULT_PCT=8.0`（%）與 `config.py:STOP_LOSS_PCT=0.08`（比例）是**兩個獨立宣告**（不像 `YIELD_HIGH_DEC` 是推導）⇒ **會漂移**。另 `HARD_STOP_LOSS_PCT=7.0` 與前者不同值，語意差別未查 | 違 `CLAUDE.md §2.1` SSOT | §5.3 |
| **N-13** | 🔴 **`evaluate_exit_signals` 在三維全缺時輸出「🟢 訊號清淡（**三維未轉空**）」** —— 那句話宣稱「我看過三個維度、都沒事」，實際可能一個都沒評估到。`compute_tech_bearish` 更是 `len(df) < 20` 就直接 `return {'bearish': False}`，**與「查過了、沒轉空」完全同形、無旗標** | **與 `light_235` 已修好的失效模式完全同型**（§3.4），但這裡沒修。部分緩解：`dims` 的說明字串有寫 `'未掃描'` | §6.3 |
| **N-14** | ⚠️ **`CLAUDE.md §8.2` 的 L2 代表檔把 `exit_signals.py` 寫在 `src/compute/strategy/`，實際在 `src/compute/scoring/`** | 憲法自己的路徑資訊過期（`§8.2.A.0 規則 1` 禁行號的同一族問題） | §6.3 |
| **N-12** | ⚠️ **`CLAUDE.md §3.3` 宣告「❌ 標記 0 項」與實況不符** —— 本次在 `calc_fundamental_score`（6 個）、`final_recommendation`（7 個）、`etf_scoring_helpers._WEIGHTS/_NORM`（13 個）、`section_357_valuation._PE_BANDS`（9 個）、財報等第樹（4 個）等處找到 inline magic number | 憲法自己說「會說謊的憲法比沒有憲法更危險」（§8.2.A.0） | 全文 |

---

## 8. 合規掃描 —— 現行 code 裡的行動語（**稽核軌跡，非本文件的建議**）

> ⚠️ **本節全部內容為「引用現行 code 的字串常數」**，逐字轉錄供稽核定位。
> **本文件本身不對任何標的產生買賣建議。**
> 判準採客戶的**缺項填補測試**：若要從「觀測」走到「行動」必須代入只有使用者才知道的變數
> （可動用資金／持有期間／風險承受度／既有部位／稅負），而 code **替他填了** ⇒ 依該判準屬建議。

### 8.1 判定層（L0/L2 純函式）裡就帶行動語的標籤 —— **影響最廣**

| 位置 | 標籤字串（引用） | 為什麼落在紅線內 |
|---|---|---|
| `shared/thresholds.py:classify_yield_zone` | `'🟢 強烈買進'` / `'🟡 適度減碼'` / `'🔴 獲利了結'` / `'⚪ 中性持有'` | **這是 L0 SSOT 函式** —— 個股 / ETF 三個 Tab 共用。「強烈買進」把「殖利率 ≥7%」這個**觀測**直接翻成**行動**，中間省略的正是資金與部位 |
| `shared/dividend_station_thresholds.py:LIGHT_META` | `'小跌加碼'` / `'急跌加碼'` / `'崩盤/深水加碼'` / `'停利警示'` + `deploy_pct = 20.0/30.0/50.0` | 已知問題 #8。**不只是 label，還給出資金比例數字** |
| `shared/dividend_station_thresholds.py` | `SATELLITE_TAKE_PROFIT_PCT = 15.0`（「衛星嚴格停利」） | 已知問題 #3。15% 該不該停利取決於成本 / 稅 / 其他部位 ——**全是使用者才知道的變數** |
| `src/compute/etf/etf_helpers.py` | `'🟢 強烈買進'` / `'🟡 適度減碼'` / `'🔴 獲利了結'`（delegate 到上面那支）<br>`'大跌大買 — 大幅加碼，剩餘資金主力投入'` / `'分批停利'` | 「剩餘資金主力投入」**直接指示資金配置** |
| `src/compute/etf/etf_recommendation.py` | `'價位偏低,分批加碼時機較佳'` / `'價位偏高,續抱可、暫緩加碼'` | L2 判定層 |
| `src/compute/etf/etf_calc.py` | `'觀察均線止跌；不加碼'` | L2 判定層 |
| `src/compute/risk/risk_control.py` | `'🟡 移動停利出場'` | L2 判定層 |
| `src/compute/risk/risk_radar.py` | `'估值頂部分位（極貴），建議減倉至中性'` / `'估值底部分位（便宜），可逐步擇機加碼'` | ⚠️ **實測為死碼**（§2.6 C5），production 不會產出 |
| `src/compute/screener/scorability.py` | `EXPENSIVE_VALUATION_MARKER = "超貴"` → `eliminated`（汰弱） | 「淘汰」本身是行動 |
| `src/ui/tabs/tab_helpers.py:classify_stock_status_lamp` | `'🔵 加碼'` / `'🟠 減碼'` / `'🟡 警示'` | L5，但是兩個分頁共用的 SSOT 函式 |
| `src/ui/tabs/tab_helpers.py:final_recommendation` | `'🟢 積極'` / `'🟡 觀察'` / `'🔴 等待'` | 「積極 / 等待」是**部位方向**的行動語 |
| `src/data/core/data_registry.py`（**L1**） | `'🟢 便宜價／強烈買進（357 殖利率估值法則）'` / `'🟡 昂貴，適度減碼'` / `'🔴 過貴，獲利了結'` | ⚠️ 落在 **L1 資料層**的教學對照表 |

### 8.2 UI 層文案（引用，數量較多，以下為定位樣本非窮舉）

`section_357_valuation.py`：`'🟢便宜價 — 積極買進'`、`'可大膽買進，股息都進口袋'`、`'🔴超過昂貴 — 避免追高'`、`'嚴禁追高'`
`etf_tab_single.py`：`'🟢 強烈買進時機'`、`'🔴 嚴禁追高'`、`'投入 20–30% 資金小量加碼'`、`'剩餘資金分批加碼'`、`'衛星部位停利或減碼，核心紀律扣款'`
`section_when_buy_sell.py`：`'🟢 可考慮加碼'`、`'🔴 不建議加碼'`、`'加碼點 >{...}'`
`macro/section_long.py`：`'科技類股可持有或加碼'`　`macro/section_mid.py`：`'等待更明確的突破訊號加碼。'`
`app_ai_service.py`：`'🚀 【強烈買入】評分≥85 + 357便宜價 + 多頭排列。'`、`'✅ 【積極買入】評分≥75且位於357便宜區，可分批布局。'`、`'⚠️ 【357估值】…不宜追高，等待回調。'`
`v5_modules.py`：`'…估值過高，建議逢高減碼'`、`'…存股首選'`

⚠️ **`app_ai_service` 那一組特別值得注意**：它是**規則式**產生的（不是 LLM 產的），
條件是 `score >= 85 and '便宜' in val and '多頭' in trend` ⇒ **字面耦合 + 直接輸出「強烈買入」**。
⇒ §2.6 的字面複本問題與合規問題**在這裡交會**：改一個估值字面，會讓「強烈買入」這句話出現或消失。

### 8.3 ✅ 已經做對的合規樣板（值得沿用）

| 位置 | 做法 |
|---|---|
| `src/compute/risk/concentration.py` | **刻意不提供燈號 / 門檻**（user 2026-08-14 裁示）。理由：DOJ 的 HHI 1500/2500 是衡量產業市場結構用的，**套到投資組合沒有依據，憑空定一個就是新的 magic number** ⇒ 只回數值 + 假設旗標 + 覆蓋率 |
| `section_when_buy_sell.py` 的總資金輸入 | **承認「這個數字只有使用者知道」** —— `st.number_input('💰 你的總資金（元）')`，註解原文「資金因人而異 → UI 輸入 + session 記住，**不寫死常數（§1 不造假假設）**」 |
| `rs_leader_service.py` | 免責原文：「這是『相對強弱』不是『基本面買點』：抗跌只代表跌得比大盤少 / 逆勢強，**不等於便宜或該追**」 |
| `shortage_screener_service.py` | 免責原文：「分數高只代表財報足跡像缺貨，**不等於股價便宜、也不保證會漲**；估值/追高/籌碼要另外看」 |
| `concentration.py` / `page_inspect.py` | **把假設攤開**（等權假設、覆蓋率、「不拿 0% 頂替」） |

⇒ **這四個樣板的共同特徵**：把「我只知道什麼」與「你還需要自己決定什麼」分開講。

---

## 9. 我沒查到的（`CLAUDE.md §-2 規則 6`）

> ⚠️ 以下全部為**單組結論**或**根本沒查**，**不得**作為後續動作的前提。

### 9.1 涵蓋率 —— 這份文件不是全站指標清單

| # | 事項 | 狀態 |
|---|---|---|
| **U-1** | 「本檔涵蓋了畫面上的全部指標」 | ❌ **不成立，也沒有宣稱成立。** 本次是**由客戶點名的 8 項 + 主要指標族出發的定向盤點**，**不是**反向從 UI 逐頁清點。`src/ui/views/`（IA v2 五頁）、`src/ui/tabs/`、`src/ui/etf/` 三組目錄**沒有逐檔清點渲染了哪些指標**。**涵蓋率未量測。** |
| **U-2** | 完全沒碰的模組 | `src/compute/strategy/v4_strategy_engine.py`、`v5_modules.py` 的**其餘函式**（只讀了 `calc_357_valuation`）、`src/compute/scoring/scoring_engine.py` 的**多因子評分 `score_single_stock` 全套**（只讀了 `compute_rsi` / `compute_atr` 兩個 kernel 與六因子權重表註解）、`src/compute/health/*`、`src/compute/notify/*`、`src/compute/screener/` 的 `shortage_screener` / `rs_leader_screener` / `cross_quarter_trends` / `forward_test`、`src/compute/etf/etf_quality.py`（星等的另一套）、`exit_signals` 的另外 4 支函式（`compute_macd` / `weekly_macd_hist` / `build_news_prompt` / `parse_news_sentiment` —— 只有 `evaluate_exit_signals` / `compute_tech_bearish` 收錄於 §6.3） |
| **U-3** | `shared/signal_thresholds.py` 的 76 個語意常數 | **只抽查了約 35 個**。`scoring_engine` 那 50 個前綴常數（`MOM_` / `RISK_` / `RS_` / `SQ_` / `FGMS_` / `LEAD_` / `CL_` / `BOLL_` / `FAKEOUT_` / `RR_` / `ATR_STOP_` / `TIME_STOP_` / `VCP_` / `SQUEEZE_` / `POS_`）**幾乎沒讀**，它們對應的算式與判定規則**未收錄**。 |
| **U-4** | 基金站指標 | **完全不在本次範圍**（`my-Fund-dashboard` 是姊妹 repo）。`S1-2 §3` / `§5` 的基金站內容**本檔未複驗、未轉錄**。 |

### 9.2 單組結論 —— 需要第二組獨立驗的

| # | 事項 | 為什麼只能當待驗事項 |
|---|---|---|
| **U-5** | **「估值字面共 15 個 family」** | 單組 grep + 人工歸併。grep pattern 只掃了 `便宜\|合理\|昂貴\|超貴\|偏貴\|極貴` 六個詞，**且只掃單引號 / 雙引號的字面**。以 f-string 拼接、或用其他措辭（「划算」「貴森森」「高估」「低估」）的**掃不到**。**歸併成 family 的判斷是人工的。** |
| **U-6** | ~~「exit_signals 的路徑找不到」~~ → **已解決，見 §6.3** | 真實路徑是 `src/compute/scoring/exit_signals.py`（`CLAUDE.md §8.2` 的 L2 代表檔寫成 `src/compute/strategy/`，**文件路徑有誤**）。⚠️ **但 `exit_signals` 的另外 4 支函式**（`compute_macd` / `weekly_macd_hist` / `build_news_prompt` / `parse_news_sentiment`）**本檔只讀了簽章，沒有收錄算式與門檻**。 |
| **U-7** | **`calc_fundamental_score` 的量綱錯誤（N-1）** | 實測部分（傳 18.0 → 估值 3/3「便宜區 >7%」）是**硬證據**；但「這就是 production 行為」的推論鏈依賴「`avg_div2` 一定是元」——我讀了上游 `app_stock_fetchers.avg_div` 的算式與 `section_health_score` 的檔內註解兩個來源，**沒有跑端到端**（沙箱無法打 FinMind）。**⚠️ 這是本檔最承重的新發現，請優先派獨立一組驗。** |
| **U-8** | **`calc_health_score` 缺值回 0 的下游影響** | `score=0` 本身是實測。但「會被 `scorability` 汰弱且防線接不到」是**單組推導**（`_as_float(0)` 回 `0.0` 不是 `None`）——**沒有跑端到端反例**。 |
| **U-9** | **`risk_radar.valuation_level` 是死碼（N-8）** | 單組 grep（`valuation_level\s*=`）。若有 caller 用 `**kwargs` 或 dict unpack 傳入，**這個 pattern 掃不到**。 |
| **U-10** | **「財報等第 `else 50` 是死碼」** | 單組推導（`max_pts > 0` ⟺ `valid` 為真，而 `if not valid:` 在其後 return `None`）。**沒有跑反例。** |
| **U-11** | **「單格缺漏仍會讓財報等第偏好」** | 沿用 `S1-2` U-10 的推論（等第樹全掛在 `len(fail_items)` 而 N/A 不進 `fail_items`）。**S1-2 沒跑反例，本檔也沒跑。** |
| **U-12** | **`bias_240` 的 `or 0` 是死碼** | 沿用 `S1-2` U-11 的推導鏈（`close > 0 → mean > 0 → ma > 0`）。**兩份都沒跑反例實測。** |
| **U-13** | **「`tab_stock.py` 是唯一沒有缺值 gate 的獲利能力渲染端」** | 只比對了三個渲染端（`page_inspect` / `section_financial_health` / `tab_stock`）。**沒有窮舉全站還有沒有第四個渲染 `Profitability_Module` 的地方。** |
| **U-14** | **「全站門檻覆寫機制只有 `macro_thresholds.json` 的 2 個 key」** | 單組結論。掃了 `st.slider` / `st.number_input`（6 個命中）與該 json。**沒掃** `st.selectbox` / `st.radio` / `st.toggle` / 環境變數 / `st.secrets` 是否也能改門檻。 |

### 9.3 查到一半、沒追完的

| # | 事項 | 停在哪 |
|---|---|---|
| **U-15** | **量比 `period` 不一致** | `calc_volume_ratio(df, period=5)` 預設 **5 日**，但 §4.1 評分表的呼叫端與 §3.6 的 `_vol_now_r` 用的是 **20 日均量**（`df2['volume'].tail(20).mean()`）。**兩個「量比」不是同一個東西，但共用同一組 `VOLUME_RATIO_*` 門檻。** 沒追哪個消費端拿到哪一個。 |
| **U-16** | **`HARD_STOP_LOSS_PCT=7.0` vs `STOP_LOSS_DEFAULT_PCT=8.0`** | 兩個不同值的停損門檻並存，畫面 help 文字同時列出「`-7%／-8%`」。**語意差別（硬停損 vs 預設停損？）本次未追。** |
| **U-17** | **`max_score` parquet 的 `score` 變成 0.5 級距** | `S1-2` 記錄 `score = [4.0, 3.0, 5.0]`（整數），本次實測 `[2.5, 2.5, 2.5, 1.5, 3.5]`。**`market_regime` 何時改成半分制、`max_score` 是否也跟著變 —— 完全沒查。** |
| **U-18** | **KD `.replace(0, 1)` 的實際觸發頻率** | **未實測**。連續 9 日 `high==low` 在台股（跌停鎖死）可能但罕見。**沒有量測。** |
| **U-19** | **`compute_atr` 缺 high/low 的實際觸發頻率** | 同上，**未量測**。哪些 fetcher 會給出只有 `close` 的 df，沒查。 |
| **U-20** | **`etf_quality.compute_etf_quality` 的星等** | §4.5 記的是 `etf_scoring_helpers.compute_etf_composite_score`（7 維）。但 `etf_quality.py` **另有一套星等映射**（同樣用 `ETF_RATING_*` 門檻）。**兩套的維度與權重是否相同，本次沒比對。** |
| **U-21** | **五桶 16 盞燈的「值從哪來」** | 本檔只寫了門檻與判定；**每盞燈的 value 由 `macro_helpers.compute_five_bucket_summary` 的 values dict 供給，那個 dict 怎麼組成沒有逐燈追**（`foreign_net` 寫死 None 是例外，因為有 `wired=False` 旗標）。⇒ **可能還有第二盞「其實沒接線」的燈沒被發現。** |
| **U-23** | **`evaluate_exit_signals` 的「三維未轉空」false claim（§6.3）** | 讀碼推導：三個 `*_hit` 在缺值時皆為 `False`，`score=0` → headline 走 `'（三維未轉空）'` 分支。**沒有實際餵三個 None 進去跑**，也**沒有查 UI 有沒有展開 `dims` 把 `'未掃描'` 顯示出來** ⇒ **實際畫面是否真的會誤導，未確認。** |
| **U-24** | **`compute_tech_bearish` 的 MA 週期 (5,20,60,240) 是 inline** | 沒有查全站是否另有 SSOT 常數（例如 `config.py:ANNUAL_MA=240` 就是 240，但這裡沒引用它）。**「這 4 個數字沒有 SSOT」是單組觀察，未窮舉。** |
| **U-22** | **畫面實機驗證** | **完全沒有。** 本檔查的是 **code 算式**；畫面上實際印出什麼數字、標什麼文案、哪些區塊預設收合，**沒有跑起來看過**（沙箱無 Streamlit 實機）。§4.2 「畫面會看到分數不會看到那個 18.0% 字串」是**讀 `render_health_score` 原碼推導的**，未實機確認。 |

### 9.4 唯讀紀律

| 項 | 狀態 |
|---|---|
| repo HEAD | 開工 `fab88a7` → 收工 `fab88a7`（未變） |
| `git status --porcelain` | 開工空 → 收工空 |
| 執行過的 git 指令 | 只有 `git log` / `git status` / `git rev-parse`（**唯讀**）。**未執行** `add` / `commit` / `merge` / `push` / `checkout` / `reset` / `stash` |
| 本次唯一的寫入 | `scratchpad/INDICATOR_SSOT.md`（本檔）＋ `scratchpad/_probe_ind.py` ＋ `scratchpad/_probe_unit.py`。**三者皆在 scratchpad，不在 repo 內。** |
| 探針性質 | 唯讀 —— 只 `import` L2 純函式並 `print` 回傳值。**不寫檔、不打網路。** 執行時 streamlit 印的 `No runtime found, using MemoryCacheStorageManager` 是 `@st.cache_data` 在無 runtime 下的正常降級訊息 |

---

## 附錄 A — 探針腳本

| 路徑 | 內容 |
|---|---|
| `scratchpad/_probe_ind.py` | `calc_health_score` 全缺 / 只有 df；`classify_stock_status_lamp` 四種 label；`classify_yield_zone` 九個分界點；`_norm` / `compute_etf_composite_score` 的 `0.0` vs `None`；`calc_sharpe` 樣本不足；`recommend_etf_action` 的 emoji / 中文耦合反例 |
| `scratchpad/_probe_unit.py` | `calc_fundamental_score` 的 `avg_div` 量綱反例（三組 元/股 × 現價 組合） |

## 附錄 B — 本檔與既有材料的關係

| 既有材料 | 本檔怎麼處理 |
|---|---|
| `S1-2_METRIC_SSOT.md` | **整合 + 複驗**。沿用其結構與多數判定；**更正 2 處**（§1.5 燈色順序判定；§2.10(b) 嚴重度已由該文件自行下修，本檔沿用）；**解決 1 個未驗項**（U-3 → 本檔 §5.1）；**複驗 1 個**（§2.2 `max_score` → 本檔 §3.3，問題仍在且列數已增） |
| `S1-1_DATA_WHITEPAPER.md` | **未重複** —— 資料來源歸 `DATA_LINEAGE.md` |
| `S1-6_COMPLIANCE_COPY_GUIDE.md` | 本檔 §8 沿用其「缺項填補測試」判準，**未重述文案規則** |
| `S2-ENG_SPEC.md` | 本次**未逐節比對**（見 §9.1 U-1） |
