# 階段1 交付物 #1 — 可用資料庫白皮書

> **產出日**：2026-09-14｜**產出者**：執行 AI（單組）｜**狀態**：⚠️ **單組結論，未經第二組獨立驗證**（§-2 規則 6）
> **範圍**：`my-stock-dashboard`（台股/ETF，可寫）＋ `my-fund-dashboard`（基金，唯讀 clone）
> **紀律**：全程唯讀。量不到的一律寫「量不到」，**沒有任何數字是推測填入的**（§1）。

---

## 0. 方法與證據等級

### 0.1 三種證據等級（全文每個數字都標）

| 標記 | 意義 | 可信度 |
|---|---|---|
| **【實測】** | 本次在沙箱內實際執行程式算出來的（讀 parquet／AST 解析／curl） | 高，但只覆蓋**本地快照**，非 production 全量 |
| **【引用】** | 從 repo 內 code 註解／docstring 抄出來的既有實測值，**不是我量的** | 中，取決於原記錄者，且可能過期 |
| **【查不到】** | 沙箱打不到／repo 內無記錄 | — **不填合理值** |

### 0.2 實際做了什麼

1. **讀實體檔，不抄文件**：對兩站 `data_cache/` + `cache/` 全部 33 個檔（28 + 5，另 1 個 NAV json）逐檔 `read_parquet` / `json.load`，逐欄算 null 率**與空字串率**（空字串不會被 `isna()` 抓到，是本次多抓出的一類缺漏）。
2. **AST 解析 `data_registry.py`**：不 import（避免 side-effect），用 `ast.literal_eval` 取出全部 78 筆宣告式來源。
3. **外部連線實測**：對 4 個代表性 endpoint 跑 `curl`，**全部 `http=000`**（連線層失敗），故**所有冷／熱延遲一律無法量測**。
4. **憲法對帳**：把 `CLAUDE.md §2.1 / §2.4 / §4.1` 逐條拿去 grep 實際常數位置。

### 0.3 沙箱外部連線實測結果【實測】

| Endpoint | HTTP | 耗時 |
|---|---|---|
| `openapi.twse.com.tw/v1/exchangeReport/FMTQIK` | **000** | 0.278 s |
| `query1.finance.yahoo.com/v8/finance/chart/^TWII` | **000** | 0.273 s |
| `api.finmindtrade.com/api/v4/data` | **000** | 0.314 s |
| `fred.stlouisfed.org/graph/fredgraph.csv?id=CPILFESL` | **000** | 0.286 s |

`000` = 連線根本沒建立（非 4xx/5xx）。**結論：本白皮書的「冷／熱載入延遲」欄位一律為【引用】或【查不到】，沒有一個是我量的。**

---

## 1. 台股站（my-stock-dashboard）

### 1.1 來源總覽【實測】

`src/data/core/data_registry.py` 的 `DATA_REGISTRY` = **78 筆**（AST 解析）。

| 維度 | 分布 |
|---|---|
| **分類** | 台灣總經 16、籌碼 12、個股財報 12、國際金融 8、台股大盤 8、ETF/基金 6、中國總經 5、新聞 RSS 4、三方備援 4、美國總經 2、AI 1 |
| **頻率** | daily 40、monthly 22、event 10、quarterly 5、yearly 1 |
| **需金鑰** | 無 57、`FINMIND_TOKEN` 13、`FRED_API_KEY` 7、`GEMINI_API_KEY` 1 |
| **可 ping** | **15 / 78**（只有 19% 有內建健康檢查 URL） |

> ⚠️ **文件 vs 實況落差 #1**：`CLAUDE.md §0` 步驟 1 寫「**27 個**外部資料來源 endpoint」。實測 registry 為 **78 筆**。§0 是 2026-06-22 的填寫紀錄（歷史值），非現況；但**讀者很容易把它當現況**。

### 1.2 本地快照資料實體（逐欄 7 項）

以下每一節 = 一個資料實體。**缺漏率全部是本次 `read_parquet` 實算**。

---

#### 實體 A｜`twii_ohlcv.parquet` — 加權指數日 K

| 項目 | 內容 |
|---|---|
| **① 實體來源** | Yahoo Finance `query1.finance.yahoo.com/v8/finance/chart/^TWII`；欄 `source` 自帶 `Yahoo:^TWII:chart`【實測】 |
| **② 更新頻率** | daily；cron `update_macro_history.yml` `0 9 * * *` UTC = **TW 17:00**（收盤後）【實測】 |
| **③ 必缺標記** | `volume` — 見下 |
| **④ 歷史缺漏率**【實測】 | rows=4,929（2006-07-17 起）。`open/high/low/close/source/fetched_at` **0.00%**；**`volume` 8 筆缺 = 0.16%** |
| **⑤ 冷／熱延遲** | 【查不到】單獨量測值。所屬總經頁整體：【引用】`tab_macro.py:167,180` 「冷啟動實測 40~75 秒」「實測冷載約 75 秒」「逾時上限 300 秒」 |
| **⑥ v1 遷移路徑** | **ETL**：已是 git 追蹤的 parquet，直接讀，無需搬 |
| **⑦ 幣別** | TWD 單一幣別，指數點數（非金額），**無匯率結算點** |

> `volume` 的 8 筆缺是**真缺**，非 0 值。對照 v3 §02「加權指數日 K 成交量全為 0 時隱藏該欄（不畫假地平線）」—— 本檔存的是 **NaN 不是 0**，符合 §1（沒有把缺畫成 0）。

---

#### 實體 B｜`finmind_inst.parquet` — 三大法人合計

| 項目 | 內容 |
|---|---|
| **① 來源** | FinMind `TaiwanStockTotalInstitutionalInvestors`（`source` 欄自帶）【實測】 |
| **② 頻率** | daily；同 `update_macro_history.yml` TW 17:00 |
| **③ 必缺** | 無 |
| **④ 缺漏率**【實測】 | rows=4,954；**4 欄全部 0.00%** |
| **⑤ 延遲** | 【查不到】；需 `FINMIND_TOKEN` |
| **⑥ 遷移** | **ETL**，parquet 直讀 |
| **⑦ 幣別** | `foreign_buy` 單位為**億元 TWD**（sample `-56.719`）⚠️ 欄名未帶單位 — 見 §4.1 對帳 |

---

#### 實體 C｜`finmind_margin.parquet` — 融資餘額

| 項目 | 內容 |
|---|---|
| **① 來源** | FinMind `TaiwanStockTotalMarginPurchaseShortSale`【實測】 |
| **② 頻率** | daily |
| **③ 必缺** | 無 |
| **④ 缺漏率**【實測】 | rows=4,954；**4 欄全部 0.00%** |
| **⑤ 延遲** | 【查不到】 |
| **⑥ 遷移** | **ETL** |
| **⑦ 幣別** | ⚠️ **單位 = 元（TWD）**，sample `241,817,472,000`。判定門檻 `MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI = 3400.0` 單位是**億** → 必須 `/1e8`。換算常數 `shared/margin_schema.TWD_PER_YI = 1e8`【實測】。**這是 §4.1 已知地雷，本站已 SSOT 化** |

---

#### 實體 D｜`finmind_m1m2.parquet` — M1B / M2 貨幣供給 ⚠️ **目前抓取失敗中**

| 項目 | 內容 |
|---|---|
| **① 來源** | `source` 欄實際寫 **`CBC:PXWeb:EF19M01+EF21M01`**【實測】—— **不是** registry 宣告的 `cbc.gov.tw/public/Attachment/ms1.json` |
| **② 頻率** | monthly |
| **③ 必缺** | 無（既有資料完整） |
| **④ 缺漏率**【實測】 | rows=240（2006-08 起）；**6 欄全部 0.00%** |
| **⑤ 延遲** | 【查不到】 |
| **⑥ 遷移** | **ETL** |
| **⑦ 幣別** | ⚠️ **TWD**（`m1b`/`m2` 為 int64，sample 147,362 / 108,052，單位應為**百萬元 TWD**，但**欄名未帶單位、檔內無宣告** → 見 §5 未驗事項）。`m1b_m2_gap` 單位為 **pts/月**（對照 `M1B_M2_GAP_DETERIORATION_THRESHOLD = -2.0`）。**§2.1 明令：CBC(TWD) 與 IMF(USD) 禁止跨幣別平均** |

> 🔴 **`metadata.json` 記載 `last_error: "抓取結果為空"`，`last_updated = 2026-07-01` → 截至今日（2026-09-14）已停更 75 天**【實測】。

