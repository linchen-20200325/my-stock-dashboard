# NEWUI2 📊 市場頁資料契約驗證（C1；docs-only）— 2026-11-12

> **性質**：稽核證據。**不是 SSOT、不是授權**。未修改任何 src／tests／workflow／資料；不接線、不解除任何 Gate、不把研究候選當成核准。與同批 `NEWUI2_FIVE_PAGE_DATA_CONTRACT_AUDIT_2026-11-12.md`（下稱「五頁稽核」）互補：五頁稽核看五頁全貌，本文專看**市場頁與「市場資金與籌碼」**的欄位契約與距接線的 Gate 缺口。
> **基準**：main `7eb48d6c`（本回合 `git fetch` 實取）；資料量測日 2026-11-12（本機 `data_cache` 最新資料日 2026-11-09）。引用以「檔:符號」為主，少數行號僅對 `7eb48d6c` 成立。
> **授權來源**：客戶「方案 B」Batch 1 授權（客戶 2026-11-12 裁示；原話與編號**見後續 DEC 登錄**，本文不自編 DEC 號）。
> **圖例**：**FACT**＝本回合讀碼／讀檔／執行直接確認；**APPROVED**＝文件記載客戶已裁示（轉錄）；**RECOMMENDATION**＝AI 推薦，非裁示；**HOLD**＝客戶裁示維持未授權；**INFERENCE**＝由 FACT 推得、未實測；**NOT VERIFIED**＝未驗，不得當前提。
> **稽核分類**：READY／BLOCKED／NOT VERIFIED **僅為本文的稽核分類，不是正式 Data State enum**（正式只有 `shared/ui2_contract/models.py::FieldState` 五態，DEC-124）。READY＝該性質成立且有守衛（**不含**授權條款與接線授權）。
> **單組聲明**：本文由單一文件組整理 C1 單組調查並自行重核關鍵事實（§9），**未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。全稱句只能當待驗事項，不得作為後續動作前提，不得寫進 commit／PR 當已完成事實。**非作者獨立 QA：待做。**

---

## 0. 結論先行

| # | 結論 | 標籤 |
|---|---|---|
| 1 | **「市場資金與籌碼」區塊目前在 UI2 完全不存在**：`src/services/ui2/market_vm.py::MARKET_CARD_IDS` 固定 6 張（twii／vix／us10y／spread／dxy／pmi），`real_canonical._market` 無任何法人／融資／板塊欄位。融資 L3 與板塊 L3 在 UI2 三目錄引用＝0，全 repo 的 `.py` 內也只有兩 L3 自身、`shared/sector_flow_fact_thresholds.py`、其測試檔提到它們 | FACT |
| 2 | **DEC-164 只核准融資＋板塊兩個 L3 的「方向」；「外資淨買賣超（僅外資）」沒有 L3、也沒有授權**（文件記載：外資 L3 另案）。線框項目「外資」在資料路徑上＝BLOCKED，不只是「未接線」 | FACT（文件側） |
| 3 | **板塊聚合的外資分項與 FinMind 大盤外資同日不等，且不是固定比例**：37 個共同交易日中 36 天同號；逐日絕對差中位 55.4 億、最大 239.6 億；最新日 −942.4 vs −900.6 億（差 −41.9）。本回合唯讀重算與調查者一致 | FACT（§3.2、§9 V5） |
| 4 | `finmind_inst.parquet` 同欄兩種 `source` 標籤（`:Foreign` 4920 列／`:Foreign_Investor` 19 列）；`load_extreme_risk_legs` 只取末 5 列、不檢查 `source` | FACT（§3.3、§9 V4） |
| 5 | 三項並列時的**新鮮度規則不一致**：板塊 4 日曆天、融資／外資／TWII 7 日曆天；且**判定基準日也不一致**（板塊與融資用台北今日，TWII 卡／日 K 的新鮮度用 L1 預設主機日期）。皆不看交易日曆 | FACT（§4） |
| 6 | 融資 L3 使用者可見常數 `MARGIN_SOURCE_TEXT` 含「全市場融資金額」；板塊側有「不稱全市場」守衛，**融資側沒有**；FinMind 該 dataset 是否含上櫃 NOT VERIFIED | FACT（字面與守衛範圍）（§6 T-1） |
| 7 | **所有接線相關 Gate 維持 HOLD／未授權**（§5）。本文未暗示任何 Gate 已解除 | FACT |
| 8 | UI2、Digest、OneBrain **沒有任何「資金與籌碼」欄位的共同核准基礎**：Digest 市場段只有 regime／light／health，OneBrain 無 producer | FACT（§8） |

---

## 1. 市場頁欄位契約驗證表

欄位：`#`｜欄位（卡／區塊）｜來源／路徑（檔:符號）｜來源已核准？｜日期／期間／單位／口徑｜資格分類｜同指標多來源／口徑混用風險｜UI2／Digest／OneBrain 同基礎？

> 「來源已核准」＝repo 內已有客戶裁示（文件記載，轉錄）；「資格」＝本文稽核分類（READY／BLOCKED／NOT VERIFIED；缺值寫「缺值」）。授權條款（TWSE／TPEX／Yahoo／FRED 等）NOT VERIFIED 是全域前提，不逐列重複。

### 1-A　市場頁**現有**欄位（Real 模式，`real_canonical._market`）

