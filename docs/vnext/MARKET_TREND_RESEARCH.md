# 大盤／市場趨勢研究與盤點（Market Trend Research）

> **定位**：研究與盤點文件；⛔ **不是實作授權、不帶 Decision 效力**；與 `docs/DECISIONS.md`／`CLAUDE.md` 牴觸時以後者為準（`PROJECT_RULES.md` §0.3 同 Blueprint 的處理）。
> **量測**：HEAD `08272e56`（#902），2026-10-22。
> **證據等級**：三組唯讀盤點＋總管抽查原碼（總管轉述彙整，撰寫組未重跑）；**單組結論，未經第二組完整驗證**（`CLAUDE.md` §-2 規則 6）—— 引用時請保留此標示，⛔ 不得當成已複驗事實或後續動作的前提。
> **客戶裁示**只在 `docs/DECISIONS.md` **DEC-071**（DR-2026-10-22-4）；未完成工作只在 `docs/BACKLOG.md` 第 5.1.6 節（`MT-*`）。本檔只放盤點事實與研究框架。
> **分層標示**（每節開頭都會寫）：〔客戶裁示 DEC-071〕／〔repo 事實〕（讀 main 原碼，HEAD `08272e56`）／〔Research Framework／Candidate〕（外部研究，⛔ 非 production rule、⛔ 不得標 Approved）／〔推論〕。
> ⛔ 本檔所有「位置」只寫 `檔案::符號`，不寫行號（`CLAUDE.md` §8.2.A.0 規則 1）。

---

## 1. 客戶已裁示的方向〔客戶裁示 DEC-071〕

只摘要；逐字原文與「不是什麼」見 `docs/DECISIONS.md` **DEC-071**。

- 新 UI 現有視覺設計方向維持、不退回舊 UI；舊 UI 是「功能／規則／資料／判讀邏輯」的參考來源，原則「保留 → 整合 → 重新編排 → 必要時收進次層／展開區」，只有確認過時、重複或客戶明確裁示後才可刪除。
- 第一頁不再以「今天」為核心，核心是「大盤＋市場趨勢」；導航名稱只有**方向**（直接投資語意），⛔ 未定案。
- 第一頁問題鏈：**大盤** → 台股趨勢 → 國際趨勢 → 風險 → 曝險／操作環境；⛔ 不新增總分，優先重用既有機制。
- 「市場位階」≠「指標危險度」，不得硬合成一個分數或一顆燈；Risk Cap 是曝險上限，不等於台股趨勢。
- 外部研究資料（蕭碧燕老師）只保留「台股趨勢＋國際趨勢」；除非 GitHub 已有正式 DEC／規格，否則不得升格為 production rule。
- EPS × PE 是大盤分析的重要方法之一，**不是**整個趨勢判斷。
- 本輪只盤點與落盤，**不授權 layout change**。

---

## 2. GitHub 既有事實〔repo 事實，HEAD `08272e56`；單組盤點＋總管抽查〕

### 2.1 現行機制各自回答什麼