---

#### 實體 E｜`tw_pmi.parquet` — 台灣製造業 PMI ⚠️ **目前抓取失敗中**

| 項目 | 內容 |
|---|---|
| **① 來源** | `source` 欄 = `data.gov.tw:dataset:6100`【實測】（8 源賽跑的第一命中，§2.1 禁止平均） |
| **② 頻率** | monthly |
| **③ 必缺** | 無 |
| **④ 缺漏率**【實測】 | rows=170（2012-07 起）；**4 欄全部 0.00%** |
| **⑤ 延遲** | 【引用】`macro_core.py:1178`「data.gov.tw 為慢速政府 API，**實測回應常 12-18s**」 |
| **⑥ 遷移** | **ETL** |
| **⑦ 幣別** | 無（指數值，合理範圍 `[30,70]`，SSOT `shared/signal_thresholds.py:139-143`） |

> 🔴 **`last_error: "抓取結果為空"`，`last_updated = 2026-08-01` → 停更 44 天**【實測】。
> 另有 durable last-known-good：`data_cache/macro_last_good/tw_pmi.json`，值 62.5 / 2026-08-01 / **`is_proxy: True`**【實測】。

---

#### 實體 F｜`fundamentals/*.parquet` — 個股季財報（12 檔，sii + otc × 6 季）

| 項目 | 內容 |
|---|---|
| **① 來源** | **MOPS** `t163sb04`（`source` 欄 = `MOPS:t163sb04:{market}:Y{roc}S{season}`）【實測】—— registry 把 MOPS 列為「備援」，但**快照實際由 MOPS 產出**，非 FinMind |
| **② 頻率** | quarterly；cron `update_fundamentals.yml` 一年 **4 次固定日**（4/7、5/22、8/21、11/21，皆為公布截止 + 1 週）【實測】 |
| **③ 必缺標記** | ⚠️ **`revenue` / `gross_profit` / `op_income` / `current_assets` 對金融業常態性缺** — 金融保險業損益表無「營業收入／毛利」科目 |
| **④ 缺漏率**【實測】 | 見下表，**上市(sii) 明顯高於上櫃(otc)**，與金融股集中在上市一致 |
| **⑤ 延遲** | 【查不到】 |
| **⑥ 遷移** | **ETL**，12 個 parquet 直讀 |
| **⑦ 幣別** | **TWD**，單位 = **千元**（sample 台泥 `total_assets=622,719,805` ≈ 6,227 億）。⚠️ **欄名未帶單位**（`revenue` 而非 `revenue_twd_k`）→ 違反 §4.1 命名規範 |

**季財報逐檔缺漏率**【實測】

| 檔案 | rows | revenue | gross_profit | op_income | current_assets | 其他 11 欄 |
|---|---|---|---|---|---|---|
| sii_114Q1 | 1,059 | 2.83% | **3.40%** | 2.55% | 2.74% | 0.00% |
| sii_114Q2 | 1,077 | 2.79% | **3.34%** | 2.51% | 2.69% | 0.00% |
| sii_114Q3 | 1,079 | 2.78% | **3.34%** | 2.50% | 2.69% | 0.00% |
| sii_114Q4 | 1,078 | 2.78% | **3.34%** | 2.50% | 2.69% | 0.00% |
| sii_115Q1 | 1,078 | 3.34% | **3.34%** | 2.50% | 2.69% | 0.00% |
| sii_115Q2 | **988** | 0.71% | 0.71% | 0.51% | 0.30% | 0.00% |
| otc_114Q1 | 875 | 0.91% | 0.91% | 0.00% | 0.00% | 0.00% |
| otc_114Q2~115Q1 | 891 | 0.79% | 0.79% | 0.00% | 0.00% | 0.00% |
| otc_115Q2 | **862** | 0.35% | 0.35% | 0.00% | 0.00% | 0.00% |

> ⚠️ **最新季（115Q2）覆蓋家數掉下來**：sii 1,078 → **988**（−90），otc 891 → **862**（−29）。`latest.json` 自己記錄 `coverage.total = 1850`、`prev_total = 1968` → **少 118 家（−6.0%）**【實測】。缺漏率同時下降，是因為**還沒公布的公司整列不存在**（不是欄位缺），屬 §4.6「月營收三態」的季報版本：**「等公布」≠「缺值」**，下游不可混為一談。

---

#### 實體 G｜`forward_test/picks.parquet` — 前進式驗證凍結選股 ⭐ **不可重建**

| 項目 | 內容 |
|---|---|
| **① 來源** | L3 `fundamental_screener_service.get_ranked_picks`（與畫面同源）→ `scripts/update_forward_test_freeze.py` 落地 |
| **② 頻率** | monthly；cron `update_forward_test.yml` `0 6 2 * *` = 每月 2 號【實測】 |
| **③ 必缺標記** | ⚠️ **`name` 欄常態性空字串**（見下） |
| **④ 缺漏率**【實測】 | rows=60（3 個 cohort × 20）。null 全 0；**但 `name` 空字串 24/60 = 40.00%**，且**分布極不均**：`2026-07-22` 12/20、`2026-08-02` 12/20、`2026-09-02` **0/20** → **2026-08-02 與 09-02 之間被修好了** |
| **⑤ 延遲** | 【查不到】 |
| **⑥ 遷移** | **ETL**（git 追蹤）+ 對帳時取「本地 ∪ Google Sheet」去重 |
| **⑦ 幣別** | `entry_price` **TWD**（sample 6000.0），欄名未帶單位 |

> 🔴 **§-1.5.F 判定 3(5) 明列此檔為「不能重建」側 → GC 一律不得碰，刪除須請示客戶。** 它記錄「當下真實做過的選股決定」，重抓只會得到今天的排名（正是 §2.3 要防的 lookahead）。
> ⚠️ `name` 空字串是**空字串不是 null** —— `isna()` 掃不到。若 v2 用 `isna()` 做資料完整性檢查，**這 40% 會靜默通過**。

---

#### 實體 H｜`macro_forward_test/signals.parquet` — 總經燈號每日落地 🔴 **3 欄 100% 全空**

| 項目 | 內容 |
|---|---|
| **① 來源** | `update_macro_forward_test.yml`，自帶 `git_sha` + `ruleset_hash` + `schema_version`（可重現性設計良好）【實測】 |
| **② 頻率** | 工作日；cron `40 9 * * 1-5` UTC = TW 17:40【實測】 |
| **③ 必缺標記** | 🔴 **`max_score` / `twii_close` / `inputs_as_of` 三欄 100% 全 NULL** |
| **④ 缺漏率**【實測】 | rows=**僅 12 筆**（2026-08-20 起）。`max_score` **100.00%**、`twii_close` **100.00%**、`inputs_as_of` **100.00%**；`missing_sources` 空字串 100%（**但這是合法值**＝沒有缺源，非缺漏）；其餘 16 欄 0.00% |
| **⑤ 延遲** | 【查不到】 |
| **⑥ 遷移** | **ETL**，但**三個欄位搬過去也是空的** |
| **⑦ 幣別** | `twii_close` 應為 TWD 指數點 — **但全空，無從驗證** |

> 🔴 **最重要的單一發現之一。** 一個宣稱要做「前進式驗證」的落地表，卻有 3 個欄位從第一筆開始就沒寫進去過。`twii_close` 全空 = **無法對帳燈號 vs 大盤實際走勢**，等於這張表目前**驗不了它要驗的東西**。
> ⚠️ **我沒有查出成因**（是 writer 沒填、還是 schema 加了欄但 writer 沒同步）→ 列入 §5 未驗事項。

---

#### 實體 I｜`sector_flow/` — 板塊資金潮汐 🔴 **最近一次 run 掉價率 92%**

| 項目 | 內容 |
|---|---|
| **① 來源** | `daily_net.parquet` 的 `source` 欄 = `TWSE:T86+MI_INDEX / TPEX:3itrade+otc_*`【實測】；`ticker_sector.json` **3,147** 檔代碼→產業對映 |
| **② 頻率** | daily；cron `30 9 * * *` UTC = TW 17:30【實測】 |
| **③ 必缺** | 欄位層面無 |
| **④ 缺漏率**【實測】 | `daily_net.parquet` rows=1,733，**9 欄全部 0.00%**。**但 `metadata.json` 的 coverage 顯示上游掉很多**：`n_stock_days_with_net = 17,350`、`n_dropped_missing_price = **16,003**` → 依 `sector_flow.py:148` 的定義（`len(inst) - len(merged)`），**掉價率 = 16,003 / 17,350 = 92.24%**，僅 1,347 筆（7.76%）進入結果 |
| **⑤ 延遲** | 【查不到】 |
| **⑥ 遷移** | **ETL** |
| **⑦ 幣別** | **TWD，單位＝億**，且**欄名有帶單位**（`net_amt_yi` / `foreign_yi` / `trust_yi` / `dealer_yi`）✅ **全 repo 單位命名最標準的一張表**，符合 §4.1 命名規範 |

