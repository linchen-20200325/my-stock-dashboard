# UI2 市場頁「市場資金與籌碼」runtime 接線前置 Gate 研究（Issue #1144 B 線；docs-only）— 2026-11-11

> **性質**：唯讀研究。**不是接線授權**（`I1144-WIRING-GATE` 仍未授權，DEC-164 G-9／DEC-165）。未修改任何 src／tests／real_feed／VM／views／allowlist；未提新來源／API／排程；不含外資 L3。
> **基準**：worktree 基底 `8ae1536`（#1145 後）；量測日 **2026-11-11**（台北今日，`today=2026-11-11` 注入）。單組撰寫，**未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。
> **標籤**：**FACT**＝本回合讀檔／實測；**INFERENCE**＝由 FACT 推得；**RECOMMENDATION**＝AI 推薦（**非裁示**）；**NOT VERIFIED**＝未驗，不得當前提。
> **符號引用**：以檔案路徑＋符號為準，不寫行號（`CLAUDE.md` §8.2.A.0 規則 1）。

---

## 0. 結論先行

| # | 結論 | 標籤 |
|---|---|---|
| 1 | 資料層（融資、板塊）**已能唯讀產出事實**，實測重現 #1142：板塊 universe 41／觀測 38／未觀測 3，融資 5399.15741 億 @ 2026-11-09，皆 `OK` 且非 stale | FACT |
| 2 | 板塊 `completeness='complete'` **只代表來源旗標完整，不代表全覆蓋**；L3 不設最低覆蓋率門檻；門檻值屬業務語意，**未裁示，本文不自設** | FACT／Decision Gate |
| 3 | PIT：parquet **無 `release_date` 欄**；只有 `fetched_at`（抓取時點）與資料日。來源發布日／可得日 **NOT VERIFIED**，不以 commit time 代替 | FACT／NOT VERIFIED |
| 4 | TWSE／TPEX／FinMind 的使用與再散布條款：本沙箱連不到官方站（`www.twse.com.tw`、`finmind.github.io` 解析失敗），**全部 NOT VERIFIED**；不得推論已授權 | NOT VERIFIED |
| 5 | 接線需動 5 個層面（real_feed、`G2F_IMPORT_ALLOWLIST`、`real_canonical`／`RealFeedSnapshot`、market VM section、`views/market.py`／FAKE 對稱），且**至少 4 個客戶 Gate（G-F2～G-F6 中與本線有關者、coverage 門檻、授權／PIT）未關閉** | FACT／INFERENCE |
| 6 | AI 推薦：**方案 B「先關 Gate、不動程式」**為預設；若客戶要求立即前進，採方案 A（只接融資一項，最小面積）。**RECOMMENDATION，非裁示** | RECOMMENDATION |

---

## 1. Coverage／Partial

### 1.1 實測（2026-11-11；`get_sector_flow_fact(today=2026-11-11)`、`get_margin_fact(today=2026-11-11)`）

| 項目 | 實測值 | 來源（路徑＋符號） | 標籤 |
|---|---|---|---|
| 板塊 state／reason／資料日／stale／completeness | `OK`／`ok`／2026-11-09／False／`complete` | `src/services/sector_flow_fact_service.py::get_sector_flow_fact` | FACT |
| universe／觀測／未觀測 | **41／38／3**（與 #1142 量測一致） | `SectorFlowCoverage` | FACT |
| 未觀測板塊 | 化學生技醫療、未分類、電子工業 | `coverage.unobserved_sectors` | FACT |
| 衍生聚合 | 合計 −920.24812237 億；正 11／負 27／持平 0；`reconciled=True`；`n_observed=38` | `SectorFlowDerived` | FACT |
| caveats | `foreign_ccy_etf_excluded_last_cron_run_scope`、`sectors_unobserved_on_data_date`、`absent_cells_in_window`、`scope_includes_etf_etn_and_receipt_labels` | `SectorFlowFact.caveats` | FACT |
| 視窗診斷 | `tpex_complete_window=True`、`tpex_ok_on_data_date=True`、`n_absent_cells_window=53`、`n_excluded_foreign_ccy=4`、`n_unclassified_stock_days=0`、`cron_coverage_n_days=1` | `SectorFlowCoverage` | FACT |
| 融資 | `OK`、5399.15741 億元、as_of 2026-11-09、`is_stale=False`、`age_days=2`、sanity 區間 (500, 10000) | `src/services/margin_fact_service.py::get_margin_fact` | FACT |