| 概念 | 回答的問題 | 主要輸入 | 規則位置 | 正式出處 |
|---|---|---|---|---|
| **市場位階** | 偏多／震盪／偏空（bull／neutral／bear／unknown） | warroom `effective_regime`：趨勢面、大盤評分、健康分、外資期貨淨口；退路依序：重跑 arbiter → `macro_state.json` 的 `market_regime`（Risk Cap 分級）→ unknown | `shared/regime_arbiter.py::arbitrate_regime`（決策樹）；L3 `get_macro_state`；UI 入口 `allocation_service.get_macro_regime` | SPEC §16.5／§16.6；`AUD-C22`、`VN-23`、`VN1-C-REGIME-RESOLVER`；⚠️ DECISIONS 無正式 DEC |
| **指標危險度** | 16 盞燈有沒有踩到危險門檻（**不含多空方向**） | 16 燈（見 2.3） | `shared/macro_buckets.py::BUCKET_DANGER_SPECS`、`::classify_danger`、`::aggregate_level`；總燈 `tab_macro_v2.overall_verdict`（worst-of） | SPEC §11／§16.3／§16.5；DEC-023；`BP-DR-19`；⚠️ 正名為客戶 2026-08-27 裁示，只在程式註解與 SPEC，DECISIONS 無 DEC（`MT-GAP-01` (b)） |
| **建議持股 %** | 建議持股區間 | `min(姿態油門, 天花板)`；天花板＝Risk Cap 上限、VIX 否決（20→30%、30→10%）、三環第一環（VIX≥20 或期貨≤−15000→20%） | `shared/allocation_decision.py::build_allocation_decision`、`shared/position_throttle.py`；新頁閘門 `src/ui/views/risk_cap_gate.py` | DEC-040、044、048、053；`BP-DR-21` |
| **大盤評分** | 趨勢強弱分數 | ^TWII MA60／MA120 連 3 日＋斜率、外資現貨、ADL（M1B−M2 停用） | `src/services/market_strategy.py::market_regime` | 無正式定義；⚠️ `ARCHITECTURE.md` 描述與程式不符（`MT-GAP-01` (h)） |
| **趨勢面** | 只看技術面多空 | MA120 連 3 日＋斜率 | 同上 | 無正式定義；為市場位階的輸入 |
| **健康分（大盤）** | 趨勢廣度分數 | 旌旗（ADL 5 日均）×0.6＋大盤評分%×0.4 | `macro_helpers.calc_traffic_light`（⚠️ repo 無 `compute_macro_health` 這個函式，`CLAUDE.md` §4.3 的名稱已過時） | SPEC §11 |
| 6-factor health score | ⚠️ **個股**技術健康度，**不是大盤** | — | `scoring_helpers.calc_health_score` | SPEC §20.3 |
| **Risk Cap v2** | 建議持股的硬天花板（曝險上限） | 見 `docs/PROJECT_STATE.md` §4 | `src/services/macro_state_locker.py::calculate_system_state` | DEC-041～053、DEC-070 |

**Risk Cap 不回答的事**〔repo 事實〕：不看 MA60／MA120 趨勢（只有 veto 3 用到 MA5 bool）；不看廣度、外資現貨、融資、NDC、CPI、美債、DXY；不產生建議持股本身（只是 `min()` 的一條）；新 UI 路徑下**不決定**市場位階（除非 warroom 不可用才退到 `macro_state.json`）。薩姆規則無資料來源、永不觸發。計分門檻多為 inline 數字。

### 2.2 市場位階 ≠ 指標危險度（程式與 UI 文案證據）

- `src/ui/views/page_today.py::PARALLEL_DISCLOSURE`：「下面兩顆燈不是同一個量，也刻意不合成第三顆」。
- `tab_macro_v2.overall_verdict` docstring 的正名說明；今天頁兩張卡分開取數。
- 兩者共用的輸入只有 health 與 fut_net。
- ⚠️ 用語撞名：「位階」另有三種用法（拐點群組乖離率、`classify_long_term_regime` 長期總經位階、cross_ai「目前總經位階」）；`market_regime` 同名三義（Risk Cap 檔欄位、`market_strategy.market_regime()` 趨勢函式、`get_macro_state()['regime']` arbiter）（`MT-GAP-01` (c)）。

### 2.3 指標危險度 16 盞燈

| 桶 | 燈 |
|---|---|
| 長期 | health、ndc_signal、m1b_m2_gap |
| 中期 | ism_pmi（⚠️ 實為**台灣** PMI）、us_core_cpi、tw_export、bias_240、us10y、dxy |
| 短線 | vix、adl（⚠️ 不是真實漲跌家數，由 ^TWII 漲跌幅估算，`MT-GAP-01` (f)）、fut_net |
| 籌碼 | margin（`discriminative=False`）、jingqi、foreign_net |
| 新聞 | news_systemic |

### 2.4 其他仍在線上的 regime／判讀模型（皆無正式定義）