> ⚠️ **92.24% 這個數字的解讀要小心**：`metadata` 同時記 `n_days: 1`，代表這是**最近一次增量 run（單日）** 的統計，不是全歷史。掉價原因是 inner join 找不到當日收盤價（§1 正確做法：不補值直接剔除）。
> **我沒有驗證**：這個掉價率是常態還是那天上游出事 → 列入 §5。

---

#### 實體 J｜其他小型快照【實測】

| 檔案 | 內容 | 缺漏 | 備註 |
|---|---|---|---|
| `macro_last_good/tw_pmi.json` | PMI durable last-known-good，value=62.5, date=2026-08-01 | — | ⚠️ **`is_proxy: True`** — 這不是原始 CIER 值 |
| `fundamentals/latest.json` | 季報指標 roc_year=115/season=2, coverage 1850 (prev 1968) | — | 覆蓋家數 −6.0% |
| `health_watchlist.json` | **`stocks: []` 空清單** | — | ✅ 檔內自述「清單為空 = 功能待命不跑（**不會腦補您的持股**）」—— §1 正面範例 |
| `sector_flow/bubble_latest.json` | 43 個產業 × 20 日窗 | — | 帶 `insufficient` 旗標 |

> ⚠️ `health_watchlist.json` 空 ⇒ `health_history.parquet` **根本不存在**（實測 `data_cache/` 無此檔）。**「健康度走勢」目前 0 樣本。**

---

### 1.3 台股站持倉（v1 → v2 遷移路徑）⭐

**儲存位置：Google Sheets（不在 repo 內）**，`src/data/portfolio/gsheet_portfolio.py`【實測】

| Worksheet | 欄位 | 用途 |
|---|---|---|
| `portfolios` | `_HEADERS = ['name', 'ticker', 'lots', 'avg_price', 'updated_at']` **5 欄** | 持倉（含價格） |
| `stock_watchlist` | `['name', 'ticker', 'updated_at']` **3 欄** | 觀察池，**物理隔離、無任何價格欄**（§1 反捏造） |
| `forward_test_picks` | `['cohort','stock_id','name','entry_price','factors','frozen_at']` **6 欄** | 選股凍結 |

**讀取後正規化**（`parse_portfolio_records`）→ `{ticker, lots, avg_price}`，且 **`lots<=0` 或 `avg_price<=0` 直接丟棄**（不納入零值髒列）【實測】

| 7 項 | 內容 |
|---|---|
| **① 來源** | Google Sheets（OAuth／Service Account 雙路徑，`oauth_state.py` 登記 EX-OAUTH-1） |
| **② 頻率** | 事件驅動（user 編輯）；讀取快取 TTL_15MIN |
| **③ 必缺標記** | 🔴 **`currency` 欄根本不存在** |
| **④ 缺漏率** | 【查不到】—— Sheets 在雲端，沙箱打不到 |
| **⑤ 延遲** | 【查不到】 |
| **⑥ v1 遷移路徑** | ⚠️ **必須 ETL 且必須補欄**：現有 5 欄 → `v2_holdings` 至少要補 `currency`。`lots` 語意為「**張**」（台股 1 張 = 1000 股），非股數 |
| **⑦ 幣別** | 🔴 **無幣別欄。幣別靠 `holding_currency(ticker)` 從代號後綴推斷**：`.TW`/`.TWO` → TWD，**其餘一律 USD**（`src/compute/etf/portfolio_fx.py`）【實測】 |

> 🔴 **`holding_currency()` 的 docstring 自己承認這是脆弱假設**（逐字引用）：
> 「代號沒後綴 → 一律當 USD（對美股 ETF 正確；**若使用者少打 `.TW`，會被當美元 → 換匯後金額放大約 32 倍**，屬**已知誤判方向**）」
> 「未來若新增第三個市場（港股 `.HK` / 日股 `.T` 等）**必須**回來擴充，否則會被當成 USD」

---

### 1.4 台股站匯率結算點 ⭐

**單一換匯點設計**（`src/compute/etf/portfolio_fx.py`，L2 純函式，零 I/O）【實測】

- **匯率來源**：`TWD=X`（Yahoo，registry 標 `USDTWD 匯率`，pingable=True），由 L5 caller 抓後**傳入**
- **換匯時點**：rows 建構完成後**只呼叫一次** `convert_rows_to_twd()`，下游 9 個消費點吃同一套 TWD 欄位
- **換哪些欄**：`FX_SCALED_FIELDS = (cost, current_value, capital_gain, dividend_received, total_pnl, current_price, avg_price)`；**ratio 類刻意不換**（分子分母相消）
- **sanity 範圍**：`USDTWD_SANITY_MIN = 25.0` ~ `USDTWD_SANITY_MAX = 40.0`【實測】
- **§1 落實**：拿不到匯率／超出 sanity → **絕不預設 1.0**，該檔標 `needs_fx=True` 移入 `excluded`，不計入任何總計
- **原幣保留**：換匯後保留 `*_native` 欄供顯示「BND 現價 72.50 USD」

> 🔴 **模組 docstring 自己揭露的限制（逐字引用）**：
> 「成本（`cost`/`avg_price`）與現值（`current_value`/`current_price`）**都用同一個今日即期匯率**換算。因此 `capital_gain` 是**純價格報酬 × 今日匯率**，**不含匯兌損益** —— 使用者真實的匯兌損益取決於當初買進時的換匯匯率，**本頁沒有那筆資料，故不估（估了就是捏造）**。」
>
> **這正是 v2 要解的核心缺口**：台股站**沒有存買入匯率**，所以算不出匯兌損益。**基金站有存**（見 §2.3）→ 直接影響 `v2_holdings` 能不能統一（見 §7）。

> **歷史事故紀錄**（docstring 逐字）：原本把每檔原幣金額直接相加，等於預設 1 USD = 1 TWD → 實機造成 **BND 現值低估 32 倍**、權重 6.8%（真值約 70%）、股債比 93/7（真值約 30/70）、組合殖利率 12.20%（真值約 3.9%），並汙染核心/衛星、產業曝險、風險貢獻、VaR、壓力測試、效率前緣。**這是「無幣別欄」的實際代價。**

---

## 2. 基金站（my-fund-dashboard，唯讀）

### 2.1 本地快照資料實體

#### 實體 K｜`data_cache/*.parquet` — 總經／市場歷史（4 檔）

| 檔案 | rows | 期間 | 欄位 | 缺漏率【實測】 |
|---|---|---|---|---|
| `fred_indicators.parquet` | 13,654 | 2011-06-01 起 | `date, series_id, value` | **3 欄全 0.00%** |
| `vix_history.parquet` | 3,841 | 2011-06-07 起 | `date, close` | **0.00%** |
| `spx_history.parquet` | 3,839 | 2011-06-07 起 | `date, close` | **0.00%** |
| `twii_history.parquet` | 3,726 | 2011-06-07 起 | `date, close` | **0.00%** |

| 7 項 | 內容 |
|---|---|
| **① 來源** | FRED / Yahoo（`repositories/macro/fred.py`、`yf.py`） |
| **② 頻率** | **每週**；cron `update_macro_history.yml` `0 0 * * 0`【實測】—— ⚠️ **比台股站的每日慢 7 倍** |
| **③ 必缺** | 無 |
| **④ 缺漏率** | 全 0.00%（見上表） |
| **⑤ 延遲** | 【查不到】 |
| **⑥ 遷移** | **ETL** |
| **⑦ 幣別** | `spx_history` = **USD**、`twii_history` = **TWD**、`vix` 無幣別 —— 🔴 **三檔 schema 完全相同（`date, close`），`close` 欄名不帶幣別，全靠檔名區分**。若 v2 要 union 這三張表，**必須外加 currency 欄，否則會混幣別相加** |

> **新鮮度**【實測】：`fred_indicators` 2026-09-10（4 天前）、`vix/spx/twii` 2026-09-11（3 天前），**`last_error` 全部 `None`** → 基金站 4 個資料集**全部健康**，對比台股站有 2 個在報錯。