**`daily_net.parquet` 原始統計（FACT，pandas 直讀）**：1716 列、37 個交易日（2026-09-11～2026-11-09）、全日 `twse_ok／tpex_ok／industry_ok` 皆 True、無 NaN；每日原始板塊標籤 45～47 個（最新日 46，標準化後 38 個有列）（**補註：原始標籤 46 → 標準化後 38 的映射過程未查證（NOT VERIFIED）**）；整檔不同標籤 49；`industry_scheme` 僅 `z43-official-code-v1`。`metadata.json`：`coverage.n_sectors=46`、`n_dropped_missing_price=15761`、`n_stock_days_with_net=18026`。

**3 個未觀測標籤在歷史中的出現（FACT）**：化學生技醫療僅 1 日（2026-10-20）、未分類 12 日（2026-09-14～2026-10-16）、電子工業 2 日（2026-10-27～10-30）。**成因 NOT VERIFIED**（`I1140-SECTOR-UNOBS-LABELS`）；`n_dropped_missing_price=15761` 的含義 **NOT VERIFIED**（`I1140-SECTOR-DROPPED-PRICE`）。

**融資資料品質（FACT）**：`finmind_margin.parquet` 4939 列、日期單調遞增且唯一、無 NaN、無 ≤0；近 60 筆落在 5340～6533 億，無觸及 sanity 邊界；近 60 筆最大日距 5 天（假日）。欄位僅 `date／margin_balance（元）／source／fetched_at`，**無 `release_date`**。歷史內部單位混用僅驗最新點（`I1140-MARGIN-UNIT-MIX`，FACT，已登記）。

### 1.2 必要完整性與缺值規則（現行 L3 已落實者＝FACT；缺口＝待裁示）

| 規則 | 現況 | 標籤 |
|---|---|---|
| 缺值不得充 0 | 板塊最新日無列＝`sign="unobserved"`、`net_yi=None`，不計入合計與正／負／持平；NaN／inf → 整份 `UNAVAILABLE`；重複列不靜默相加；`SectorNetRow.__post_init__` 強制 `net_yi=None ⇔ unobserved` | FACT |
| 融資缺值 | 缺／壞／sanity 不過／as_of 不符／未來日 → 無值（`MISSING`／`UNAVAILABLE`），**只有 OK／STALE 可帶 `value_yi`** | FACT |
| 衍生聚合只對「完整且對帳通過」者計算 | partial／unknown → `derived=None`（rows 照給）；計數恆等式 `正+負+持平=n_observed`、`n_observed+n_unobserved=n_universe` 於建構時強制 | FACT |
| 不得稱全市場 | 板塊 L3 無任何「全市場」欄位；但 `MARGIN_SOURCE_TEXT` 含「全市場融資金額」描述性字樣（`I1140-MARGIN-SOURCE-TEXT`） | FACT |
| ETF 家族成員缺席 | 承襲 L2 Z43；部分成員缺席時 L3 **未揭露**（`I1140-ETF-FAMILY-ABSENT`）。合計含 ETF／ETN／受益憑證類標籤（caveat `scope_includes_...`） | FACT |
| 視窗診斷計數範圍 | `n_excluded_foreign_ccy`／`n_unclassified_stock_days`／`cron_coverage_n_days` 是**上次 cron 範圍**，非綁定資料日、非整個視窗（`I1140-SECTOR-CRON-SCOPE`） | FACT |

### 1.3 衍生聚合的合法顯示條件（依 DEC-164 G-3 方案 A；條件為客戶已裁示，非本文新訂）