cross_ai ①「目前總經位階」與 ⑤「結論」投票；`classify_long_term_regime`（12 個月景氣 4 態）＋雙速合議；`V4StrategyEngine.check_macro_veto`；旌旗 regime；`market_score.status`；國際盤領先指標 `shared/global_lead_markets.py`（只用於推播與 page_hold，**另一組持股數字，不經 `get_allocation`**，`MT-GAP-01` (g)）；短線雷達 9 燈（`src/compute/risk/risk_radar.py`）。

### 2.5 重複計分／多重門檻（「重複」屬〔推論〕）

- ^TWII 價格同時進入：大盤評分、趨勢面、bias_240、adl、jingqi、健康分、Risk Cap BIAS240 與 MA5。
- 外資期貨 6 處門檻各異：燈 −10000／−20000、arbiter −30000、Risk Cap −35000、三環 −15000、v4 veto（`MT-GAP-01` (d)）。
- VIX 約 8 套門檻；PMI、BIAS240 多處使用。
- `MACRO_ALERT_RULES` 與 `MACRO_THRESHOLDS` 兩套 CPI／US10Y／DXY 門檻並存（`MT-GAP-01` (e)）；`MACRO_THRESHOLDS` 部分 key（HY_SPREAD、YIELD_10Y2Y、YIELD_10Y3M、M2_YOY、FED_BS_YOY）單次 grep 未見消費端（⚠️ **非**已確認死碼）。
- ⛔ 本節只是盤點：**不提出合併、不提出新權重**；任何去重或調和屬 Decision Gate（`PROJECT_RULES.md` §4 #1／#2）。

### 2.6 新 UI 現況（B）

- 主導航唯一來源 `shared/ia_nav.py::PAGE_LABELS`：🚦 今天／🔍 找標的／🔬 查一檔／💼 我的持股／📖 憑什麼（5 頁），側欄 radio 入口（DEC-018）。Blueprint §4.2 目標為「今天／機會／持股／我的」（`BP-DR-01`；DEC-062 Q1＝B 只核准**送審範圍**，線框未拍板）。
- 第一頁「今天」元件：狀態列（交易日、總經、Sheet 綁定）；結論三卡並排 ①建議持股（Risk Cap gate）②指標危險度 ③市場位階；更新表單；三欄摘要（位階／動能／風險，**動能未接線**）；今日關鍵橫幅（門檻層只有舊 `section_mid` 會寫 `macro_alerts` → 新 UI session 結構上永遠未評估）；今天該做的事、AI 摘要（**未接線**）；葉 2 五桶摘要＋16 燈逐桶卡（值、門檻帶、方向）。**本頁無任何圖表。**

### 2.7 舊 UI 有、新版第一頁未承接或部分承接的大盤判讀邏輯（C）

> 判定方法：新頁 grep 無命中、無對應呼叫；**未實機**。逐項處置（保留／整合／重新編排／收次層）尚未提案，見 BACKLOG `MT-MAP-OLDUI`。⛔ 刪除須客戶裁示（DEC-019／DEC-020）。

1. 拐點六面向＋CPI×Fed 雙頂回落（`src/ui/tabs/macro/section_state.py`）
2. 均線位階：MA60／MA120 彎折、月線乖離；新版「動能」格未接線
3. 熱錢三角：外資 × 匯率（`hot_money.py`）
4. 國際盤：美股三大指數、各區域股市、全球資金流向／風險情緒、科技巨頭與 SOX（`section_long.py`）
5. 台股大盤 K 線、OTC 櫃買、台幣卡（`section_long.py`）
6. 總經指南針：S&P500 對 60MA（`src/ui/render/app_render.py::render_macro_compass`）
7. 全球風險 10 燈＋雙速合議（`helpers._render_global_risk_bucket`）；中國拖累（`helpers._render_china_drag_panel`）
8. 籌碼細項：投信／自營大盤淨額、選擇權 PCR、先行指標表、韭菜指數、外資投信同買同賣、v4 總經否決燈、sleeves（`section_chips.py`）
9. 基本面否決清單、三環 SSS／A／B 火力分級（`section_mid.py`；只有天花板進 allocation）
10. 規則決策五維（`section_cross_ai.py`）
11. 今日作戰室與月虧損停機（`section_warroom.py`）；News AI 總裁決與新聞桶（`section_news_ai.py`）；AI 總經摘要
12. 紅綠燈分項（趨勢評分、健康分、信心）；Fed Funds 卡
13. 今日關鍵門檻層在純新 UI session 永遠未評估（`macro_refresh_service.UNTOUCHED_BLOCKS`）
14. 走勢圖、門檻線、K 線、台幣與加權參考走勢、16 燈表格搜尋（`tab_macro_v2.py`）
15. 個股與 ETF 頁的總經背景（`macro_stock_link.py`）