---

#### 實體 L｜`cache/nav/{CODE}.json` — 基金 NAV 快取 🔴 **缺漏率 99.7%**

**repo 內只有 1 個檔**：`cache/nav/TLZF9.json`【實測】

| 項目 | 內容 |
|---|---|
| **① 來源** | GitHub Actions 每日預存（`scripts/fetch_nav_cache.py`）；但此檔 `source` 欄 = **`cache_only`**，`fund_name` = **空字串** |
| **② 頻率** | 宣告 daily；**實際 `updated_at = 2026-07-22` → 距今 54 天未更新**【實測】 |
| **③ 必缺標記** | 🔴 **整條序列本質上就是稀疏的** |
| **④ 缺漏率**【實測】 | **10 個點橫跨 5,270 天（14.43 年）**。以 252 交易日/年計，期望約 3,636 點 → **覆蓋率 0.275%，缺漏率 99.725%**。**最大空窗 2,029 天（5.56 年）**，gap 序列 `[332, 1, 136, 62, 685, 1783, 241, 2029, 1]` |
| **⑤ 延遲** | 【查不到】 |
| **⑥ 遷移** | ⚠️ **不建議 ETL 這個檔** —— 長歷史真正的家在 **Google Sheets `nav_history` 分頁**（見 §2.2） |
| **⑦ 幣別** | 🔴 **此 json 無 currency 欄**（只有 `code/fund_name/updated_at/source/count/history[{date,nav}]`）。幣別要另外查 |

> ✅ **本 repo 自己已經抓到並誠實處理了這件事** —— `sources.py:1260` 註解逐字：
> 「實測 cache/nav/TLZF9.json = 10 點橫跨 14.43 年、最大空窗 **2,029 天**、密度 0.69 點/年 —— 拿去算 Sharpe / σ / 最大回撤（年化 ×√252，假設每點=1 交易日）出來的是**看起來像數字的雜訊**。」
> **我的獨立實算與這段註解完全吻合**（10 點 / 14.43 年 / 2,029 天）→ 這是本次少數有**交叉驗證**的數字。
>
> 處置機制 `shared/data_quality.assess_nav_cache_quality()` 採**兩段式且刻意不對稱**：
> - **Tier A 擋**：筆數不足 / schema 違反 → 視同無快取
> - **Tier B 不擋、標註疑義**：密度 / 空窗 / 新鮮度 → 序列照回，掛 `supports_annualized=False` 旗標
> 理由（逐字）：「本函式是 Streamlit Cloud 美國 IP 被上游封鎖時**唯一還吐得出 NAV 的來源**，擋掉會把『數字可疑』變成『完全沒資料』，那是更糟的失效模式。」
> → **這是 §1 Fail Loud 的高品質實作範例，v2 應沿用此模式。**

---

### 2.2 基金站 NAV 長歷史（Google Sheets）

| 項目 | 內容 |
|---|---|
| **① 來源** | Google Sheets **獨立一本**，分頁 `nav_history`；Sheet ID = `NAV_SHEET_ID` secret → baked 預設，**僅此兩層、無自動回退**【實測】 |
| **② 頻率** | daily；cron `weekly_nav_backfill.yml` `0 12 * * *`（持倉 ∪ 選股池 → nav_history），**失敗會推 LINE 通知** |
| **③ 必缺** | 【查不到】 |
| **④ 缺漏率** | 【查不到】—— 雲端 Sheets，沙箱打不到 |
| **⑤ 延遲** | 【查不到】 |
| **⑥ 遷移** | **ETL**（已有 `scripts/migrate_nav_caches_to_sheet.py`，走 `append_points` 依 `(code,date)` 去重、冪等） |
| **⑦ 幣別** | ✅ **有 `currency` 欄** — `_NAV_HEADERS = ["code","date","nav","fund_name","source","recorded_at","currency"]` **7 欄**【實測】 |

> ⚠️ 本地 `cache/nav_history/` 目錄**不存在**（實測 `No such file or directory`）→ **repo 內完全沒有長歷史 NAV 樣本可供離線統計。**

---

### 2.3 基金站持倉（v1 → v2 遷移路徑）⭐

**儲存位置：Google Sheets**。**兩套 schema 並存**（v1 保單制 / v2 基金明細制）【實測】

**V1 — `repositories/policy/_helpers.py`**

| 類 | 欄位 |
|---|---|
| `REQUIRED_COLS`（8） | `policy_id, policy_name, fund_url, invest_twd, invest_date, **currency**, **fx_at_buy**, notes` |
| `OPTIONAL_COLS`（6） | `policy_tier, div_cash_pct, avg_nav_with_div, **avg_nav**, **fx_avg**, units` |

**V2 — `repositories/policy/v2.py`（10 欄，中文 header 存 Sheet、英文內部用）**

| EN | ZH | 責任 |
|---|---|---|
| `policy_id` | 保單編號 | user 填 |
| `fund_code` | 基金代號 | user 填 |
| `fund_name` | 基金名稱 | 自動 |
| **`currency`** | **幣別** | 自動 |
| `tier` | 級別 | 自動 |
| `invest_twd` | 淨投資金額 | user 填 |
| `div_cash_pct` | 現金給付% | user 填 |
| `units` | 持有單位數 | 自動 |
| `avg_nav` | 平均買入單位成本 | user 填 |
| **`avg_fx`** | **平均買入匯率** | user 填 |

**交易帳 — `repositories/ledger_repository.py`（9 欄）**

`policy_id | date | code | action | units | nav_at_action | **twd** | fee | note`
`KNOWN_ACTIONS = ('buy','sell','dividend','fee','fx')` — ⚠️ **含 `fx` 這個 action 類型**

| 7 項 | 內容 |
|---|---|
| **① 來源** | Google Sheets（`Policies` / v2 分頁 / `_Ledgers`） |
| **② 頻率** | 事件驅動 |
| **③ 必缺標記** | `units`/`avg_nav`/`avg_fx` 為**選填** → 空 = T7 不算市值（**不猜**） |
| **④ 缺漏率** | 【查不到】（雲端） |
| **⑤ 延遲** | 【查不到】 |
| **⑥ 遷移** | ⚠️ **ETL，但要處理 v1/v2 雙 schema + 中英文 header 雙向翻譯**（`ZH_HEADERS_V2` / `EN_HEADERS_V2` / `_LEGACY_ZH_ALIASES_V2` 三張對映表） |
| **⑦ 幣別** | ✅ **原幣 + 台幣雙軌，且存了買入匯率**：`currency`（原幣別）、`avg_nav`（**原幣** NAV）、`avg_fx`（**買入時**匯率）、`invest_twd`（**台幣**投入額）。核心算式【實測】：`compute_units(invest_twd, avg_nav, avg_fx) = invest_twd / (avg_nav × avg_fx)` |

---

### 2.4 基金站匯率結算點 ⭐

**`repositories/fund/fx_and_main.py::get_latest_fx(pair)`**【實測】

| 項目 | 內容 |
|---|---|
| **來源瀑布** | Yahoo `{pair}=X` → FRED（`_FRED_FX_MAP`）→ **open.er-api.com** → **Frankfurter** |
| **快取** | `_FX_CACHE` TTL **300 秒**，⚠️ **positive-only**（只快取成功值，失敗不入快取）—— 符合 v3 §02「只快取成功結果」 |
| **退避** | 走 `infra/source_backoff`（`should_skip` / `record_failure` / `kind_for_status`）—— 符合 v3 §02「失敗時退避，不連續轟炸來源」 |
| **timeout** | 15 s（er-api、Frankfurter）【實測】 |
| **結算點** | **兩個不同時點**：`avg_fx`（**買入時**，存在 Sheet）與 `get_latest_fx()`（**當下即期**，300s 快取）→ **因此基金站算得出匯兌損益** |

> ⚠️ **實測發現的一個防禦缺口**：`fx_and_main.py` 的 er-api / Frankfurter 兩段 `requests.get(..., **verify=False**)`【實測】。這會停用 TLS 憑證驗證。**不在本次任務範圍內修**（§-1：無 bug 觸發不動工），但 v2 若沿用此取數路徑應知悉。

---

## 3. `CLAUDE.md §4.1` 單位陷阱表 — 逐條對照【實測】