全部同時成立才可顯示合計與計數：(1) `completeness == complete` 且 `derived` 非 None 且 `reconciled`；(2) 資料日外露、`is_stale` 如實傳遞；(3) 明示「衍生聚合」（非來源直接提供）；(4) 同時揭露 `n_observed／n_universe／n_unobserved`，**不得稱全市場、不得給誤導性合計**；(5) 不排序、不做 Top／Bottom；(6) 口徑文字依 G-10（三大法人合計，與「大盤外資淨買賣超（僅外資）」不可比）。**(7) 最低覆蓋率門檻——見 Decision Gate DG-COV。**

### 1.4 Decision Gate DG-COV（最低 coverage 門檻；`I1140-COVERAGE-MIN`）

**未裁示；本文不提百分比。** 只列選項與影響（皆為業務語意，需客戶用商業語言回答）：

| 選項 | 內容 | 影響（INFERENCE） |
|---|---|---|
| C0 | 不設門檻，只如實顯示 38／41 與未觀測清單 | 今日可顯示；風險＝「合計」被讀成全市場訊號，需文案強揭露 |
| C1 | 設「未觀測板塊數／比例」上限，超過則隱藏合計、只留逐列 | 需客戶給數值；今日 3/41 是否過線取決於該值；邊界（恰等於門檻）需一併裁示 |
| C2 | 設「特定板塊必須有列」（例如指定核心板塊）才顯示合計 | 需客戶指定名單；牽涉板塊分類語意 |
| C3 | 永不顯示合計（只顯示逐列與計數） | 最保守；偏離 G-3 方案 A 已裁示的衍生聚合 |

---

## 2. PIT／資料日期

| 面向 | 融資（`finmind_margin.parquet`） | 板塊（`sector_flow/daily_net.parquet`） | 標籤 |
|---|---|---|---|
| 觀測日（資料歸屬日） | `date` 欄 | `date` 欄；L1 另以 `metadata.last_updated` 判新鮮度（`reader._compute_staleness`） | FACT |
| 抓取時點 | `fetched_at`（逐列；最新列 2026-11-09T19:40:31Z） | `fetched_at`（逐列，同日同值；最新 2026-11-09T19:57:52Z）；`metadata.updated_at` | FACT |
| **來源發布日／可得日** | **無 `release_date` 欄 → NOT VERIFIED** | **無 `release_date` 欄 → NOT VERIFIED** | FACT／NOT VERIFIED |
| 以 commit time 代替？ | **禁止**（DEC-165）。git 紀錄僅顯示檔案最近一次 commit 為 `4432d5a` 2026-11-10 08:46 +0800，**這是 cron 提交時間，不是來源發布時間** | 同左 | FACT |
| 假日／缺日 | 日期只含交易日；假日無列（近 60 筆最大間隔 5 天）。L3 以 `age_days` 與 L1 `is_stale` 判定，未獨立驗證交易日曆 | `n_absent_cells=53`（視窗交易日軸缺席格）；2026-09-25～09-28、10-09～10-11、10-23～10-26 等區間無列（假日或缺抓 **NOT VERIFIED**，未對照 TWSE 休市表） | FACT／NOT VERIFIED |
| stale | L1 `is_stale`；L3 缺／非布林 → `STALE freshness_undetermined`；`True` → `STALE stale` | 觀測日距今 >4 日曆天（`SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS`，值以 `shared` 常數為準，本文未另行確認）→ stale | FACT |
| partial | n/a | `completeness`＝`partial`（旗標未全真或 TPEx 視窗不完整）→ 不給 `derived` | FACT |
| 未來日期 | 最新日 > 台北今日 → `MISSING future_as_of`（fail closed） | 觀測日晚於今日或晚於 `updated_at` 台北日 → 視為 stale 且觀測日不外露；L3 `date_disagreement` 等 | FACT |
| 同日資料可得性 | 2026-11-09 資料於同日 19:40Z（＝台北 11-10 03:40）抓到 | 同日 19:57Z（台北 11-10 03:57） | FACT；「盤後多久可得」由 cron 時間推得，**非來源官方發布時刻** → NOT VERIFIED |