**已承接**：建議持股油門（卡 ① 推導依據）、五桶與 16 燈、板塊熱力圖／資金潮汐（在找標的頁，非第一頁）。
⚠️ **不一致**〔推論〕：Blueprint §4.3 把「🌍 總經／🚦 總經 v2」標為「已併入新 UI」，與上列部分／未承接不一致（`MT-GAP-01` (a)；本批 ⛔ 不改 Blueprint）。
⚠️ **未查證**：`tab_macro_v2` 與 `tab_macro` 是否重複（`CLAUDE.md` §8.3 既有登記）。

---

## 3. 外部研究框架〔Research Framework／Candidate，⛔ 非 production rule〕

> **來源**：客戶提供之外部研究資料（蕭碧燕老師）；依 DEC-071 只保留**台股趨勢＋國際趨勢**部分。⛔ 未收錄基金配置與個別商品。
> ⛔ 本節是外部研究方法與觀察框架，**除非 GitHub 已有正式 DEC／規格，否則不得直接升格為 production rule**（客戶原文，DEC-071）；本節任何內容 ⛔ 不得標 Approved。
> ⚠️ **案例值警示**：本節出現的 17%、週 K／D 約 50、4 萬／4.5 萬／4.8 萬、EPS 成長 35%、PE 15～21 倍、39,856～56,862 —— 一律是**該份研究當時假設下的案例值，⛔ 不得作為 production threshold**。保存的是**方法論**，不是數字。

### 3.1 台股趨勢

**T1｜技術面：短期修正 vs 長期趨勢**
- 方法論：「短期修正」與「長期趨勢」必須分開判讀；不要因為短期下跌就直接把長期趨勢翻成空頭。
- 案例（⚠️ 案例值，非門檻）：週線大盤最大跌幅約 17%、週 K／週 D 回到約 50，在當時多頭環境中被解讀為合理修正；同時區分短期壓力與長期多頭格局（4 萬／4.5 萬／4.8 萬為該資料當時的點位情境）。

**T2｜獲利面：EPS × PE 大盤估值矩陣**
- 方法論：「台股 EPS × 本益比 → 加權指數情境矩陣」，是**台股大盤／台股趨勢的重要分析方法之一**。
- ⛔ **不是整個趨勢判斷**：它只是估值面，必須與技術（T1）、籌碼（T3）、產業獲利（T4）、國際（I1）及既有市場位階／危險度／Risk Cap 一起讀。
- 案例（⚠️ 案例值，非門檻）：樂觀版本 EPS 預估成長 35% 以上、PE 計算區間 15～21 倍、加權指數高點情境約 39,856～56,862 點。
- 未來研究方向（客戶原文要點）：如何使用**可追溯、可更新**的 EPS 預估與合理 PE 情境形成大盤估值區間 —— 不是把簡報當年的數字永久寫死（資料缺口見 §4，BACKLOG `MT-RES-EPSPE`）。

**T3｜籌碼面：外資**
- 方法論：「外資資金方向是台股趨勢的重要觀察面向。」台股趨勢不能只剩 EPS 與技術面。
- ⛔ 不得把「外資是阻力」永久寫死；須與 repo 現有外資現貨、外資期貨、market regime、Risk Cap hard veto 做**責任邊界盤點**，避免重複計分（現況見 §2.5）。

**T4｜產業／獲利趨勢：CSP／AI CAPEX → 台股企業獲利**
- 正面傳導：大型 CSP 資本支出上修 → AI 供應鏈需求 → 台灣企業盈餘預期上修 → 台股整體獲利展望受支撐。
- **反面風險（必須一併保存）**：CSP CAPEX 過高 → 自由現金流下降 → 若投資無法轉換成營收／獲利 → 可能成為產業與市場風險。
- ⛔ 不只保存樂觀敘事。