| # | 欄位 | 來源／路徑 | 來源已核准？ | 日期／單位／口徑 | 資格 | 多來源／混用風險 | 同基礎？ |
|---|---|---|---|---|---|---|---|
| A1 | 核心卡：台股加權指數收盤 | `real_feed._read_twii`→`market_twii_view_service.get_twii_trend_view(1)`→`data_cache/twii_ohlcv.parquet`（Yahoo `^TWII` 1d）→`real_canonical.twii_card_spec`；契約 `validate_twii_fact`（價格≤0、負 age_days 拒用） | 是（既有 canonical，DEC-148／156 文件記載） | 最新一筆收盤，`f"{x:,.2f}"`（指數點，卡片不標單位）；as_of＝parquet 末列；`is_stale` True／False／None 皆有字樣 | READY（接線＋契約） | 低（UI2 只此一源）。Legacy 另有 session 內 `^TWII` 路徑（跨頁同指標多條取數，INFERENCE，UI2 不用） | UI2 是；Digest market 段**不含 TWII**；OneBrain 未建 |
| A2 | 主圖：20 根日 K | `real_feed._read_twii_kbar`（第二次呼叫同 service，`with_ohlc=True`）→`real_canonical.kbar_chart_spec`；與卡片同源對帳 `kbar_same_source_problem` | 是（DEC-156） | OHLC 契約 `shared/twii_ohlc_contract`；不足 20 根照實少畫；as_of／最新收盤／來源與卡片逐項對帳，不一致→紅 | READY（對帳失敗→Unavailable）；MA／量／更長視窗 BLOCKED（需 Visual Gate） | 兩次讀取可能不同快照→已有對帳守衛（`tests/test_ui2_twii_kbar.py`） | 同 A1 |
| A3 | 現在狀態＝市場位階 | `real_feed._read_regime`→`allocation_service.get_macro_regime(strict=True, require_valid_risk_cap=True)`→`macro_state_locker.get_macro_state`→`real_canonical.regime_spec` | 是（DEC-124／074／075 字樣；位階為全站單一橋樑） | 類別值；**契約無 as_of**（畫面 `⬜ 資料日未提供`）；`light` 在 `RegimeFact` 內但**畫面不渲染** | READY（接線）；**本沙箱實測 `unloaded`**（`is_loaded=False`），部署端 NOT VERIFIED | `get_macro_state` 對非 canonical regime 洗成 `neutral` 且 `is_loaded=True`、`light` 直通不驗（`I1140-MACRO-STATE-NONCANON`，既知、被測試釘住、不動）→ 同一標籤可能掩蓋上游異常 | UI2 與 Digest 位階來自同一函式，但 **Digest 無 production caller**；兩邊各有一份白名單集合（`REGIME_LABEL` vs `REGIME_LIGHT`），**無等式測試**（`I1140-REGIME-SET-EQ`） |
| A4 | Risk Cap（context row） | `real_canonical._risk_cap_row` 固定 | 契約固定（Freeze §0.1.4） | 恆 `⬜ 無法判定`，不讀 `exposure_limit_pct` | 缺值（刻意） | 無 | UI2 不顯示；Digest 另有 `risk_cap.*` 路徑 → 兩邊**有意不同** |
| A5 | 核心卡：VIX | `_not_provided`（`此項目尚未開放`）；候選：`macro_snapshot.fetch_vix_block`（yfinance 直連）／session `macro_info['vix']` | 來源路徑存在但**未接**；無乾淨 L3 | — | 缺值 | VIX 另有 FRED／CBOE 說法（憲法 §2.1，與碼不符，見五頁稽核 C5）；DEC-070「只用已完成收盤」僅語意裁示、程式未實作 | 無 |
| A6 | 核心卡：US 10Y | `_not_provided` | 未接；口徑 D1＝FRED DGS10（僅口徑，轉錄） | — | 缺值 | ⚠ 最典型「同指標不同來源」：FRED `DGS10` vs Yahoo `^TNX`（Legacy 有揭露）。接線時不明示單一來源→混用（憲法禁止平均） | 無 |
| A7 | 核心卡：利差 | `_not_provided`（「尚無正式定義」） | 無正式定義（10Y-2Y／10Y-3M／M1B-M2 擇一） | — | 缺值（BLOCKED：業務定義） | 三種定義不可互換 | 無 |
| A8 | 核心卡：DXY | `_not_provided` | 未接；Yahoo `DX-Y.NYB` 單源，舊備援鏈可落到 ETF | — | 缺值 | 低（單源）；備援鏈風險見五頁稽核 X-06 | 無 |
| A9 | 核心卡：PMI／景氣 | `_not_provided`（台灣 PMI 與景氣燈號意義不同，待定義） | 未接；`tw_pmi` 為 proxy（DEC-155：不得為正式訊號） | 月頻 | 缺值（BLOCKED：業務定義） | PMI 多源賽跑取第一命中、禁平均；PMI 與景氣燈號是不同指標 | 無 |
| A10 | OneBrain Outlook | `_not_provided`（`_R_STAGE_G`） | OneBrain runtime 未授權（永久禁止清單，文件側） | — | 缺值 | 無 | OneBrain 未建 |
| A11 | 為什麼／指標明細／原始資料表 | `_not_provided`（`why.regime_explain` 已接線） | 未接 | — | 缺值 | 無 | 無 |
| A12 | 今日結論／今日主要風險 | `_not_provided` | 未提供 | — | 缺值 | 無 | 無 |
| A13 | 是否需行動／下一步 | `vm_common.aggregator_pending_field` | 待 System Action Aggregator | — | 缺值 | 無 | 無 |

統計（A，13 列；調查者計）：**真實且有使用資格＝3**（A1、A2、A3；A3 僅 `is_loaded=True` 時）；契約固定缺值＝1（A4）；capability not_provided 缺值＝9（A5～A13，其中 A7、A9 另卡在業務定義）。Real 模式下 Preview／FAKE 資料＝0（FAKE 只存在於 `scenarios.py`；`tests/test_ui2_guards.py::test_everything_is_labelled_fake` 守 FAKE 標示）。計數為調查者人工分類，本回合未重算。

### 1-B　DEC-164 已核准方向、但**未接線**的「市場資金與籌碼」三項

| # | 項目 | 資料路徑 | 有 L3？ | 來源已核准？ | 日期／單位／口徑（本回合實測） | 資格 | 口徑混用風險 | 同基礎？ |
|---|---|---|---|---|---|---|---|---|
| B1 | **外資淨買賣超（僅外資）** | `scripts/update_macro_history.py::fetch_finmind_inst`→`data_cache/finmind_inst.parquet`（欄 `date foreign_buy source fetched_at`；億元，買−賣÷`TWD_PER_YI`）；L1 僅 `macro_cache_reader.load_extreme_risk_legs`（吐 `foreign_5d_yi`／`foreign_date`，非「最新日＋as_of＋stale」） | **無**（外資 L3 另案） | **未核准** | 4939 列；`source` 兩種標籤（§3.3）；`:Foreign_Investor`（新）2026-10-12 起 19 列 | BLOCKED（無 L3、無授權）；資料檔可讀 | 高：單點顯示尚可；任何跨 2026-10-08／10-12 的多日加總混兩種口徑 | Digest 無此欄；OneBrain 未建 |
| B2 | **融資餘額（大盤）** | `margin_fact_service.get_margin_fact`（`_evaluate`）←`macro_cache_reader.load_v2_chart_series()['margin']`←`data_cache/finmind_margin.parquet`（`margin_balance` 元→億） | **有**（#1142），0 production caller | 方向已核准；**接線未核准**（`I1144-WIRING-GATE`） | 本回合讀 L3：`OK`、**5399.15741 億**、as_of 2026-11-09、`is_stale=False`、`age_days=3`；sanity 開區間 (500, 10000) 億；歷史內部單位混用僅驗最新點（`I1140-MARGIN-UNIT-MIX`） | 資料層 READY／接線 BLOCKED | `MARGIN_SOURCE_TEXT` 含「全市場融資金額」（§6 T-1）；FinMind 該 dataset 是否含上櫃 NOT VERIFIED | 同上 |
| B3 | **板塊資金流（最新交易日三大法人合計淨額）** | `sector_flow_fact_service.get_sector_flow_fact`←L1 `src/data/sector_flow/reader.py`←cron `scripts/update_sector_flow.py`→L2 `src/compute/sector_flow.py::compute_sector_daily_net` | **有**（#1142），0 production caller | 方向已核准（G-3 方案 A、G-10）；接線未核准 | 本回合讀 L3：`OK`、`complete`、universe 41／觀測 38／未觀測 3、合計 **−920.24812237 億**、正 11／負 27／持平 0、as_of 2026-11-09、非 stale；單位億；口徑＝（外資＋投信＋自營）張×1000 股×收盤÷1e8 | 資料層 READY／接線 BLOCKED | 金額定義與 B1 不同（張×收盤估算 vs 申報買賣金額差）；合計含 ETF／ETN／受益證券／存託憑證（caveat `scope_includes_etf_etn_and_receipt_labels`） | 同上 |