**INFERENCE**：現有證據只能支持「資料日＋抓取時點」兩個時間戳；若客戶要求 PIT（可得日）語意，必須先有來源發布日證據，現無。DEC-164 已將卡片層與日 K 未來日行為不對稱登記為 `I1140-FUTURE-ASOF-ASYM`，板塊／融資 L3 均 fail closed，無不對稱。

**Decision Gate DG-PIT**：在無 `release_date` 下，是否接受以「資料日＋抓取時點（明示非發布時點）」作為 UI 揭露的時間語意？（需客戶裁示；本文不代為接受。）

---

## 3. 上游授權與再散布（TWSE／TPEX／FinMind）

| 上游 | 本專案用途（FACT，讀檔） | 官方原文取得？ | 結論 |
|---|---|---|---|
| TWSE（T86／MI_INDEX 等） | 板塊事實的三大法人張數、收盤價（`daily_net.parquet.source`：`TWSE:T86+MI_INDEX`） | 嘗試 WebFetch `https://www.twse.com.tw/zh/page/about/website/terms.html`：**主機無法解析**（沙箱網路白名單外） | **NOT VERIFIED** |
| TPEX（insti／dailyTrade、afterTrading） | 同上（`TPEX:insti/dailyTrade+afterTrading/otc`） | 未能取得官方原文（同一網路限制；未另試其他 TPEX 網址） | **NOT VERIFIED** |
| FinMind（`TaiwanStockTotalMarginPurchaseShortSale`、`TaiwanStockTotalInstitutionalInvestors`） | 融資餘額與大盤外資（`finmind_margin.parquet`／`finmind_inst.parquet` 的 `source` 欄） | 嘗試 WebFetch `https://finmind.github.io/`：**主機無法解析** | **NOT VERIFIED** |

- **FACT**：repo 內 `docs/` 至少 `PROJECT_STATE`／`DECISIONS`／`SUPERSESSION_AUDIT` 三檔寫「授權／再散布 NOT VERIFIED」；本回合未窮舉其他檔，也未取得官方條款原文。
- **INFERENCE（反向，禁止誤用）**：檔案可讀、API 可呼叫、已在 repo 內 git 追蹤，**皆不構成授權依據**。
- 若要關閉此項：需在可連外環境逐一取得官方使用條款原文（URL＋引用段落）並由客戶裁示可否在 Streamlit Cloud 對外呈現與衍生聚合。**Decision Gate DG-LIC**（客戶／法務層，非技術拍板）。

---

## 4. 缺口盤點

### 4.1 G-F2～G-F6（皆**待客戶裁示**；出處 `docs/vnext/STAGE_F_HEADLESS_INPUT_AND_STALE_SEMANTICS_2026-11-11.md` 的 Gate 表、DEC-160／161）

| ID | 內容 | 與本線（市場資金與籌碼）的關係 | 狀態 | 需誰裁示 |
|---|---|---|---|---|
| G-F2 | headless 持股授權（Digest 可否消費私有持股） | **無直接關係**（本區塊不含持股）；INFERENCE：不阻塞本線 | 待裁示 | 客戶 |
| G-F3 | A2 stale 取向（A2-i／A2-ii） | 間接：定義 stale 值能否進入 Digest 段；本區塊為顯示層，不進 Digest。INFERENCE：不阻塞 | 待裁示 | 客戶 |
| G-F4 | Digest v2 schema／compat／PIT Gate | 與本區塊無直接關係；但其「PIT 設計」若將來要求 `release_date`，會回頭影響 §2 | 待裁示 | 客戶 |
| G-F5 | production caller 建立時機 | 本區塊接線＝UI2 feed 新讀取，**不是** Digest caller；INFERENCE：不阻塞，但 DEC-164 §四（「未核准 UI2 feed／section 接線」處，即其 G-9 授權範圍）已明定「UI2 feed／section 接線」本身須新 Gate | 待裁示 | 客戶 |
| G-F6 | 登入前置（`NUI2-AUTH-CONTRACT-GATE`） | 本區塊為公開市場資料，無需登入；INFERENCE：不阻塞 | 待裁示 | 客戶 |