### 3.2 國際趨勢

**I1｜殖利率＋領先指標「雙變數方向判讀」**
- 歷史比較：
  - 美國網路泡沫：美債殖利率明顯上升＋領先指標反轉向下 → 之後股市進入重大修正。
  - 日本泡沫：日本長債殖利率升至高位＋領先指標接近／形成高點 → 資產價格之後進入長期調整。
- 方法論核心：「殖利率＋領先指標一起看。」核心不是單看美股漲跌，也不是單看 VIX。
- **看方向，不看水位**：⛔ 不是看到殖利率高就直接判定泡沫／空頭。
- 來源當時的判讀（⚠️ 當時情境，非規則）：殖利率已由高點下降＋領先指標由谷底回升 → 與歷史泡沫破裂前的組合不同，**當時偏向軟著陸環境**判讀。
- ⛔ 不得把該簡報當時的數字寫成永久 threshold；若要成為判讀規則＝Decision Gate（新資料語意，`PROJECT_RULES.md` §4 #2）。

### 3.3 國際 → 台股的傳導鏈

```
國際利率／景氣
↓
全球企業投資與風險偏好
↓
AI／CSP CAPEX
↓
台灣供應鏈營收與獲利
↓
台股 EPS 預估
↓
EPS × PE 大盤估值
↓
再與台股技術／籌碼／市場位階／Risk Cap 一起閱讀
```

- 用途：讓「國際趨勢」與「台股趨勢」不是兩個互不相干的資料櫃。
- ⛔ 這是**資訊架構與研究關係**，**不授權建立單一總分公式**（客戶原文，DEC-071）；⛔ 不得把鏈上各環加權成一個新分數。

---

## 4. Mapping 表：研究框架 → repo〔repo 事實＋狀態判定；單組〕

> 狀態**只能**用：已存在，可重用／已存在但新版漏接／部分存在／Research Candidate／缺資料／需要 Decision Gate（客戶原文第九節）。每列只放一個狀態；條件式附註移到「備註」欄。