統計（B，3 列）：資料層 READY＝2（B2、B3，**接線資格 BLOCKED**）；BLOCKED（無 L3＋無授權）＝1（B1）。

---

## 2. (a) 衍生板塊聚合與 Coverage（G-3 方案 A）

**FACT — 聚合方法**（讀碼）

1. 個股層 `src/compute/sector_flow.py::compute_sector_daily_net`：張數 × `SHARES_PER_LOT` × 收盤價 ÷ `YUAN_PER_YI`；三分項任一 NaN → 淨額 NaN（`min_count=3`）；有法人列但缺／非正收盤價 → **該股該日剔除**（以 `how="inner"` 合併；計數 `n_dropped_missing_price`）；無產業別 → 「未分類」桶；外幣 ETF（代號前綴 `00` 且第六碼 K／C／M／S，`shared/sector_flow_thresholds.py`）排除。
2. 標準化 `canonicalize_sector_daily`：別名表合併、重複 (date, 標籤) raise、不丟列。
3. L3 `sector_flow_fact_service`：母體 `universe` 取自標準板塊清單（窗口 20 交易日內任一天出現過）；最新日無列的板塊 → `sign="unobserved"`、`net_yi=None`；正／負／持平以具名 ε 判定；`rows` 依板塊名排序，不依金額。
4. 衍生聚合 `SectorFlowDerived`：**只在 `completeness == complete` 時給**；恆等式（正＋負＋持平＝觀測數、觀測＋未觀測＝母體）於建構時強制；對帳（逐列 net＝foreign＋trust＋dealer、原始合計 vs 標準化合計）失敗 → UNAVAILABLE。

**FACT — Coverage 如何計算與呈現**

- L3 `SectorFlowCoverage` 是**板塊標籤層級**：本回合 `n_universe=41、n_observed=38、n_unobserved=3`（未觀測：化學生技醫療、未分類、電子工業）。**不是個股覆蓋**：`n_stocks` 只是各板塊實際入帳股數加總，沒有分母；`daily_net.parquet` 欄位為 `date sector net_amt_yi foreign_yi trust_yi dealer_yi n_stocks twse_ok tpex_ok source industry_ok industry_scheme fetched_at`，**不存個股代碼**，故個股／金額／市值覆蓋皆**算不出**。
- 缺價被剔除的個股：`metadata.json` `per_day['20261109']`＝`twse_inst 17119、tpex_inst 911、twse_close 1381、tpex_close 1003`；`coverage.n_stock_days_with_net=18026`、`n_dropped_missing_price=15761`，**18026−15761＝2265＝Σ n_stocks（算術吻合，本回合重核）**。`twse_close＋tpex_close＝2384` 與 2265 差 119，原因未知（NOT VERIFIED）；15761 的組成（INFERENCE：T86 `selectType=ALL` 含大量權證等非股票工具）未逐檔驗證（`I1140-SECTOR-DROPPED-PRICE`）。
- **L3 不輸出 `n_dropped_missing_price`**：`sector_flow_fact_service` 只取 `metadata.coverage` 的 `n_excluded_foreign_ccy_stock_days`、`n_unclassified_stock_days`、`n_days`（本回合讀碼）。且這些診斷計數是**上一次 cron 範圍**（`coverage.n_days=1`），L3 的 caveat 碼已帶 `_last_cron_run_scope` 命名揭露範圍。→ **使用者看不到「合計」背後被剔除的股數**（候選 N-4）。
- 板塊「缺列」（unobserved）→ `None`，不計入合計與正負持平，並加 caveat `sectors_unobserved_on_data_date`。
- **「不能冒稱全市場」**：L3 無任何 market／全市場欄位；測試 `tests/test_sector_flow_fact_service.py::test_no_market_wide_or_forbidden_fields`、`::test_no_market_wide_in_reason_caveat_codes` 守住，但這些守衛只管 **L3 識別字與 `repr`**，**沒有任何使用者可見文案或 UI 層守衛**（UI 尚不存在）；線框草稿用詞「全體淨額合計」有被讀成全市場的風險（INFERENCE，文案屬後續 Gate）。
- 合計實際範疇（FACT，文件側）：含 ETF／ETN／受益證券／存託憑證，排除外幣 ETF 與無有效收盤股 → 「合計」＝**入帳工具的三大法人張數×收盤價加總**，**不是**「全市場三大法人淨額」。
- 本回合另見：`data_cache/sector_flow/metadata.json` `bubble_window.n_absent_cells=53`（板塊×日空格）與 `n_member_absent_cells=0`（ETF 家族成員缺席，`I1140-ETF-FAMILY-ABSENT` 針對此項）是**不同的量**，勿混。

**結論 (a)（一句）**：衍生聚合在**板塊標籤層級**的缺值處理與恆等式／對帳守衛完整（缺值不補 0、不等於全市場、不排序），但 Coverage 只能表達 38／41 個標籤、無法表達個股或金額覆蓋，且缺價被剔除的股數不外露——「不誤導的合計」能否成立，取決於尚未裁示的 DG-COV。

---

## 3. (b) 三大法人 vs 外資口徑

### 3.1 取數路徑（讀碼，FACT）