> 以上「關係／阻塞」欄為 **INFERENCE**（撰寫組讀 Gate 表所得），是否真不阻塞須客戶或獨立 QA 確認。**G-F1 方案 A 已於 DEC-161 核准**，非本表範圍。

### 4.2 `I1140-*` 殘餘缺口（逐項；依 `docs/BACKLOG.md`『Issue #1140』段）

| ID | 與接線的關係 | 狀態／阻塞 | 需誰裁示 |
|---|---|---|---|
| I1140-COVERAGE-MIN | **阻塞接線**（DG-COV） | 未裁示 | 客戶 |
| I1140-ETF-FAMILY-ABSENT | 接線 Gate 重審（揭露文案） | 未處理 | 總管提案＋客戶（若涉文案） |
| I1140-SECTOR-CRON-SCOPE | 接線時文案不得把「上次 cron 範圍」寫成整窗 | 未處理 | 總管 |
| I1140-MARGIN-SOURCE-TEXT | 「全市場融資」字樣與 G-3 不得誤稱全市場的精神需對齊（G-3 針對板塊聚合；融資是 FinMind 加總序列，是否可稱全市場屬事實查證 **NOT VERIFIED**） | 未處理 | 總管＋客戶（文案） |
| I1140-MARGIN-UNIT-MIX | 若取歷史序列／趨勢才觸發；僅顯示最新點不阻塞 | 未處理 | 總管 |
| I1140-MARGIN-NAT | 僅有 caller 傳 NaT 才觸發；feed 不傳 today，不阻塞 | 未觸發 | — |
| I1140-SECTOR-UNOBS-LABELS／-DROPPED-PRICE | 成因 NOT VERIFIED；影響 DG-COV 的判讀 | 未查證 | 總管（獨立一組查證） |
| I1140-PRICE-WORDING／FUTURE-ASOF-ASYM／TODAY-TZ／OHLC-GUARD／AI-FUTURE-ASOF／NAN-MID-WINDOW／C12-PATH-NOT-EXHAUSTIVE／MACRO-STATE-NONCANON／REGIME-SET-EQ／MACRO-BARREL-ST／DIGEST-HEALTH-RANGE／DIGEST-A2-IMPL | 屬 TWII／Digest／macro 路徑，與融資＋板塊區塊**無直接依賴**（INFERENCE） | 各自觸發條件未成立 | — |

### 4.3 G2F allowlist、FAKE／Real 對稱（只盤點，**不改**）

| 項目 | 現況（FACT，讀 `tests/test_ui2_guards.py`、`src/services/ui2/real_feed.py`、`tests/test_ui2_real_feed.py`） | 接線時需要的變更（INFERENCE） |
|---|---|---|
| `G2F_IMPORT_ALLOWLIST`（`tests/test_ui2_guards.py`） | feed 只准 import `market_twii_view_service.get_twii_trend_view`、`allocation_service.get_macro_regime`、`real_canonical` 的具名集合 | 需新增 `margin_fact_service`／`sector_flow_fact_service` 的具名 import；`_G2F_BANNED_NAMES` 含 `datetime／pandas／time`，feed 不得自帶時鐘（兩個 L3 的 `today=None` 內部取台北今日，可行） |
| `real_feed.read_real_snapshot` | 目前讀 3 個事實：台股卡片、位階、日 K；`app.py` shell 文字稱「只接 2 項真資料」 | 新增兩個 `_read_*`；各事實互相隔離（失敗不拖垮他者） |
| `RealFeedSnapshot` | 欄位：`twii／regime／kbar` 與各自 `*_error` | 需新增欄位與 `of()` 簽名；錯誤代碼需符合 `ERROR_CODE_RE` |
| `WIRED_PATHS`（`tests/test_ui2_real_feed.py`）與 `_all_fields`／`_paths` | 守衛「已接線欄位」清單與遍歷 | 新欄位須納入，否則守衛紅燈（反向守衛，即設計意圖） |
| FAKE 軸 | FAKE 六場景**無**對應資金資料（`NEWUI2_MARKET_CAPITAL_FLOW_TEXT_WIREFRAME` §A，FACT） | 須補帶 **FAKE 標示**且結構與 Real 對稱的占位 |
| `real_canonical`（純函式映射） | 目前映射 TWII／regime／kbar 的四態 | 需新增融資／板塊的 `FieldState`→VM 映射；G-5 規定僅 sanity 判未過才附「資料檢查未通過」 |