| # | 陷阱 | 憲法宣告位置 | 實測結果 |
|---|---|---|---|
| 1 | **% vs 小數** | `shared/thresholds.py:21-27` | ✅ **符合**。`YIELD_HIGH=7.0` / `YIELD_HIGH_DEC=YIELD_HIGH/100`，**DEC 由 PCT 推導**（非兩個獨立常數）→ 結構上不可能漂移 |
| 2 | **元 vs 百萬 vs 億** | `signal_thresholds.MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI` + `margin_schema` | ✅ **符合**。`=3400.0`（億）、`TWD_PER_YI=1e8`、`margin_schema.py:36` 註明「TodayBalance 單位 = **元**，÷1e8 = 億」。實測 `finmind_margin.parquet` 存的是**元**（241,817,472,000）→ 一致 |
| 3 | **TWD vs USD** | `data_registry.py:345-350` | ✅ 規則在（CBC 主 / IMF 備，禁平均）。⚠️ 實測 `finmind_m1m2.parquet` 的 `source` 欄為 `CBC:PXWeb:EF19M01+EF21M01`，**與 registry 宣告的 `ms1.json` 不同路徑** |
| 4 | **YoY vs MoM** | `merrill_clock.py:5,133` | 🔴 **憲法 evidence 已失效**：`merrill_clock.py` 已於 v18.359 F-4 **刪除**（§8.2 L2 列自己也標了 `~~merrill_clock.py~~`）。**§4.1 表格的 Evidence 欄仍指向已刪檔案** |
| 5 | **名目 vs 實質** | — | 憲法自述「尚未實作」，實測無對應 code → 一致 |
| 6 | **交易日 vs 日曆日** | `signal_thresholds.TRADING_DAYS_PER_YEAR` | ✅ **符合**，實測 `=252` |
| 7 | **TW 時區 vs UTC** | `app.py:47` 等 | ✅ 未逐一複驗，但 cron 全部用 UTC 且註解標 TW 換算（如 `0 9 * * *` = TW 17:00）→ 一致 |
| 8 | **點數 vs 百分比** | `signal_thresholds.M1B_M2_GAP_DETERIORATION_THRESHOLD` | ✅ **符合**，實測 `=-2.0`（pts/月）。`finmind_m1m2.parquet` 的 `m1b_m2_gap` 為 float64 差分值 → 一致 |

### 3.1 §2.1 來源分級表的正／反兩面對帳【實測】

✅ **正面（憲法準確）—— TW PMI 8 源賽跑順序逐字吻合**

`CLAUDE.md §2.1` 寫「依 `PMI_SOURCE_REGISTRY` 順序賽跑，取第一個命中（CIER-EN > data.gov.tw > NDC > CIER首頁 > StockFeel > Cnyes > CIER-cid8 > MoneyDJ，**共 8 源**）。**不平均**」。

AST 解析 `macro_core.PMI_SOURCE_REGISTRY` 實測 **8 筆，順序完全相同**：

| # | 標籤 | fetcher |
|---|---|---|
| 1 | `CIER-EN` | `_pmi_src_cier_en_monthly` |
| 2 | `data.gov.tw` | `_pmi_src_dgtw` |
| 3 | `NDC` | `_pmi_src_ndc` |
| 4 | `CIER` | `_pmi_src_cier21` |
| 5 | `StockFeel` | `_pmi_src_stockfeel` |
| 6 | `Cnyes` | `_pmi_src_cnyes` |
| 7 | `CIER-cid8` | `_pmi_src_cier8` |
| 8 | `MoneyDJ` | `_pmi_src_moneydj` |

→ **這是本次對帳中唯一一處「憲法宣告與 code 逐字吻合」的多源規則。** 對照 `tw_pmi.parquet` 的 `source` 欄實際值 = `data.gov.tw:dataset:6100`（第 2 順位命中）→ **賽跑機制確實在運作**，第 1 順位 CIER-EN 當時未命中。

🔴 **反面（行號過期）**

| 憲法 §2.1 寫 | 實測位置 | 偏差 |
|---|---|---|
| `macro_core.py:1262` | **`macro_core.py:1535`** | **273 行** |
| `tw_macro.py:74` | **`tw_macro.py:77`** | 3 行 |

→ **§8.2.A.0 規則 1（禁寫行號，「行號是保證會過期的資訊」）目前只寫在 §8.2.A 的例外清單脈絡下，但 §2.1 / §3.2 / §3.3 / §4.1 各表也大量使用行號**，且已經開始漂移。

---

**額外發現：欄名帶單位的落實極不平均**【實測】

| 落實程度 | 資料實體 | 欄名 |
|---|---|---|
| ✅ **完全符合 §4.1 命名規範** | `sector_flow/daily_net.parquet` | `net_amt_yi` / `foreign_yi` / `trust_yi` / `dealer_yi` |
| 🔴 **完全未帶單位** | `fundamentals/*.parquet` | `revenue` / `gross_profit` / `total_assets`（實為**千元 TWD**） |
| 🔴 **完全未帶單位** | `finmind_inst.parquet` | `foreign_buy`（實為**億元 TWD**） |
| 🔴 **完全未帶單位** | `finmind_margin.parquet` | `margin_balance`（實為**元 TWD**） |
| 🔴 **完全未帶單位** | `twii/spx_history.parquet`（基金站） | `close`（TWD vs USD **只靠檔名區分**） |

> **同一個 repo 內，`margin_balance`（元）、`foreign_buy`（億）、`revenue`（千元）三個欄位都叫「金額」但單位差 10^3 ~ 10^8，且欄名都不帶單位。** §4.1 的命名規範（`amount_twd` / `amount_twd_yi`）**在既有落地資料上大致未被遵守** —— 規範寫在憲法，但資料是規範寫下之前就長出來的。

---

## 4. 冷／熱載入延遲總表

> 🔴 **本節沒有任何一個數字是我量的。** 沙箱 4/4 endpoint 全 `http=000`（§0.3）。

**【引用】repo 內既有實測值**

| 對象 | 值 | 出處 |
|---|---|---|
| 總經頁**冷啟動** | **40~75 秒** | `src/ui/tabs/tab_macro.py:167,405` |
| 總經頁**冷載實測** | **72.4 秒** / 「約 75 秒」 | `tab_macro.py:178,180,397` |
| 總經頁**逾時上限** | **300 秒**（5 分鐘） | `tab_macro.py:167,180,405` |
| 總經頁**暖快取** | 「數秒」（無精確值） | `tab_macro.py:405`、`page_today.py:575` |
| `data.gov.tw` 單源 | **常 12-18 秒** | `macro_core.py:1178`（「慢速政府 API」） |
| 個股組合 | ⚠️ **無全域逾時上限**，耗時隨檔數線性成長，「30 檔的組合**不可能** 60 秒跑完」 | `tab_stock_grp.py:331` |
| 配息 rolling 計算 | **< 1 ms**（純計算，非 I/O） | `dividend_station_service.py:191` |
| macro barrel lazy import | 冷啟動淨節省 **≈ 0 ms** | `src/data/macro/__init__.py:23` |

**【實測】code 內的 timeout 常數**（可作延遲**上界**，非實際耗時）

| 站 | 常數 | 值 |
|---|---|---|
| 台股 | `src/data/**` 逐源 `timeout=` 分布 | 12s ×42、15s ×40、20s ×16、10s ×15、25s ×9、5s ×3、8/60/30/3/2s 各 1 |
| 台股 | `macro_fetch_orchestrator._INNER_ITEM_TIMEOUT_S` | **8 s**（單檔上限） |
| 台股 | `macro_fetch_orchestrator._job_timeout` 預設 | **30 s** |
| 台股 | `_AS_COMPLETED_TIMEOUT` | `max(job_timeouts) + 20` s（全域上限） |
| 基金 | er-api / Frankfurter FX | **15 s** |
| 基金 | `_FX_CACHE_TTL` | **300 s** |

**【實測】快取 TTL（台股站 `shared/ttls.py`，`@st.cache_data(ttl=)` SSOT）** — 熱載入上界

`TTL_10MIN=600` / `TTL_15MIN=900` / `TTL_30MIN=1800` / `TTL_1HOUR=3600` / `TTL_2HOUR=7200` / `TTL_6HOUR=21600` / `TTL_1DAY=86400` / `TTL_3DAY=259200` / `TTL_7DAY=604800`

> ⚠️ **憲法 §2.4 對帳**：表列 9 個 TTL 常數與實際 `shared/ttls.py` **完全一致**【實測】。但 §2.4 表**漏列 `TTL_10MIN`**（code 有、憲法表沒有）。

---

## 5. 母法修正提案候選（正式格式）