| 路徑 | 來源／口徑 | 單位 | 去向 |
|---|---|---|---|
| ① TWSE BFI82U（大盤，三類） | `daily_data_fetchers._parse_bfi82u_rows`／`fetch_institutional`；外資＝外資及陸資（**不含**外資自營商），自營＝自行＋避險（`shared/inst_labels.py`） | 億元（元÷1e8，按「買賣差額」欄名定位） | Legacy（section_chips／page_market 等）；**UI2＝0 命中，Digest＝0**。「TWSE 僅含上市」為領域知識，repo 內無明文（INFERENCE） |
| ② FinMind `TaiwanStockTotalInstitutionalInvestors`（只取外資） | `scripts/update_macro_history.py::fetch_finmind_inst`→`finmind_inst.parquet` | 億元（買−賣金額） | `macro_cache_reader.load_extreme_risk_legs`（`foreign_5d_yi`，極端風險橫幅）；**UI2／Digest＝0**；即 B1 |
| ③ TWSE T86＋TPEX 個股（三類，張） | `data_loader_inst_fetchers`（`_get_t86_day`／`_get_tpex_day`）；cron 板塊用 | 張→×1000 股×收盤→億 | 板塊 `daily_net.parquet`；個股頁 fallback |
| ④ FinMind 個股法人 | `data_loader._fetch_finmind_inst_raw` | 股／張 | 個股頁 |

### 3.2 外資（板塊分項）vs 外資（FinMind 大盤）：實證不等（FACT，本回合重算）

方法：`python -I` 唯讀 `pd.read_parquet`；`data_cache/sector_flow/daily_net.parquet` 逐日 `foreign_yi` 加總（所有原始標籤列，無 NaN）inner-join `data_cache/finmind_inst.parquet` 逐日 `foreign_buy` 加總。

| 項目 | 值 |
|---|---|
| 共同交易日 | 37（2026-09-11～2026-11-09） |
| 同號天數 | 36／37 |
| 逐日絕對差 | 中位 **55.42** 億；最大 **239.57** 億 |
| 最新日 2026-11-09 | 板塊外資分項 −942.44 vs FinMind 外資 −900.56（差 −41.87）億 |
| 近 3 日差（板塊−FinMind） | 11-05：+49.19；11-06：+127.20；11-09：−41.87 |

成因＝**INFERENCE（未逐項驗）**：板塊用「張數×**收盤價**」估算，FinMind 用申報買賣金額差；板塊含上櫃，FinMind 該 dataset 是否含上櫃 NOT VERIFIED。→ 同一個「外資」字眼在兩處數字不同，**不可並列、加減**（G-10）。目前**沒有單一 SSOT 標籤常數**同時定義兩個口徑字樣（L3 只有描述性 `SectorFlowBasis`；無外資 L3）。

### 3.3 `finmind_inst.parquet` 內部口徑斷點（FACT：標籤分布；NOT VERIFIED：成分）

- `source` 欄（本回合實測）：`FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign`＝4920 列，日期 2006-09-29～2026-10-08；`…:Foreign_Investor`＝19 列，日期 2026-10-12～2026-11-09。
- `fetch_finmind_inst` docstring（批 Z40，客戶 2026-10-11 官方口徑）自述：新口徑只取 `Foreign_Investor`（外資及陸資，不含外資自營商）；既有 `:Foreign` 舊列口徑隨時期而異（2017-12-18 前 FinMind 來源端本身含外資自營商；2017-12-18 起至上線日存 Foreign_Investor＋Foreign_Dealer_Self），歷史不重抓，列級 `source` 可分辨。**這些成分敘述是 docstring 對「派工規格所載實測事實」的轉述，自述「本批未重抓驗證」→ 本文 NOT VERIFIED。**
- `docs/vnext/NEWUI2_MARKET_CHIPS_OLD_UI_FIRST_MAPPING_2026-11-11.md` §1.1 的敘述（只寫「2017-12-18 前」）與上述 docstring 三時期說法不完整對應（候選 N-2；文件更正屬 §-1，有任務碰到才動）。
- 單點（最新列）安全；任何 ≥19 列的多日彙總會跨斷點。`load_extreme_risk_legs` 的 `foreign_5d_yi` 只取末 5 列、只讀 `date`／`foreign_buy` 兩欄、**不檢查 `source`**（本回合讀碼）；目前 5 日窗在新口徑內（INFERENCE，因 19≥5）。
- 最後一筆 `:Foreign` 與第一筆 `:Foreign_Investor` 的日期切點（2026-10-08／10-12）與 docstring 所述的上線日期（2026-10-11 客戶裁示）吻合（INFERENCE：切換發生於該批上線時）。

### 3.4 同一標籤可能顯示成不同口徑的四個具體風險點

1. **外資 vs 三大法人合計（G-10）**：B1「僅外資」與 B3「三大法人合計（外資＋投信＋自營）」金額定義不同（§3.2）。
2. **`finmind_inst` 內部斷點**（§3.3）。
3. **BFI82U 預填 0.0**：`daily_data_fetchers._parse_bfi82u_rows` 對未觀測格預填 `0.0`，以 `InstNetDict.unobserved_net` 另記（`shared/inst_net.py`）；只有部分消費點讀旗標，其餘仍讀 0.0（`inst_net.py` 頭註自陳）。屬 Legacy 路徑；UI2 日後若取 BFI82U，必須用 `is_net_observed`。
4. **新鮮度規則不一致**（§4）。

**結論 (b)（一句）**：口徑差異在資料層與 L3 層已被正確區分（Z40 `inst_labels` SSOT、L3 `SectorFlowBasis`），但**尚無外資 L3、無單一標籤 SSOT**，且 `finmind_inst` 存在時間序列口徑斷點；目前只靠線框文字約定，無法保證日後 UI 不把「外資」與「三大法人合計」以相近標籤顯示。

---

## 4. (c) 缺值／過期語意與 stale 閾值不一致

**FACT — 兩個 L3 的缺值／過期語意**