| 研究框架 | repo 現有資料 | repo 現有 rule | 舊 UI | 新 UI | 狀態 | 備註 |
|---|---|---|---|---|---|---|
| T1 長期趨勢／均線位階 | ^TWII 日 OHLC 歷史 `data_cache/twii_ohlcv.parquet`（2006 起，cron） | `compute_twii_bias`（MA20／60／120／240、bias）；`market_regime` MA60／120；bias_240 燈 | 有 | bias_240 燈＋方向；市場位階卡 | 已存在，可重用 | — |
| T1 短期修正：指數回檔／最大跌幅 | 同上（可 resample 週線） | 指數層級無回檔計算（`calc_mdd` 只用於 ETF） | 無 | 無 | 部分存在 | 加判讀門檻＝需要 Decision Gate（§4 #1） |
| T1 週 K／D | 同上 | `calc_kd` 為日線、用於個股；指數週 KD 無 | 個股 | 個股 | 部分存在 | 若加判讀門檻＝需要 Decision Gate（§4 #1） |
| T2 台股整體 EPS／EPS 預估 | 無指數 EPS、無預估；只有個股歷史季 EPS（FinMind／MOPS，含全上市彙總 `t163sb04`） | 個股 EPS 檢查 | 個股 | 個股 | 缺資料 | 新來源＝Decision Gate（§4 #3）；自行彙總＝新公式（#1）＋新語意（#2）；〔推論〕MOPS 全上市彙總可合成「已實現 EPS」，但不是框架要的「預估 EPS」 |
| T2 大盤本益比 | 無；只有個股 PE／PB 每日快照（TWSE BWIBBU_d、TPEX），未存歷史 | 個股 PE 篩選 | 選股網 | 找標的／查一檔 | 缺資料 | 同上 |
| T2 EPS×PE → 指數情境矩陣 | 無 | 無 | 無 | 無 | Research Candidate | 相鄰 `VN-32`／`BP-RC-07`（Scenario）；前置＝上兩列資料 |
| T3 外資現貨水位 | TWSE BFI82U／FinMind；歷史 `data_cache/finmind_inst.parquet`（口徑 2017-12-18、Z40 兩次分段） | foreign_net 燈；大盤評分 +1 | `section_chips` | foreign_net 燈（水位） | 已存在，可重用 | — |
| T3 外資方向／連續日數 | `tw_macro.fetch_foreign_consecutive_days` 等 | 連續日數反轉 | 拐點面板 | 方向列刻意標「無資料」 | 已存在但新版漏接 | 接法涉口徑分段＝資料語意（§4 #2）；〔推論〕`finmind_inst.parquet` 分段不可直接當同一序列 |
| T3 外資期貨 | FinMind TX／TAIFEX | fut_net 燈；Risk Cap Required Core＋veto 3 | `section_chips` | fut_net 燈；Risk Cap gate | 已存在，可重用 | 門檻 6 處並存（§2.5） |
| T4 CSP 資本支出 | 無 | 無 | 無 | 無 | 缺資料 | 新來源＝Decision Gate（§4 #3） |
| T4 AI 供應鏈需求代理 | 只有股價：^SOX、MSFT／GOOGL／NVDA／AMD／AVGO／TSM（`daily_checklist.TECH_MAP` 等） | SOX／NVDA 點火條件、族群情緒文字 | `section_long`／`section_mid` | 無 | 部分存在 | 價格動能，**不是** CAPEX |
| T4 台灣企業營收／盈餘預期 | 個股月營收、全市場月營收批次、出口 YoY | tw_export 燈；缺貨選股；個股 capex_intensity | 有 | tw_export 燈；選股 | 部分存在 | 無全市場彙總與預期值 |
| T4 反面：CAPEX 過高 → 自由現金流 | 無 | 無 | 無 | 無 | 缺資料 | — |
| I1 美國長天期殖利率 | FRED DGS10（L1 只回單點）、risk_radar 取 120 筆、^TNX 約 90 天 | us10y 燈只看水位；risk_radar 日衝擊；方向刻意「無資料（不混源）」 | 走勢線、雷達 | us10y 燈（水位） | 部分存在 | 方向判讀＝新資料語意，需要 Decision Gate（§4 #2）；〔推論〕DGS10 歷史技術上可取得，但會改變「不混源、單點」既有設計 |
| I1 日本長債殖利率 | 無 | 無 | 無 | 無 | 缺資料 | 新來源＝Decision Gate（§4 #3） |
| I1 美國領先指標（LEI／OECD CLI） | 無美國 CLI／LEI；只有中國 OECD CLI、OECD 美國商業信心當 PMI 備援 | 中國 CLI 分級 | 中國拖累面板 | 無 | 缺資料 | 新來源＝Decision Gate（§4 #3） |
| I1 美國 ISM PMI | `macro_core.fetch_ism_pmi` 存在，production 0 caller | 無（燈 key `ism_pmi` 實為台灣 PMI） | 無 | 無 | 部分存在 | — |
| I1 台灣景氣領先指標（NDC） | FinMind TaiwanBusinessIndicator `leading` 欄 | `tw_macro.fetch_ndc_leading_index` 6M 平滑＋拐點；ndc_signal 燈 | 拐點面板 | 只有 ndc_signal 燈；領先指標 6M 未接 | 已存在但新版漏接 | — |
| I1 雙變數方向組合（殖利率×領先指標） | 美國側兩項皆不全 | 無 | 無 | 無 | Research Candidate | 若成判讀規則＝需要 Decision Gate（§4 #1／#2） |
| 鏈：全球風險偏好 | VIX、HY OAS、DXY、熱錢、N225／HSI | vix、dxy 燈；risk_radar；flow_engine | 有 | vix、dxy 燈 | 部分存在 | 「全球企業投資」無資料 |
| 鏈：台股 EPS 預估 → 估值 | 無 | 無 | 無 | 無 | 缺資料 | 同 T2 |
| 鏈：再與技術／籌碼／市場位階／Risk Cap 一起看 | 元件皆存在 | 有 | 有 | 今天頁 | 已存在，可重用 | 元件可重用；把框架疊為 Context／Core＝需要 Decision Gate（DEC-009；Context 升 Core 或 hard veto 須客戶裁示） |