> 依客戶母法「提案要走正式格式：變更條款、阻礙原因、替代方案、影響評估」。
> ⚠️ 以下為**提案**，非已拍板決定。依 §8.4 step 4 + §-1.5.F 判定 8，**範圍由客戶決定，做法由內部拍板**，故每案均附**總管推薦方案**。

---

### 提案 #1｜`CLAUDE.md §2.1` 列的 TW CPI / TW 失業率兩個資料源**不存在**

| 欄 | 內容 |
|---|---|
| **變更條款** | `CLAUDE.md §2.1` 5-Tier 表（T2 FinMind 列）；`data_registry.py` 兩筆 entry（`TaiwanCPI_YoY`、`TaiwanUnemployment`） |
| **阻礙原因** | 【實測】兩筆 registry entry 的 `endpoint` 欄**自己就寫著**「`dataset=TaiwanMacroEconomics`（**⚠️ dataset 不存在**）」，`usage` 欄寫「**現況恆無資料，待新源**」。`tw_macro.py:420` 註記 v19.85 已查證「TaiwanMacroEconomics 在 FinMind **不存在**（SDK 2.0.4 Dataset 枚舉無此名）」。→ **憲法列的來源，實際拿不到任何一筆資料。** |
| **替代方案** | (a) **主計總處**官方 API／data.gov.tw dataset（與 PMI 同路徑，已有 8 源賽跑機制可複用）；(b) **FRED** 的 TW 系列（`INTDSRTWM193N` 已在用，CPI 可查 `TWNCPIALLMINMEI` 等 OECD 鏡像）；(c) **暫不替換**，registry 保留「已知失效」標記，v2 不建這兩個欄位 |
| **影響評估** | **低**。這兩個指標目前**恆無資料**，等於已經沒人在用 → 移除或替換都**不會改變任何現有畫面行為**。反之**不處理的成本**：v2 若照憲法建欄，會做出兩個永遠空白的欄位 |
| **總管推薦** | ✅ **採 (c) + (a)**：v2 **先不建**這兩欄（避免做出空欄），registry 的失效標記**保留不刪**（它是誠實紀錄）；若客戶業務上真的需要 TW CPI，再走 (a) 另案設計新源 |

---

### 提案 #2｜`CLAUDE.md §4.1` 陷阱表第 4 列的 Evidence 指向**已刪除的檔案**

| 欄 | 內容 |
|---|---|
| **變更條款** | `CLAUDE.md §4.1` 表格「YoY vs MoM」列的 Evidence 欄：`merrill_clock.py:5,133` |
| **阻礙原因** | 【實測】`merrill_clock.py` 已於 **v18.359 F-4 刪除**。憲法**自己在 §8.2 L2 層列**已把它標成 `~~merrill_clock.py~~`（v18.359 F-4 已刪），**但 §4.1 的 Evidence 欄沒有同步** → 同一份憲法內，一處說它刪了、另一處還拿它當證據 |
| **替代方案** | (a) Evidence 改指現存的 `shared/signal_thresholds.py`（PMI 有效範圍已下沉至 `:139-143`，憲法 §3.2 已經這樣改過）＋ `macro_core.py:216`（CPI YoY）；(b) 整列標「待重新定位 evidence」 |
| **影響評估** | **極低**（純文件）。但**不處理的成本不低**：這正是 §8.2.A.0 整節在講的「**會說謊的憲法比沒有憲法更危險**」—— 後續 AI 會照著去讀一個不存在的檔 |
| **總管推薦** | ✅ **採 (a)**。這是 §8.2.A.0 規則 1（禁寫行號）沒有涵蓋到的同類失效：**行號會過期，檔名也會**。建議順帶在 §4.1 表頭補一句「Evidence 欄同受 §8.2.A.0 規則 1 拘束」 |

---

### 提案 #3｜`CLAUDE.md §2.4` Freshness 表**漏列 `TTL_10MIN`**

| 欄 | 內容 |
|---|---|
| **變更條款** | `CLAUDE.md §2.4` TTL 對照表 |
| **阻礙原因** | 【實測】`shared/ttls.py` 定義 **9 個** TTL 常數，`TTL_10MIN=600`（註「tw_macro 7 處 fetcher，v18.402 D3 新增 SSOT」）。§2.4 表只列 **8 個**，`TTL_10MIN` 不在表上 |
| **替代方案** | (a) 表上補一列；(b) 依 §8.2.A.0 規則 3 精神，**表改為指向 `shared/ttls.py`**，不在 .md 內重複維護 |
| **影響評估** | **極低**。但這是**同一類失效的第三個實例**（清單靠人工同步 → 必然漂移） |
| **總管推薦** | ✅ **採 (b)**。§8.2.A.0 規則 3 已經為 §8.2 立下「清單由測試強制、.md 不重複維護」的先例，§2.4 是同構問題，建議沿用同一解法而不是再補一次清單 |

---

### 提案 #4｜`CLAUDE.md §0` 的「27 個外部資料來源」與實況差 2.9 倍

| 欄 | 內容 |
|---|---|
| **變更條款** | `CLAUDE.md §0` 步驟 1 |
| **阻礙原因** | 【實測】AST 解析 `DATA_REGISTRY` = **78 筆**，§0 寫 27 |
| **替代方案** | (a) 就地補註「27 為 2026-06-22 量測值，現況見 registry」；(b) 依 §8.2.A.0 **規則 4**（會漂移的量測值一律標日期或不寫）**直接拿掉數字** |
| **影響評估** | **極低**。§0 本身是「填寫紀錄」＝歷史文件，不是規則。但 §8.2.A.0 規則 4 明文管的就是這種數字 |
| **總管推薦** | ✅ **採 (b)**，與規則 4 一致。⚠️ **注意這一案與 #1~#3 性質不同**：§0 是歷史紀錄，**歷史紀錄寫當時的值是對的**，不算錯 → 若客戶認為歷史紀錄應原樣保留，**本案可直接撤回**，只需確保沒有人拿 §0 當現況用 |

---

### 提案 #5｜`macro_forward_test/signals.parquet` 三個欄位從未被寫入

| 欄 | 內容 |
|---|---|
| **變更條款** | 非憲法條款，屬**資料契約**缺口（影響 §2.3 前進式驗證的可驗證性） |
| **阻礙原因** | 【實測】`max_score` / `twii_close` / `inputs_as_of` 三欄在**全部 12 筆**中 **100% 為 NULL**。`twii_close` 全空 ⇒ **無法把燈號與大盤實際走勢對帳**，這張表目前驗不了它設計要驗的東西 |
| **替代方案** | (a) 修 writer 補寫三欄（需先查成因）；(b) 若三欄已無用 → **刪欄**（依 v3 §03-1「過期代碼何時刪除」屬內部自決）；(c) 維持現狀並在 v2 明確標記為「已知全空，不可依賴」 |
| **影響評估** | **中**。這張表只有 12 筆（2026-08-20 起），**還很年輕** → 現在修，損失的歷史最少；拖越久、空值歷史越長 |
| **總管推薦** | ⚠️ **先查成因，不要先修**。我**沒有查出**是 writer 漏寫還是 schema 加欄未同步（§5 已列為未驗事項）。依 §-2 規則 4，**建議另派一組獨立查證**後再決定 (a)/(b)。**在成因查清前，v2 一律不得依賴這三欄。** |

---

### 提案 #6｜台股站持倉 schema 無 `currency` 欄（直接卡住 `v2_holdings` 統一）