- 融資 L3 與板塊 L3 都用 `FieldState`（OK／STALE／MISSING／UNAVAILABLE），**只有 OK／STALE 可帶值**（兩者 `__post_init__` 強制）；reason→state 為單一 dict，測試窮舉。兩 L3 皆不使用 `NOT_EVALUATED`。
- 缺值≠0：板塊 NaN／inf → 整份 UNAVAILABLE；`net_yi=None ⇔ unobserved`；`test_nan_never_converted_to_zero`、`test_zero_is_valid_observation_counted_flat_not_unobserved`。融資 inf／NaN → MISSING、sanity 失敗 → MISSING（不給值）。
- stale 判定：板塊＝`reader._compute_staleness`，只看 `metadata.last_updated`（**資料觀測日**），缺／壞／晚於今日／晚於排程執行日一律 stale 且觀測日不外露，**絕不以 `updated_at`（cron 時刻）頂替觀測日**；融資＝L1 attrs，`is_stale` 非布林 → `STALE freshness_undetermined`；未來日 fail closed。
- Real 模式現有缺值：A5～A13 九欄皆 `⬜ 尚未提供`（capability），**沒有任何一欄被呈現為 0／中性／正常**（`tests/test_ui2_real_feed.py::test_every_unwired_real_field_states_its_reason`、`::test_only_wired_fields_carry_data_across_injected_combinations`）。

**FACT — 新鮮度閾值與基準日不一致（候選 N-1）**

| 項目 | 閾值 | 基準日 | 出處（符號） |
|---|---|---|---|
| 板塊 | **4** 日曆天 | 台北今日（`tw_now().date()`） | `shared/sector_flow_thresholds.SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS`；`src/data/sector_flow/reader._compute_staleness` |
| 融資 | **7** 日曆天（`STALE_DAYS_DAILY`，經 `CACHE_DATASET_CADENCE['finmind_margin']='daily'`） | 台北今日（L3 顯式傳入 `_taipei_today()`） | `shared/staleness.py`；`margin_fact_service._taipei_today` |
| 外資（`finmind_inst`） | **7**（同上） | L1 預設主機 `date.today()` | `macro_cache_reader.compute_cache_staleness` |
| TWII 卡／日 K | **7**（同上） | 新鮮度走 L1 預設主機 `date.today()`；日 K 未來日判定用台北今日 | `market_twii_view_service.get_twii_trend_view(today=None)` |
| PMI | `tw_pmi` 未登錄 `CACHE_DATASET_CADENCE` → 必回 stale | — | `macro_cache_reader` |

→ 三者都不看交易日曆；**同一資料日在連假期間可能板塊判過期、外資／融資不判**（INFERENCE：兩個閾值不同；`SUPPLEMENT I-5` 文件側亦有同見）；基準日也分「台北／主機」兩種（部署主機時區 NOT VERIFIED；`I1140-TODAY-TZ` 條件式 Gate 已登記）。

**INFERENCE／缺口**

- `partial`／`unknown`（板塊 `completeness`）**不在 `FieldState` 五態內**（DEC-124 釘「恰為五個」，`tests/test_ui2_guards.py::test_dec124_data_semantics_are_exactly_the_five`）。線框的 `partial` 狀態必須另行映射（如 OK＋chip），**目前無映射、無測試**（候選 N-3）。
- `not_provided`（`CapabilityState`）是 Preview-only marker（`test_dec124_capability_marker_is_preview_only`）。日後三欄接線後，該標記必須退出這三欄；現有守衛是否阻擋「Real 後仍用 not_provided」**未驗證**（NOT VERIFIED）。

**結論 (c)（一句）**：兩個 L3 對缺值／stale／未來日一致使用 `FieldState` 四態且缺值不為 0，Real 模式未接欄位全為 `⬜ 尚未提供`；缺口在 `partial` 無對應狀態映射，以及三項 stale 閾值（4 日 vs 7 日）與基準日（台北 vs 主機）不一致。

---

## 5. (d) 距離正式接線的 Gate 缺口表

> 「誰能解除」依文件記載：**客戶**＝需客戶裁示；**總管**＝AI 總管依 v3 §03-1 內部可拍板。**本表未宣稱任何 Gate 已解除。** 狀態皆為文件記載（BACKLOG／DECISIONS）；ID 均已 grep 確認存在。