### 4.4 版面與固定項

| 項目 | 現況 | 標籤 |
|---|---|---|
| OneBrain 下方 section | 客戶指定（G-1）；現行渲染順序：標題→L1→日 K→`render_cards`（6 張）→OneBrain→`render_sections(skip={onebrain})`。新區塊放 OneBrain 之後，須確認 `skip` 不致重複渲染 | FACT（讀 wireframe §A）／INFERENCE（渲染細節） |
| 六張核心卡固定 | `src/services/ui2/market_vm.py::MARKET_CARD_IDS = twii, vix, us10y, spread, dxy, pmi`；`build_market_page_vm` 數量或順序不符即 `raise ValueError` | FACT |
| `SHOWN_FOLDS` 不變 | `src/ui2/views/_page.py::SHOWN_FOLDS`＝{`p4_target/conditions`、`p4_me/digest`、`p4_me/registry`}；G-2 不折疊→不改 | FACT |
| 五頁頂部導航 | `shared/ui2_contract/pages.py`：`P4_HOLD／P4_ME／P4_MARKET／P4_TARGET`＋`P4_DATA` 共 5 頁；`src/ui2/shell/app.py` 以 `st.radio(..., horizontal=True)` 呈現導覽。本線不改導覽 | FACT |
| 視窗量測 | `docs/vnext/newui2_realfeed/viewport_measurements.json`（既有；手機 `scroll_end_bottom=763.8` ≤791，見 wireframe §A 轉述）為**舊量測**；新區塊會推高 `scroll_end_bottom`，**未重測** | FACT（舊值）／NOT VERIFIED（新區塊後） |

### 4.5 未測環境（一律 NOT VERIFIED）

| 環境 | 狀態 |
|---|---|
| 390×844 首屏／捲動（含新區塊） | **NOT VERIFIED**（新區塊不存在於 UI；舊量測不適用） |
| 1440×900 首屏／捲動 | **NOT VERIFIED** |
| Streamlit Cloud 實際渲染 | **NOT VERIFIED** |
| iOS／Android 真機 | **NOT VERIFIED** |
| Playwright／瀏覽器 viewport 自動化 | **NOT VERIFIED**（本回合未執行） |
| `role="group"`＋`aria-label`（G-8）無障礙測試 | **NOT VERIFIED**（實作階段才可驗） |

---

## 5. 最小候選施工方案與三方案比較（**RECOMMENDATION，非裁示**；前提＝客戶先關閉 §6 Gate 並另行授權接線）

### 5.1 最小候選施工（若日後授權；現不動）

1. `src/services/ui2/real_feed.py`：新增 `_read_margin`／`_read_sector`（各自 try／except 隔離，只留例外型別名代碼）。
2. `G2F_IMPORT_ALLOWLIST` 新增兩個具名 import；`real_canonical` 新增事實 dataclass 與四態映射、`RealFeedSnapshot` 欄位。
3. market VM 新增 L1 SectionVM（**不動 `MARKET_CARD_IDS`**）；`views/market.py` 於 OneBrain 之後渲染。
4. FAKE 對稱占位（帶 FAKE 標示）；`WIRED_PATHS`／`_paths` 納入新欄位。
5. 測試：四態映射、融資單位／sanity、板塊 coverage／stale／partial、衍生聚合揭露、G2F teeth、FAKE／Real 對稱、390／1440 量測。