| 欄 | 內容 |
|---|---|
| **變更條款** | `CLAUDE.md §4.1`「TWD vs USD」列的適用範圍；`v2_holdings` schema 設計 |
| **阻礙原因** | 【實測】台股站 `portfolios` 只有 5 欄（`name/ticker/lots/avg_price/updated_at`），**無幣別、無買入匯率**。幣別靠 `holding_currency(ticker)` **從代號後綴推斷**，模組 docstring 自承：使用者少打 `.TW` → **金額放大約 32 倍**（已知誤判方向）；新增第三市場（`.HK`/`.T`）會被誤判為 USD。且因無買入匯率，**匯兌損益「本頁沒有那筆資料，故不估」**。基金站**兩者都有**（`currency` + `avg_fx`） |
| **替代方案** | (a) `v2_holdings` **強制** `currency` + `fx_at_buy` 兩個必填欄，台股列 currency 預設 TWD、`fx_at_buy=1.0`（**⚠️ 這是填預設值，須顯式標 `is_default` 旗標，否則違反 §1**）；(b) 只加 `currency`，`fx_at_buy` 允許 NULL 並讓下游**明確顯示「匯兌損益不可得」**（沿用台股站現行誠實作法）；(c) 維持後綴推斷 |
| **影響評估** | **高** —— 這是**兩站能不能共用 `v2_holdings` 的決定性欄位**。(c) 會把已知的 32 倍誤判風險帶進 v2；(a) 會製造一個「看起來有值其實是預設」的欄位（§1 風險）；(b) 資訊量最誠實但下游要處理 NULL |
| **總管推薦** | ✅ **採 (b)**。理由：§1 明令「任何填補必須顯式呼叫 + 寫 log + 帶旗標」，(a) 的 `fx_at_buy=1.0` 對台股**數值上正確**但對「**使用者是否真的以 1.0 換匯**」是捏造；(b) 則完整保留「這筆資料不存在」這個**事實**，且與台股站現行「不估就是不估」的處置一致。⚠️ **`currency` 欄本身建議設為必填**（不可推斷）—— 這一項是把 32 倍誤判風險擋在入口的唯一手段 |

---

### 提案 #7｜`§8.2.A.0 規則 1`（禁寫行號）的適用範圍建議擴及全檔

| 欄 | 內容 |
|---|---|
| **變更條款** | `CLAUDE.md §8.2.A.0` 規則 1 的適用範圍；連帶影響 §2.1 / §3.2 / §3.3 / §4.1 各 Evidence 欄 |
| **阻礙原因** | 【實測】規則 1 自述理由是「行號在任何一次重構後就失效，而重構**不會**觸發本清單更新 → 行號是**保證會過期**的資訊」，但它目前的**文字脈絡限定在 §8.2.A 例外清單**。實測 §2.1 的兩個行號已漂移：`macro_core.py:1262` → 實際 **1535**（**差 273 行**）、`tw_macro.py:74` → 實際 **77**。§4.1 更嚴重（提案 #2：整個檔案已被刪除） |
| **替代方案** | (a) 規則 1 升格為**全檔通則**（「本憲法任何 Evidence 欄一律用『檔案路徑 + 符號名』，不寫行號」）；(b) 只在 §2.1/§3.2/§3.3/§4.1 各補一句指回規則 1；(c) 維持現狀，靠人工修 |
| **影響評估** | **中**。純文件變更、零 code 風險；但**不處理的成本是複利的** —— 每次重構都讓憲法多說一次謊，而 §8.2.A.0 開頭已經自述過「**一份會說謊的憲法比沒有憲法更危險**」 |
| **總管推薦** | ✅ **採 (a)**。理由：(b) 要在 4 個地方各補一次，本身又是一份需要人工同步的清單（重蹈 §8.2.A.0 規則 3 要防的失效模式）；(a) 一次到位且與規則 1 的既有理由完全同構。⚠️ **但這是憲法層變更，依 §-2 規則 5「會寫入檔案 → 一律派工」，須由總管另派一組執行，不在本次唯讀盤點範圍內。** |

---

## 6. 兩站差異（直接影響 `v2_holdings` 能否統一）

> ⚠️ 本節全部為【實測】比對，但**只覆蓋我讀到的模組**，非窮舉（見 §7）。

### 6.1 🔴 阻斷級差異（不解決就無法統一）

| # | 概念 | 台股站 | 基金站 | 衝擊 |
|---|---|---|---|---|
| **D1** | **幣別儲存** | 🔴 **無欄位**，`holding_currency(ticker)` 後綴推斷 | ✅ `currency` 欄（v1 REQUIRED + v2 皆有） | **v2_holdings 的主鍵級差異**。台股列遷過去時 currency 只能「推斷後寫入」，等於把脆弱假設固化進資料 |
| **D2** | **買入匯率** | 🔴 **不存在** → 匯兌損益「故不估」 | ✅ `fx_at_buy`(v1) / `avg_fx`(v2) | 統一後**兩邊的 `capital_gain` 語意不同**：基金站含匯兌損益、台股站不含。**同一欄名兩種意思 = §4.1 級別的陷阱** |
| **D3** | **部位計量單位** | `lots`（**張**，台股 1 張 = 1000 股） | `units`（**基金單位數**，小數） | 兩者都叫「持有量」但**量綱不同**，且台股是整數語意、基金是連續值。`v2_holdings` 若共用一欄，**必須**同時帶單位欄 |
| **D4** | **成本基礎** | `avg_price`（**每股**價格，TWD 或 USD） | `avg_nav`（**原幣** NAV）+ `invest_twd`（**台幣**投入額）**雙軌** | 基金站存「我投了多少台幣」＋「單位成本多少原幣」；台股站只存單價。**基金站資訊嚴格較多**，台股站無法反推 |

### 6.2 🟡 需對映但不阻斷

| # | 概念 | 台股站 | 基金站 |
|---|---|---|---|
| D5 | **標的識別** | `ticker`（含 `.TW`/`.TWO` 後綴，**保留原樣不改大小寫**） | `fund_code`(v2) / `fund_url`(v1，MoneyDJ URL) |
| D6 | **分層標記** | 無（核心/衛星在 ETF 模組另算） | `policy_tier`(v1) / `tier`(v2)：`core`/`satellite`/`""` |
| D7 | **持倉分組** | `name` 欄（一個 sheet 多組合，用 name 篩） | `policy_id`（保單編號） |
| D8 | **髒列處理** | `lots<=0 或 avg_price<=0` **直接丟棄** | 選填欄空 → **不算市值**（保留列） |
| D9 | **Header 語言** | 純英文 | **中英雙軌**：Sheet 存中文、內部用英文，3 張對映表（`ZH_HEADERS_V2`/`EN_HEADERS_V2`/`_LEGACY_ZH_ALIASES_V2`） |
| D10 | **Schema 版本** | 單一版本 | **v1 / v2 並存**，讀取時自動偵測 |

### 6.3 🟢 架構層差異（影響 ETL 寫法，不影響 schema）

| # | 面向 | 台股站 | 基金站 |
|---|---|---|---|
| D11 | **分層命名** | 7 層 `src/{data,compute,services,ui}` + `shared/`（L0） | `repositories/` + `services/` + `ui/` + `infra/` + `shared/` |
| D12 | **總經快取頻率** | **每日** cron | **每週** cron（`0 0 * * 0`）—— 慢 7 倍 |
| D13 | **快取健康度**【實測】 | 5 個 dataset，**2 個 `last_error` 非空**（m1m2 停更 75 天、tw_pmi 停更 44 天） | 4 個 dataset，**`last_error` 全部 `None`**，最舊 4 天 |
| D14 | **NAV/價格長歷史** | parquet in-repo（twii 4,929 筆完整） | **Google Sheets**（repo 內只有 1 個 10 點的殘缺快取） |
| D15 | **FX 退避機制** | 【查不到】台股站是否有 backoff | ✅ `infra/source_backoff`（`should_skip`/`record_failure`）+ positive-only 快取 |
| D16 | **同名檔不同義** | `data_cache/metadata.json` | `data_cache/metadata.json` — **同名、同結構、內容完全不同** ⚠️ ETL 時極易覆蓋 |

> ⭐ **D16 是實務上最容易出事的一條**：兩站都有 `data_cache/metadata.json`，schema 相同（`updated_at` + `datasets{}`），但 dataset 名稱完全不重疊。**合併時若不加來源前綴，會直接互相覆蓋。**

---

## 7. 我沒能驗到的事（§-2 規則 6 誠實揭露）

> **本節是本白皮書可信度的上界。** 引用本白皮書任何結論前請先讀這一節。

### 7.1 🔴 結構性驗不到（沙箱能力限制）

1. **所有冷／熱載入延遲，一個都沒量到。** 4/4 endpoint `http=000`。§4 的所有數字**全部是【引用】repo 內他人記錄的值**，我**沒有**複現其中任何一個。這些值可能已過期（例如「冷載 72.4 秒」是哪個版本、哪個網路環境量的，我**沒有查**）。
2. **兩站的 Google Sheets 全部讀不到。** 影響：
   - 台股站 `portfolios` / `stock_watchlist` / `forward_test_picks` 的**實際缺漏率 = 【查不到】**
   - 基金站 `Policies` / v2 分頁 / `_Ledgers` / `nav_history` 的**實際缺漏率 = 【查不到】**
   - → **§6 的兩站持倉差異全部基於 schema 定義（code），不是基於實際資料。** 實際資料裡有多少列 `currency` 是空的、多少 `avg_fx` 沒填，**我完全不知道**。