| Gate ID | 內容 | 狀態 | 誰能解除 | 已有證據 | 缺什麼證據／輸入 |
|---|---|---|---|---|---|
| `I1144-WIRING-GATE` | 是否授權 UI2 runtime 接線（feed／section／allowlist／snapshot／canonical／VM／view） | **未授權**（DEC-164 G-9、DEC-165） | 客戶 | 前置研究 `UI2_RUNTIME_PREGATE_RESEARCH_2026-11-11.md`＋補強；接線面清單（`tests/test_ui2_guards.py::G2F_IMPORT_ALLOWLIST`、`tests/test_ui2_real_feed.py` 的 `WIRED_PATHS`） | 客戶授權；DG-COV／PIT／LIC／SCOPE 先決 |
| DG-COV＝`I1140-COVERAGE-MIN` | 板塊最低 coverage 門檻、母體口徑 | **未裁示**；不得自設百分比 | 客戶 | L3 coverage 38／41；計數恆等式 | 客戶選擇；若要個股／金額／市值覆蓋 → 需逐檔落地＋官方清單＋授權＝新儲存／新來源（未授權）；`n_dropped_missing_price` 組成 |
| DG-PIT | 無 `release_date` 下，是否接受「資料日＋抓取時間（明示非發布時點）」 | **未裁示** | 客戶 | 三資料集僅 `date`＋`fetched_at`（本回合讀欄位確認：`finmind_inst` 為 `date foreign_buy source fetched_at`，`daily_net` 無 `release_date`）；融資 `fetched_at` 對多數列為 bootstrap 單一時點（文件側） | 客戶裁示；若要真 PIT → 需來源發布日證據（現無）；parquet 不保存修訂版本 |
| DG-LIC＋`I1144-LIC-THREE-QUESTIONS` | TWSE／TPEX／FinMind 於 Cloud 呈現與衍生聚合的授權（是否商業／是否公開／公開 repo 是否保留個股級列） | **HOLD**；FinMind PARTIALLY、其餘 NOT VERIFIED | 客戶／法務 | `UI2_RUNTIME_PREGATE_EVIDENCE_SUPPLEMENT` §11 對照矩陣；`PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT` | 官方條款原文（沙箱連不到）；客戶／法務判斷 |
| DG-SCOPE | 接線範圍：先融資一項（A）／先關 Gate（B）／融資＋板塊（C） | **未裁示**（AI 推薦 B→A，非裁示） | 客戶（§8.4 step 4，須附推薦） | PREGATE §5.2 三方案 | 客戶選擇 |
| 外資 L3 | 「外資淨買賣超（僅外資）」唯讀 L3＋授權 | **未授權、另案** | 客戶（授權）；總管（技術設計） | `finmind_inst.parquet`、`load_extreme_risk_legs`；Mapping §3 提案 | 客戶授權；`:Foreign` 斷點揭露方式；與板塊口徑的單一標籤 SSOT |
| `I1140-MARGIN-SOURCE-TEXT` | `MARGIN_SOURCE_TEXT` 含「全市場融資金額」 | open，未處理 | 總管＋客戶（文案） | 本文 §6 T-1；FinMind dataset 是否含上櫃 NOT VERIFIED | 事實查證（dataset 範圍）＋文案裁示 |
| `I1140-ETF-FAMILY-ABSENT` | 家族成員缺席時 L3 未揭露 | open；目前 `n_member_absent_cells=0`（潛在） | 總管 | `metadata.json bubble_window`（本回合讀檔確認） | L3 輸出該計數＋揭露文案 |
| `I1140-SECTOR-CRON-SCOPE` | 診斷計數是「上一次 cron」範圍 | open | 總管 | L3 caveat 碼已帶 `_last_cron_run_scope`；`coverage.n_days=1` | 接線文案不得寫成整窗 |
| `I1140-SECTOR-UNOBS-LABELS`／`-DROPPED-PRICE` | 3 個偶發標籤成因、15761 組成 | open，成因 NOT VERIFIED | 總管（獨立一組查證） | §2 算術吻合 | 逐檔資料（現無，`daily_net` 不存個股代碼） |
| `I1140-MARGIN-UNIT-MIX` | 融資歷史內部單位混用僅驗最新點 | open，條件式（取歷史序列／趨勢才觸發） | 總管 | `shared/margin_schema.py` 頭註 | 8 月混用列「修掉或重建」NOT VERIFIED |
| G-F3／G-F4／G-F5（間接） | A2 stale 取向／Digest v2 PIT／production caller 時機 | 待裁示；歸類「間接，不阻塞」＝**INFERENCE** | 客戶 | PREGATE §4.1 | 客戶或獨立 QA 確認「不阻塞」歸類 |
| G-F2／G-F6、`I1144-DG-A3`、`I1144-DG-HEALTH`（非前提） | 持股授權／登入／配對／health 範圍 | 未授權；歸類「非市場頁前提」＝**INFERENCE** | 客戶 | BACKLOG | 同上 |
| `I1144-DATA-STORAGE-DECISION` | 是否修改公開 repo 的資料保存方式 | **待客戶裁示，非動工項** | 客戶 | `PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT` | 客戶裁示 |
| **N-1（新增候選，本批提出、未登記）** | 三項並列的新鮮度閾值（4／7 日）與基準日（台北／主機）不一致 | 未登記於 BACKLOG（grep `SECTOR_FLOW_STALE_MAX` 僅命中歷史列，調查者查） | 總管（技術）＋客戶（若要統一語意） | §4 | 是否需統一屬業務語意（待判） |
| **N-2（新增候選）** | `finmind_inst` `:Foreign` 斷點在 Mapping 文件的敘述不完整 | 文件與 docstring 不一致 | 總管（文件更正；§-1：有任務碰到才動） | §3.3 | docstring 成分說法需重抓驗證（NOT VERIFIED） |
| **N-3（新增候選）** | `partial`／`unknown` 無對應 `FieldState` 映射 | 無映射、無測試 | 總管（映射設計）；客戶（若涉畫面） | §4 | 映射設計與線框確認 |
| **N-4（新增候選）** | 缺價剔除股數 `n_dropped_missing_price` 在 L3 不外露 | `sector_flow_fact_service` 只取三個診斷 key | 總管 | §2 | 是否外露、如何避免被讀成覆蓋率 |

> N-1～N-4 為**候選**，尚未登記為 BACKLOG 條目，**不是 Gate、不是待辦授權**；登記屬治理 PR，由總管另案處理。

---

## 6. (e) 測試守衛盤點與缺口

> 以讀測試原始碼為主；**本回合未重跑調查者自報的 pytest 數字**；測試名均已 grep 確認存在。是否綠燈、是否有牙（除檔內自稱 `has_teeth` 者）NOT VERIFIED。

### 6.1 現有守衛（代表性）

| 範圍 | 守住的性質 | 測試（檔::函式） |
|---|---|---|
| 融資 L3 | 單位量級錯誤拒收、sanity 開區間 | `tests/test_margin_fact_service.py::test_unit_off_by_1e3_rejected`、`::test_sanity_reject`、`::test_sanity_accept` |
| 融資 L3 | 缺值≠值（缺檔／空／缺欄／壞檔／全 NaN／inf） | `::test_missing_file`、`::test_empty_file`、`::test_non_finite_latest`、`::test_every_non_value_scenario_has_none_value` |
| 融資 L3 | 重複日期 fail closed、未來日／as_of 對帳、stale 邊界 | `::test_duplicate_last_date_real_path_fails_closed`、`::test_future_asof_plus_one_rejected`、`::test_stale_boundary_7_days_not_stale_8_days_stale` |
| 融資 L3 | 無判讀／無 UI／無網路／未接線 | `::test_no_threshold_or_judgement_in_source`、`::test_source_has_only_fixed_user_visible_strings`、`::test_scope_guard_not_wired_to_ui_or_real_feed` |
| 融資 L3 | 真實快取釘住 | `::test_real_cache_pinned_snapshot`（快取更新則 skip） |
| 板塊 L3 | 只用最新日、rows 依名稱 | `tests/test_sector_flow_fact_service.py::test_only_latest_day_used_not_window_sum`、`::test_rows_sorted_by_name_not_amount_and_not_bubble_order` |
| 板塊 L3 | 缺值≠0、未觀測不入合計、重複列不靜默相加 | `::test_nan_never_converted_to_zero`、`::test_unobserved_sectors_not_in_total_or_signs`、`::test_duplicate_rows_are_not_silently_summed_nor_dropped` |
| 板塊 L3 | 對帳與恆等式；完整性≠覆蓋度；partial 不給 derived | `::test_reconcile_failure_when_canonicalization_changes_total`、`::test_completeness_is_flag_completeness_not_coverage`、`::test_partial_gives_rows_but_no_derived` |
| 板塊 L3 | stale 邊界（4 日）、觀測日未知⇒stale | `::test_stale_boundary_4_days`、`::test_observation_date_unknown_is_stale_true` |
| 板塊 L3 | 不稱全市場、無 UI 引用、純讀 | `::test_no_market_wide_or_forbidden_fields`、`::test_no_ui_or_vm_references_the_new_service` |
| 板塊 L3 | 真實快取（41／38／3、−920.248 億） | `::test_real_data_cache_once` |
| UI2 契約／接線 | 五態恰五個、紅色只給 Unavailable、capability 只限 Preview | `tests/test_ui2_guards.py::test_dec124_data_semantics_are_exactly_the_five`、`::test_red_is_only_for_unavailable_never_for_unloaded`、`::test_dec124_capability_marker_is_preview_only` |
| UI2 契約／接線 | feed 唯一 I/O 檔、精確白名單 | `::test_g2f_feed_files_are_exactly_the_named_one` |
| UI2 Real | 只接線 3 事實、其餘逐項說明原因 | `tests/test_ui2_real_feed.py::test_every_unwired_real_field_states_its_reason`、`::test_only_wired_fields_carry_data_on_sandbox_reality` |
| UI2 Real | TWII：未知新鮮度非 OK、契約違反隔離 | `::test_twii_unknown_freshness_is_never_ok`、`::test_twii_broken_contract_is_loud_and_isolated` |
| Digest | 位階／燈號白名單、SSOT 推導＋突變測試 | `tests/test_decision_digest_builder_regime_light_whitelist.py`（檔名；函式細項本回合未逐一核） |

