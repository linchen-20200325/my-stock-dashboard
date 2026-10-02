# MACRO_MASTER — 總經指標盤點（五桶 16 盞燈）

> WD5 撰寫組產出｜2026-09-21｜分支 `claude/stock-dashboard-handoff-g9dtm0`
> 本檔是**現況盤點**，只描述「本 repo 現在有什麼、哪裡是壞的或空的」。
> 全檔不含投資建議、不含操作動作、不引用任何個人或機構背書。此免責全檔僅述一次。

## 0. 誠實邊界（先讀這段）

**⚠️ 客戶指定的那份「上週排程」不在本 repo。** 實測：`三維評分`／`候選指標`／`MACRO_MASTER`
三個關鍵字全 repo **0 命中**；「六層」僅 2 處命中且**都是別的東西** ——
`docs/v2/stage1/DATA_LINEAGE.md:206` 是「融資餘額」單一指標的 6 層資料**備援鏈**，
`docs/v2/spec/UI_PAGE_WHY.md:24` 是那一頁的 UI **版面**層。
⇒ **本檔不宣稱自己是「上週排程的那六層／那三維」——無從對照，宣稱即造假。**

**本檔改用的做法（三點）**
1. 分類改用**本 repo 實際存在的分類**：五桶 16 盞燈（`shared/macro_buckets.py:109`），**不是六層**。
2. 三個評分維度與 P0 的定義**由 AI 總管另立**，判準寫死於 §2。
   ⚠️ **三維與 P0 是總管提出的，非客戶原文**（標註方式比照 `CLAUDE.md` §-1.5.A-8 註 (d) 前例）。
   **客戶若另有定義，一句話即可推翻本檔重做。**
3. 依客戶長期指令，**中國相關指標不納入本盤點**（本 repo 確有其取數與門檻，本檔一律不列，連名稱不寫）。

## 1. 本 repo 的真實分類：五桶 16 盞燈 ＋ 2 條參考走勢（非燈）

`shared/macro_buckets.py:109` 逐字：`BUCKET_ORDER = ["long", "mid", "short", "chips", "news"]`

| 桶 | 盞數 | 燈 key |
|---|---|---|
| 🌳 `long` 長期／結構・景氣位階 | 3 | `health`、`ndc_signal`、`m1b_m2_gap` |
| 📈 `mid` 中期／景氣循環 3-12 月 | 6 | `ism_pmi`、`us_core_cpi`、`tw_export`、`bias_240`、`us10y`、`dxy` |
| ⚡ `short` 短線急殺／即時 risk-off | 3 | `vix`、`adl`、`fut_net` |
| 🧩 `chips` 籌碼／大戶定位日線 | 3 | `margin`、`jingqi`、`foreign_net` |
| 📰 `news` 新聞／系統性風險掃描 | 1 | `news_systemic` |
| **合計** | **16** | |

**兩條參考走勢不是燈**：`usdtwd` 新台幣匯率、`taiex` 加權指數，掛 `REFERENCE_BUCKET = "reference"`。
`shared/macro_buckets.py:436` 逐字：「**刻意不是** `BUCKET_ORDER` 裡的任何一個」、「**不算一盞燈**
—— 不進 x/16 分母、不進五桶 worst-of 彙總」。⇒ 本檔一律寫「16 盞燈 ＋ 2 條參考走勢」。

**彙總方式**：桶內 **worst-of**（`macro_buckets.py:aggregate_level`，紅>黃>綠，全 gray→gray），
**非加權合成**；**桶間無權重**（`grep BUCKET_WEIGHT` 全 repo 0 命中），`BUCKET_ORDER` 只是顯示序。

## 2. 三維評分判準（⚠️ 總管另立，非客戶原文）

| 維度 | ✅ | ⚠️ | ❌ |
|---|---|---|---|
| **D1 資料可得性** | 有 fetch，且多源賽跑或有備援鏈 | 有 fetch 但**單一來源**（該源失效即灰） | **無資料源**（無任何 fetch） |
| **D2 門檻 SSOT 健全度** | 具名常數住 `shared/` | **inline 裸數字**（有值但無 SSOT），或名數混用 | 無門檻，**或雙軌值不一致** |
| **D3 鑑別力** | 會隨狀態變化並區分 | 變化但區分度弱，**或接線過新／樣本不足尚無法判定** | **實測恆定**（畫面有燈、底下不動） |