3. **所有 API 的實際回應 schema 沒驗過。** 我只讀到「落地後的 parquet」和「code 裡宣告的欄位」，**沒有驗證上游現在還回不回這些欄位**。

### 7.2 🟡 有能力驗但本輪沒做（範圍取捨）

4. **基金站 677 個 `.py` 只讀了約 15 個。** 集中在 `repositories/{fund,policy,ledger}` + `services/nav_history_gs` + `shared/data_quality`。**`services/` 下 5 個子目錄、`ui/` 整個、`models/`、`infra/` 幾乎沒碰。** → **基金站可能還有我沒看到的資料實體。**
5. **台股站 `src/` 只讀了資料層與少數 compute。** `src/ui/views/`（IA v2 新 View 層，且**有 2 個未 commit 的修改**）完全沒讀。
6. **`signals.parquet` 三欄全空的成因沒查**（提案 #5 已標）。是 writer 漏寫？schema 加欄未同步？還是上游那三個值本來就常缺？**三種可能我一個都沒排除。**
7. **`sector_flow` 92.24% 掉價率是常態還是單日異常，沒查。** metadata 的 `n_days: 1` 顯示這是單日增量統計。**我沒有回溯歷史 run 的 coverage**，所以**不能說「板塊資金潮汐長期掉 92% 的資料」** —— 只能說「最近一次 run 掉了 92%」。
8. **`finmind_m1m2` 的 `m1b`/`m2` 單位沒有確證。** 我推測是**百萬元 TWD**（依數量級 147,362），但 **parquet 內無單位宣告、欄名不帶單位、我也沒去讀 CBC PXWeb 的 EF19M01 定義**。→ **這個「百萬元」是推測，不是實測，不得當前提使用。**
9. **兩站的 `requirements.txt` 版本相容性沒驗。** 憲法 §-1.5.D 要求現場讀 `requirements.txt` 反解 Streamlit floor，**我沒做**。

### 7.3 ⚠️ 全稱句自標（§-2 規則 6）

10. **「兩站 `data_cache/` 已全部盤過」** —— 這句**成立範圍僅限「目錄下的檔案」**：台股 28 檔、基金 5 檔 + 1 個 nav json，**逐檔開啟**。但：**`.gitignore` 排除的檔案我看不到**，production 執行時產生的快取（Streamlit `@st.cache_data` 記憶體快取、`data_cache/` 下未被 git 追蹤的派生物）**不在其中**。
11. **「78 筆 registry 已窮舉」** —— 僅就 `DATA_REGISTRY` 這一個變數而言成立（AST 解析，非 grep）。憲法 §2.1 另載兩個獨立來源清單，**我補驗了存在與筆數，但沒有逐一追進每個 fetcher 函式**：
    - `macro_core.PMI_SOURCE_REGISTRY` = **8 筆**【實測】
    - `tw_macro.CBC_MS1_URLS` = **2 筆**【實測】
    → **三份清單合計 88 筆**，但**我沒有查三者之間有無重疊**（PMI 那 8 源有 7 個也出現在 `DATA_REGISTRY` 的「三方備援」分類裡，看起來重疊但**我沒有逐筆比對**）→ **不得把 88 當成「來源總數」。**
12. **「§4.1 八條單位陷阱已逐條對照」** —— 八條**都查了**，但第 7 條（TW 時區 vs UTC）我**只看 cron 註解**，沒有逐一驗證 code 裡每個 `datetime` 的 tz 處理。**該條的「✅ 符合」信心度明顯低於其他七條。**
13. **本白皮書全部結論為單組產出，未經第二組獨立複驗。** 依 §-2 規則 6，在被獨立稽核前一律屬**待驗事項**，**不得**作為後續動作的前提，**不得**寫進 commit message／PR 描述當成已完成的事實。
    ⚠️ 特別提醒：**§6「兩站差異」是承重判定**（後續 `v2_holdings` schema 設計會直接拿它當前提）。依 §-2 規則 4，**建議優先派獨立一組複核 D1~D4 四條**。

### 7.4 📌 唯讀紀律：一個必須報告的事實

14. **台股 repo 的工作區狀態在我執行期間被「另一個 session」改變了 —— 不是我改的。** 據實記錄完整時序：

    | 時點（UTC，2026-09-14） | 事件 | 證據 |
    |---|---|---|
    | ~09:12 | 我開工，**先**存檔 baseline | `BASELINE_stock_status.txt` = 2 行 |
    | 開工當下 | 台股 repo **已經是 dirty**：`M src/ui/views/page_why.py`、`M tests/test_p05_why_view.py`（`2 files changed, 656 insertions(+), 41 deletions(-)`），HEAD = `ee6ffa5` | `git status --porcelain` + `git diff --stat` |
    | **09:21:28** | **另一個 Claude session 把這 2 個檔 commit 掉了** — `22921ed fix(ui/page_why): 頁5 把 16 盞燈算成 18 盞 —— 修回客戶 2026-08-27 的裁示`，Author `Claude <noreply@anthropic.com>`，diffstat **與我 baseline 逐字相同**（367/330、656/41） | `git show --stat 22921ed`、`git reflog` |
    | 09:25 | 我收工複驗：台股 repo **已變成完全乾淨**，HEAD = `22921ed` | `git status --porcelain` 空輸出 |

    **結論（三點，請一起讀）**：
    - ✅ **我的增量 = 零。** 本次全程只執行讀取指令（`cat`/`head`/`sed -n`/`grep`/`find`/`ls`/`git status`/`git log`/`git show`/`curl`/唯讀 python 探針）。**唯一的 `sed -i` 是改我自己在 scratchpad 的探針腳本**（`/tmp/.../probe_registry.py`），**不在任何 repo 內**。
    - ✅ **兩個 repo 收工時 `git status --porcelain` 都是空的** —— 交付要求達成。
    - ⚠️ **但達成的原因不是「我沒動它」，而是「別人把它 commit 了」。** 這兩件事在結果上看起來一樣，**在稽核上完全不同**。若只回報「收工時是乾淨的」而不講這段，會讓讀者以為 repo 從頭到尾沒被動過 —— 那是**誤導**（v3 §04 第 2 段明禁）。
    - 🔴 **這對總管有一個獨立的作業意義**：**本 repo 在我工作期間有並行寫入者。** 依 `PROCESS.md §3`「寫入端嚴格序列化、一次一檔」與 v3 §00「多 Agent 派工防撞」，**這件事本身值得總管確認是否為預期的派工**。我**沒有**去查那個 session 是誰派的（不在我的任務範圍，且查別人的 session 不是唯讀盤點該做的事）。

15. **基金 repo 全程乾淨、零風險。** 開工與收工 `git status --porcelain` 皆為空輸出，`--untracked-files=all` 亦為 0 行。**我對該 repo 只做了 `cat`/`grep`/`ls`/`sed -n`/`wc`/唯讀 python 讀檔。**

---

## 8. 給階段 2 的 5 個最重要結論

1. **`v2_holdings` 的 schema 卡點是「幣別」與「買入匯率」，不是別的。** 台股站兩個都沒有、基金站兩個都有（§6 D1/D2）。台股站的 32 倍誤判風險已由其 docstring 自承。
2. **兩站對「量綱」的紀律不平均。** `sector_flow` 欄名全帶 `_yi`（模範），`fundamentals`/`finmind_*` 全不帶（`revenue` 千元、`foreign_buy` 億、`margin_balance` 元，差 10^5）。v2 若 union 這些表，**欄名不帶單位就是下一次 32 倍事故的溫床**。
3. **有兩批資料「看起來有、其實沒有」**：`signals.parquet` 三欄 100% 全空、基金 NAV 快取 99.725% 缺漏。**兩者共通點是都能通過 `isna()` 以外的檢查**（前者是 NULL 但下游未檢、後者是點數夠但密度不足）。基金站已有 `assess_nav_cache_quality` 這個**高品質解法，建議 v2 全面沿用**。
4. **空字串是本 repo 的隱形缺漏**。`picks.parquet` 的 `name` 40% 是空字串、null 率 0% —— **任何只用 `isna()` 的資料品質檢查都會漏掉它**。
5. **台股站目前有 2 個資料集在報錯**（m1m2 停更 75 天、tw_pmi 停更 44 天），基金站 4 個全綠。v2 若把台股總經當地基，**要先確認這兩條線是不是已經長期失血**。

---

**— 白皮書結束 —**