---

## 5. 大盤／市場趨勢頁的問題鏈〔客戶裁示 DEC-071 ＋ repo 事實對映〕

客戶原文（DEC-071）：「不要只寫「台股趨勢／國際趨勢」而把「大盤」漏掉。」第一頁核心問題鏈與 repo 既有機制的**對映**（對映為撰寫組讀法、單組；⛔ 不是線框、不是 layout 授權）：

| 問題鏈 | 對映的既有機制〔repo 事實〕 | 研究框架補充〔Candidate〕 |
|---|---|---|
| ① 現在的**大盤**是什麼狀態？ | 大盤評分、趨勢面、健康分（大盤）、市場位階卡 | — |
| ② **台股趨勢**怎麼走？ | 市場位階（多空）、趨勢面、bias_240、外資現貨／期貨燈 | T1～T4 |
| ③ **國際趨勢**怎麼走？ | vix、dxy、us10y 燈；risk_radar；舊 UI 國際盤（新版未承接，§2.7） | I1、§3.3 傳導鏈 |
| ④ 目前有哪些**風險**？ | 指標危險度（16 燈 worst-of） | T4 反面風險 |
| ⑤ 對**曝險／操作環境**代表什麼？ | Risk Cap（曝險上限）、建議持股＝min(姿態, 天花板) | — |

**硬限制（DEC-071）**
- ⛔ **不新增總分**；優先重用既有機制。
- **各機制責任分離**：
  - 市場位階＝多空／趨勢；
  - 指標危險度＝風險門檻是否踩到，**不含方向**；
  - Risk Cap＝曝險上限，**不等於台股趨勢**；
  - 建議持股＝`min(姿態, 天花板)`。
- ⛔ 不得為了新版 UI 簡化而把市場位階與指標危險度硬合成一個分數或一顆燈。
- 實際畫面怎麼排＝線框 Gate（`MT-WIREFRAME`；DEC-003 草稿先行）。

---

## 6. Data ≠ AI〔Approved：DEC-027；`PROJECT_RULES.md` §13〕

- 資料層負責客觀資料取得、驗證、標準化、provenance；Rule Layer 執行正式規則；Decision Layer 形成正式判斷；AI 只負責解釋。
- **missing ≠ 0；unavailable ≠ neutral；not evaluated ≠ safe。**
- EPS、PE、殖利率、領先指標、外資、CSP CAPEX 等資料若未取得，⛔ **不得由 AI 猜值**；也不得以研究案例值（§3）代填。
- 新資料來源、新 API／MCP 接入 production 資料鏈＝Decision Gate（`PROJECT_RULES.md` §4 #3／#4）。

---

## 7. 未驗證與盲點（依 `CLAUDE.md` §-2 規則 6 誠實揭露）

1. **全部未實機**：§2.6、§2.7 由讀碼與 grep 判定，未啟動新／舊 UI 實測。
2. **單組 grep**：「新版未承接」「查無既有 ID」「單次 grep 未見消費端」都是單組結論，⛔ 不得讀成「全都查過了」。
3. **`tab_macro_v2` vs `tab_macro` 是否重複**：未查證（`CLAUDE.md` §8.3 既有登記）。
4. **Blueprint §4.3 標示不一致**：「總經／總經 v2 已併入新 UI」與 §2.7 盤點不一致（〔推論〕；`MT-GAP-01` (a)；本批不改 Blueprint）。
5. **線上可用性未測**：FinMind／TWSE／FRED 等來源在現行部署的實際可得性、OECD／LEI 等候選來源是否可取得，皆未測。
6. **重複計分**（§2.5）屬推論，未逐條比對是否真的進入同一決策。
7. **外部研究資料**：只以客戶轉述的要點收錄，撰寫組未見原始簡報；案例值僅為紀錄，未驗證。