⚠️ **D3 的證據強度要打折**：❌ 只在**有實測佐證恆定**時給；✅ 實為「**目前無反證**」，
不等於「已逐盞實測」。此限制依 `CLAUDE.md` §-1.5.A-7 據實標明。

**排序規則**：三維中 **❌ 越多越優先**。
**P0 ＝ 含任一 ❌ 的項目** —— 即「**畫面上看得到、但底下是壞的或空的**」，這類最會誤導使用者。

## 3. 16 盞燈逐盞評分

| 燈 | 資料源（檔:符號） | 門檻 SSOT | D1 | D2 | D3 |
|---|---|---|:-:|:-:|:-:|
| `health` 總經健康評分 | `src/compute/macro/macro_helpers.py::calc_traffic_light` | `macro_buckets.py:_HEALTH_YELLOW/_HEALTH_RED` | ⚠️ | ✅ | ✅ |
| `ndc_signal` NDC景氣對策燈號 | `src/data/macro/macro_snapshot.py::fetch_ndc_block` | **inline 裸數字** 32/38/23/16 | ⚠️ | ⚠️ | ✅ |
| `m1b_m2_gap` M1B-M2資金動能 | `macro_snapshot.py::fetch_m1b_m2_block` | **inline 裸數字** 1.0/0.0 | ⚠️ | ⚠️ | ✅ |
| `ism_pmi` 台灣PMI | `src/data/macro/macro_core.py::fetch_tw_pmi`（8 源賽跑） | `_PMI_YELLOW/_RED`（鏡像 `MACRO_THRESHOLDS['PMI']`） | ✅ | ✅ | ✅ |
| `us_core_cpi` 美國核心CPI YoY | `macro_snapshot.py::fetch_cpi_block` | `_CPI_YELLOW/_RED` | ⚠️ | ✅ | ✅ |
| `tw_export` 台灣出口訂單YoY | `macro_snapshot.py::fetch_export_block` | `shared/signal_thresholds.py:TW_EXPORT_YOY_BANDS` | ⚠️ | ✅ | ✅ |
| `bias_240` 年線乖離率BIAS240 | `macro_snapshot.py::compute_twii_bias` | **inline 裸數字** 10.0/20.0 | ⚠️ | ⚠️ | ✅ |
| `us10y` 10Y公債殖利率 | `macro_snapshot.py::fetch_us10y_block`（備援 `^TNX`） | `_US10Y_YELLOW/_RED` | ✅ | ✅ | ⚠️ |
| `dxy` 美元指數DXY | `src/data/daily/daily_data_fetchers.py::fetch_single('DX-Y.NYB')` | `_DXY_YELLOW/_RED` | ⚠️ | ✅ | ⚠️ |
| `vix` VIX恐慌指數 | `macro_snapshot.py::fetch_vix_block` | `_VIX_YELLOW/_RED` = 22/30 | ✅ | **❌** | ✅ |
| `adl` ADL漲跌家數比 | `daily_data_fetchers.py::fetch_adl` | 黃走 `MARKET_BREADTH_NEUTRAL_PCT`、**紅是 inline 35.0** | ⚠️ | ⚠️ | ✅ |
| `fut_net` 外資期貨淨口 | `src/data/macro/leading_indicators.py::finmind_fut_oi` | `FOREIGN_FUTURES_MEDIUM/HIGH_RISK_THRESHOLD_LOTS` | ⚠️ | ✅ | ✅ |
| `margin` 融資餘額 | `daily_data_fetchers.py::fetch_margin_balance`（6 層 fallback） | `MARGIN_BALANCE_WARN/OVERHEAT_THRESHOLD_YI` | ✅ | ✅ | **❌** |
| `jingqi` 旌旗指數 | `src/services/jingqi_calc.py::compute_and_store_jingqi` | **inline 裸數字** 60.0/40.0 | ⚠️ | ⚠️ | ✅ |
| `foreign_net` 外資現貨淨買賣 | **無** —— `macro_helpers.py:1841` 對此 key 呼叫 `_unwired("foreign_net")` | inline 0.0/-200.0 | **❌** | ⚠️ | **❌** |
| `news_systemic` 系統性風險新聞數 | `src/data/news/news_fetcher.py::fetch_macro_news` | `NEWS_SYSTEMIC_YELLOW/RED_COUNT` | ⚠️ | ✅ | ✅ |

## 4. 燈號登記表以外的兩類項目

**(a) 已有取數、未登記為燈的候選**（D1 皆 ✅／⚠️，D3 因未接線無從判定）