### 6.2 「應有守衛但沒有」（只列，不補；皆為 INFERENCE／缺口觀察）

| # | 缺口 | 依據 |
|---|---|---|
| T-1 | 無守衛禁止融資 L3 使用者可見常數含「全市場」（板塊側有，融資側無） | `MARGIN_SOURCE_TEXT`＝「本地融資餘額歷史快取（FinMind 全市場融資金額，元換算為億元；每日更新）」（本回合讀碼）；`test_source_has_only_fixed_user_visible_strings` 只限定常數名稱集合、不禁內容（調查者讀） |
| T-2 | 無單一 SSOT 標籤常數＋測試保證「外資（僅外資）」與「三大法人合計」字樣永遠分開 | 外資無 L3；`SectorFlowBasis` 僅描述性；線框約定僅在文件 |
| T-3 | 無測試比較三項的 stale 語意（4 日 vs 7 日、台北 vs 主機基準日） | `reader.py` 與 `staleness.py` 各自測試，無跨項測試 |
| T-4 | 無測試覆蓋 `finmind_inst` `source` 標籤斷點（多日加總是否跨口徑） | `load_extreme_risk_legs` 不檢查 `source`（本回合讀碼） |
| T-5 | `partial`／`unknown` 無對 UI 狀態的映射測試 | `FieldState` 五態不含 partial |
| T-6 | L3 不輸出缺價剔除股數，也無測試要求 coverage 與 derived 一併外露 | `sector_flow_fact_service` 只取三個診斷 key |
| T-7 | UI2 `RegimeFact`／Digest 白名單兩份集合無等式測試 | `I1140-REGIME-SET-EQ` |
| T-8 | 未來接線時「Real 欄位不得再用 `not_provided`」缺反向守衛 | `WIRED_PATHS` 為手工清單；capability 守衛只限制 Preview 外使用 |
| T-9 | 真實快取釘住測試日期後只 skip，快取更新後不再驗該 L3 數值回歸 | `test_real_cache_pinned_snapshot`（融資側） |

---

## 7. 結論（僅稽核分類；非授權、非 Gate 解除）

| 分類 | 項目 |
|---|---|
| **READY（資料層／L3 層，不含接線）** | 融資 L3（B2）缺值語意、單位 sanity、未來日 fail closed、四態映射；板塊 L3（B3）缺值不補 0、恆等式與對帳、衍生聚合僅 complete 時給、不排序、不稱全市場（程式識別字層）；UI2 現有 3 真實欄（A1–A3）契約與隔離；Real 模式下 9 個未接線欄皆明示 `⬜ 尚未提供`，無 0／中性冒充 |
| **BLOCKED** | UI2 接線（`I1144-WIRING-GATE` 未授權）；DG-COV；DG-PIT；DG-LIC；DG-SCOPE；外資 L3（B1，無 L3＋無授權）；利差與 PMI 卡（需業務定義）；VIX／US10Y／DXY 卡（無乾淨 L3；US10Y 有 FRED／`^TNX` 雙口徑待裁） |
| **NOT VERIFIED** | 上游授權與再散布（TWSE／TPEX／FinMind 條款）；PIT 發布日；Cloud／真機／Playwright／新區塊量測；FinMind 外資／融資 dataset 是否含上櫃；`:Foreign` 列成分（docstring 轉述）；15761 與 119 差額的組成；3 個偶發板塊標籤成因；`n_dropped_missing_price` 是否皆為非股票工具；本回合所有測試的實際執行結果；部署主機時區 |

---

## 8. UI2／Digest／OneBrain 是否同一核准資料與規則基礎（只寫有證據的）

- **UI2 ↔ Digest（FACT）**：兩者位階都來自 `get_macro_state`（UI2 經 `get_macro_regime`）。Digest `_market_section` 只組 `market.regime`／`market.light`／`market.health` 三個 Fact（本回合讀碼）；其白名單由 `shared/regime_arbiter.REGIME_LIGHT` 推導，UI2 `validate_regime_fact` 用 `REGIME_LABEL`＋已知 source 集合——**兩份集合不同源、無等式測試**（`I1140-REGIME-SET-EQ`）。Digest **不含** 法人／融資／板塊／TWII／VIX 等任何資金籌碼欄位 → 「資金與籌碼」三項**沒有任何 Digest 消費者**（Digest 對該區塊＝不適用；INFERENCE：因 Digest 契約凍結、無對應事實欄）。
- **Digest production caller**：`decision_digest_*` 在非測試的 `.py` 中只被 digest 自家三檔（`shared/decision_digest_terms.py`、`src/services/decision_digest_assembly.py`、`src/services/decision_digest_builder.py`）提到（本回合 grep）。
- **UI2 ↔ OneBrain**：OneBrain 在 UI2 為 `_R_STAGE_G` not_provided；runtime／provider 屬永久禁止清單（文件側）。**無共同基礎可言＝N/A。**
- **UI2 ↔ Legacy New UI**：Legacy 的 `page_market` 已顯示 BFI82U 三大法人與融資原始值，含寫死註記「融資燈門檻已失準；歷史單位混用區間屬資料疑義」（文件側，Mapping §1.2）；UI2 刻意不沿用。
- **其餘**：UI2 三項真值欄（A1～A3）與 Digest／OneBrain 是否同一「核准資料與規則基礎」——除位階共用 `get_macro_state` 外，**NOT VERIFIED**。

---

## 9. 本回合重核紀錄、勘誤與限制

### 9.1 重核（方法與結果）