### 5.2 三方案比較

| 方案 | 內容 | 風險 | 速度 | Token | 前置 Gate |
|---|---|---|---|---|---|
| **A 只接融資（單一事實）** | 只做融資一項（最小面積：一個 `_read_*`、一個 VM field、一組守衛） | 低～中：融資單位歷史混用僅驗最新點；FinMind 授權 NOT VERIFIED | 快（約為 C 的 1/3，INFERENCE） | 低 | DG-LIC、DG-PIT；不需 DG-COV |
| **B 先關 Gate，不動程式（AI 推薦）** | 本文件交客戶；客戶裁示 DG-COV／DG-PIT／DG-LIC 與是否採 A 或 C；再另開接線 Gate | 最低（零程式變更） | 最慢（等裁示） | 最低 | 即本文 §6 |
| **C 融資＋板塊一次接** | 依 wireframe §F 全套 | 中～高：衍生聚合顯示條件、ETF 家族揭露、3 未觀測板塊解讀、較多測試面與版面高度未測 | 慢 | 高 | DG-COV、DG-PIT、DG-LIC 皆須先裁示 |

> 速度與 Token 比較為 INFERENCE（依需動檔案數與測試面推估，非實測）。

**AI 推薦（RECOMMENDATION，非裁示）**：預設 **方案 B**——目前三個 Gate（DG-COV、DG-PIT、DG-LIC）皆非技術問題、皆未裁示，貿然寫程式會把「尚未被允許顯示的東西」做成可顯示的東西；若客戶當下裁示 DG-PIT 與 DG-LIC 可接受，再以 **方案 A** 分批（融資先、板塊後），避免一次 C 觸碰 DG-COV。

---

## 6. 待客戶裁示的 Decision Gate 彙整

| Gate | 問題（商業語言） | 選項 | AI 推薦（非裁示） |
|---|---|---|---|
| DG-COV | 板塊資料沒涵蓋全部板塊時，還要不要顯示「合計」？涵蓋多少以下就隱藏？ | C0／C1（需客戶給數值）／C2／C3，見 §1.4 | C0＋強揭露（38／41 與未觀測清單）作為起點；數值門檻由客戶定 |
| DG-PIT | 沒有「來源發布時間」，只顯示「資料日＋我們抓到的時間」可以嗎？ | 接受（明示非發布時點）／不接受（先補來源證據） | 接受並明示；但屬客戶語意 |
| DG-LIC | TWSE／TPEX／FinMind 資料在 Cloud 上呈現與加總，是否需先取得官方條款確認？ | 先確認／風險自負先行 | 先確認（本沙箱無法取得官方原文） |
| DG-SCOPE | 先接融資一項（方案 A）還是兩項一起（C）？ | A／B／C | B→A |
| WIRING-GATE | 是否正式授權 UI2 runtime 接線（含 allowlist 變更） | 授權／暫不 | 暫不，待上述裁示 |

---

## 7. 限制與未驗

- 本文件單組撰寫，未經第二組複驗；實測數字（41／38／3、融資值）可重現，但以 `today=2026-11-11` 注入，之後資料日會變動（`CLAUDE.md` §8.2.A.0 規則 4）。
- 為跑 L3 服務，本回合在沙箱以 pip 安裝 pyarrow 與 requirements 依賴；**未改任何 repo 檔**（僅新增本文件）。
- 上游授權、PIT 發布日、Cloud／真機／Playwright／390／1440 新區塊量測，**全部 NOT VERIFIED**。
- 假日與缺日（如 2026-09-25～28、10-09～11、10-23～26）僅依資料推得，未比對休市表。
- 「G-F2～G-F6 不阻塞本線」為撰寫組推論，需客戶或獨立 QA 確認。
- 本文件的推薦不是裁示；沉默不等於同意。