| 項目 | 取數（檔:符號） | 門檻現況 |
|---|---|---|
| Fed Funds Rate | `macro_snapshot.py::fetch_fed_funds_block` | 無燈（現供 CPI×Fed 雙頂偵測用） |
| 台灣 CPI YoY | `src/data/macro/tw_macro.py::fetch_tw_cpi_yoy` | `MACRO_THRESHOLDS['TW_CPI_YOY']` 有值，無燈 |
| 台灣失業率 | `tw_macro.py::fetch_tw_unemployment` | `MACRO_THRESHOLDS['TW_UNEMP']` 有值，無燈 |
| 央行重貼現率 | `tw_macro.py::fetch_cbc_discount_rate` | `MACRO_THRESHOLDS['CBC_RATE']` 有值，無燈 |
| 市場寬度（漲跌家數） | `tw_macro.py::fetch_twse_breadth`（≠ `fetch_adl`，是另一支函式） | 未登記 |

**(b) 常數存在但無資料餵入（死門檻，D1 ❌）**
`MACRO_THRESHOLDS` 的 `YIELD_10Y2Y`、`YIELD_10Y3M`、`FED_BS_YOY` —— 全 repo 僅
`src/ui/tabs/tab_edu.py` 教學字串命中，**無任何 fetch**。

## 5. P0 清單（含 ❌ 者，依 ❌ 數排序）

### P0-1｜`foreign_net` 外資現貨淨買賣 —— **D1 ❌ ＋ D3 ❌（雙 ❌，最優先）**
`src/compute/macro/macro_helpers.py:1841` 對此 key 呼叫 `_unwired("foreign_net")`，**未呼叫任何 fetch**
⇒ `wired=False`，**恆灰 ⬜**。它佔 `chips` 桶 3 盞中的 1 盞、佔 x/16 分母 1 席，但**永遠不提供資訊**。
**風險**：使用者看到「籌碼桶 3 盞」，實際只有 2 盞在運作；分母被稀釋且不可見。

### P0-2｜`margin` 融資餘額 —— **D3 ❌（實測恆定）**
`shared/macro_buckets.py` 的 `spec.discriminative=False`，**實測長期穿透 `MARGIN_BALANCE_WARN` 與
`MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI` 兩線恆紅**。取數健全（6 層 fallback，D1 ✅）、門檻有 SSOT（D2 ✅），
壞的是**門檻位置**：一盞永遠紅的燈等於沒有燈，且會把 `chips` 桶的 worst-of 永久釘在紅。
**風險**：`chips` 桶彙總被單盞恆紅綁架，其餘盞的變化在桶層級看不到。

### P0-3｜`vix` VIX恐慌指數 —— **D2 ❌（雙軌門檻不一致）**
`shared/macro_buckets.py` 的 `_VIX_YELLOW/_RED` = **22/30**，
`src/compute/risk/risk_radar.py` 的 `VIX_WARN_LEVEL` = **25.0**／`VIX_PANIC_LEVEL` = 30.0。
⇒ **同一個 VIX 值在兩個畫面可能一黃一綠**（22–25 區間）。
⚠️ **不要誤判成另一組**：`macro_buckets` 與 `macro_core.MACRO_THRESHOLDS` 是**鏡像且值一致**，
由 `tests/test_macro_buckets.py::test_mirror_matches_macro_core` 守護，**那組不是漂移**。真正的雙軌在此。

### P0-4｜三個死門檻 —— **D1 ❌（常數存在、無資料源）**
`YIELD_10Y2Y`、`YIELD_10Y3M`、`FED_BS_YOY` 定義在 `MACRO_THRESHOLDS`，全 repo 唯一命中是
`src/ui/tabs/tab_edu.py` 的教學字串。**風險**：門檻看起來「有在用」，實際無任何 fetch 餵入；
日後若有人據此以為該指標已接線，會建立在假前提上。

**⛔ P0 到此為止，依指示停下。**

## 6. P1 / P2（僅記存在，本檔不展開）

- **P1（含 ⚠️、無 ❌，共 13 盞 ＋ 5 候選）**：`ndc_signal`／`m1b_m2_gap`／`bias_240`／`jingqi`
  的 inline 裸門檻、`adl` 的名數混用、`us10y`／`dxy` 的 v19.175 新接線待觀察、
  其餘 D1 ⚠️ 單一來源那一群（`health`／`us_core_cpi`／`tw_export`／`fut_net`／`news_systemic`），
  以及 §4(a) 五個已有取數但未登記為燈的候選。
- **P2（三維全 ✅）**：`ism_pmi` 一項。