| # | 項目 | 方法 | 結果 |
|---|---|---|---|
| V1 | 預設路徑只到 FAKE | `src/ui2/shell/app.py` 讀碼＋`grep ui2 app.py`＝0 行 | 一致（細節見五頁稽核 §10 V1） |
| V2 | REAL 帶真值＝台股卡＋日 K；位階已接線但恆 unloaded | 沙箱 `read_real_snapshot()`：`regime=unknown/⬜/unloaded/is_loaded=False`；`twii.close=(41661.69921875,)`、`as_of=2026-11-09`、`age_days=3`、`is_stale=False` | 一致 |
| V3 | 兩 L3 在 UI2 三目錄引用＝0 | `grep -rln … src/ui2 src/services/ui2 shared/ui2_contract`＝無輸出；全 repo `.py` 只命中兩 L3 自身／`shared/sector_flow_fact_thresholds.py`／兩測試檔 | 一致（僅靜態 `.py`） |
| V4 | `finmind_inst` source 斷點 | 唯讀 parquet：4939 列；`:Foreign` 4920（2006-09-29～2026-10-08）、`:Foreign_Investor` 19（2026-10-12～2026-11-09） | 一致 |
| V5 | 板塊外資 vs FinMind 外資 | §3.2 方法；37 日、36 同號、中位 55.42、最大 239.57、最新 −942.44 vs −900.56（差 −41.87） | **與 C1 報告一致**（55.4／239.6／−942.4／−900.6／−41.9） |
| V6 | 「只接 2 項真資料」文案 | `grep` 命中 `src/ui2/shell/app.py`（`_FEED_LABELS`）與 `tests/test_ui2_drawer_browser.py` | 一致（詳見五頁稽核 §7.3 D；只描述事實，未改文案） |
| V7 | 卡片新鮮度 | 讀 `compute_cache_staleness`／`STALE_DAYS_DAILY=7`；沙箱 today 2026-11-12 | 一致（age_days=3、is_stale=False） |
| V8 | 成交量猜單位（推論） | 讀 `leading_indicators.twse_volume` 備援迴圈；parquet 最近非 NaN volume＝4,239,400 | 迴圈為 FACT；偏差為 INFERENCE（詳五頁稽核 X-10） |
| V9 | 本文特有的補充重核 | 讀 L3：融資 5399.15741 億@2026-11-09；板塊 41／38／3、−920.24812237、`complete`；`metadata.json` per_day 算術 18026−15761＝2265；`reader._compute_staleness` 用 `tw_now().date()`；`margin_fact_service._taipei_today`；`compute_cache_staleness` 預設 `date.today()` | 與 C1 一致；**基準日不一致是本回合新增觀察**（調查者未明言） |

### 9.2 勘誤

1. **新增觀察（非勘誤）**：stale 判定的**基準日**也不一致（台北 vs 主機）。C1 原料只提閾值不一致（N-1）；本文補充基準日，併入 N-1。
2. **absent 計數**：`n_member_absent_cells=0`（ETF 家族成員）與 `n_absent_cells=53`（板塊×日空格）是不同的量（§2 末）。
3. **`:Foreign` 成分**：C1 原料有「依 docstring 至少 2017-12-18 起含外資自營商」的敘述，並已自標「未重抓驗證」；本文維持 NOT VERIFIED，未升級為 FACT。
4. **行號**：C1 原料引用的行號（如 `real_canonical.py:324-331`、`BACKLOG:2203`）在 3C 重整與後續變動後不可信，本文改用符號／ID。

### 9.3 限制（如實）

- 未連外網；Cloud／真機／Playwright 未驗；新區塊（尚不存在）無法量測。
- 全稱句查法：「融資／板塊 L3 0 production caller」＝`grep` 僅對靜態 `.py`，不含動態 import、文件、設定檔；「UI2 0 命中」＝對三目錄 grep；「Digest 不含資金籌碼欄」＝讀 `_market_section` 與 digest 模組（調查者另 grep `shared/decision_digest*.py` 全文，只命中 `isinstance` 與 `INDUSTRY_SUBJECT_TERMS`，本回合未重跑該 grep）。
- 「T86 `selectType=ALL` 含權證」「FinMind 外資 dataset 是否含上櫃」「TWSE BFI82U 僅上市」為領域知識／INFERENCE，repo 內無直接證據。
- 調查者讀了 DEC-164～173 相關段、線框、Mapping、READONLY_CONTRACT_AUDIT、PREGATE、EVIDENCE_SUPPLEMENT（§1、§4、§10 節選）；`EVIDENCE_SUPPLEMENT` §11–§12（授權矩陣）、`PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT`、`STAGE_F_GF1…` 未讀，其結論僅轉述 BACKLOG 摘要。
- 單組產出，未經第二組獨立複驗。

---

## 10. 建議下一批（最多 3 項；**皆為 RECOMMENDATION，非授權；不得自動跨越 Decision Gate**）

| # | 項目 | 需客戶裁示？ | 前置 Gate | 風險 | AI 總管推薦 |
|---|---|---|---|---|---|
| 1 | **非作者獨立 QA 本文與五頁稽核**：第二組重核 §9.1 的 V3／V4／V5 與 §3.3、§4 基準日觀察，並覆核 N-1～N-4 是否成立 | 否（內部 QA；§-2 規則 4） | 無 | 低；docs-only。不做的風險＝全稱句長期停在單組待驗 | **推薦先做** |
| 2 | **整理 DG-SCOPE／DG-COV／DG-PIT／DG-LIC 的商業語言決策單**（附 AI 推薦；PREGATE 研究的推薦為「先關 Gate、不動程式」，必要時最小面積只接融資一項），並以治理 PR 登記 N-1～N-4 | 是（決策單給客戶；登記由總管另案） | `I1144-WIRING-GATE` 不在此批解除，僅整理決策材料 | 低；不動 runtime。風險＝被讀成授權（本文各表已標 HOLD） | 推薦；在 #1 之後 |
| 3 | **（僅客戶先裁示後）外資口徑標籤 SSOT 與外資 L3 的設計草稿**：先解 `:Foreign` 斷點揭露方式、「外資」vs「三大法人合計」字樣分離，再談 L3 | 是（外資 L3 屬未授權另案；涉畫面字樣須先出文字線框） | 外資 L3 授權；DG-LIC／DG-PIT；`I1144-WIRING-GATE` | 中；易被讀成授權接線，且口徑斷點成分仍 NOT VERIFIED（需重抓驗證，新來源／新儲存須另授權） | 暫不推薦自動啟動；列為客戶可選項，**不跨越 Gate** |

> 本文為稽核證據。接線、新增 L3、改文案、改 UI 結構、改資料保存方式——**每一項都需客戶另行授權**。
