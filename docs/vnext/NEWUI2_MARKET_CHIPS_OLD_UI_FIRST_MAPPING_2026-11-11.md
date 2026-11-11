# New UI2 市場頁｜三大法人／融資／板塊資金流：Old-UI-First 唯讀盤點與接線設計（2026-11-11）

- **基準**：main `a6155dde`；量測日 2026-11-11。
- **授權**：Issue #1134（Old-UI-First 唯讀盤點與接線設計，客戶裁示轉錄，見 `docs/DECISIONS.md` DEC-162）。
- **驗證程度**：本文事實由**四位 agent 唯讀盤點**後彙整。**皆為 agent 產出，未經人工複驗，不是 QA PASS**。
- **證據級別**：`FACT`＝讀碼／讀檔直接確認；`INFERENCE`＝由事實推得，未實測；`NOT VERIFIED`＝未驗證或無法在沙箱驗。
- **引用規則**：只寫 `path::symbol`，不寫行號。量測值（列數、日期、金額）會漂移，以量測日為準。
- **非施工授權**：本文只做唯讀盤點與接線設計。§3 全部為**提案、未授權**。**不是**任何 UI2 接線、adapter、新來源、fetcher／cron／Secret、或投資語意（法人強弱、融資趨勢、資金流信號、分數、權重、排名）的授權。
- **與既有文件的關係**：承接 DEC-161 與 `docs/vnext/STAGE_F_GF1_HEADLESS_MARKET_CONTRACT_2026-11-11.md`（該文 §1 已列 inst／margin／sector_flow 的 headless 可讀性與缺口）。本文**不取代**它，補的是「舊 UI 呈現與耦合 → Legacy New UI → UI2 現況」的能力對照，以及接線提案。不能將可讀 parquet 直接視為已核准的 UI2 live 信號。

---

## §1 三項資料：Old UI → Legacy New UI → UI2 能力對照

### 1.1 三大法人（inst）

| 面向 | 內容 | 級別 |
|---|---|---|
| 舊 UI | `src/ui/tabs/macro/section_chips.py` §三籌碼：①外資大買／大賣超結論卡（單日 `cl_data['inst']`，單位億元；±100 億為 inline literal：≥100 綠、≤-100 紅、其間灰『觀望』；卡內有『積極加碼／嚴格減碼』建議行動文字）②外資／投信／自營商柱狀圖（外資藍、投信綠、自營金、負值紅；未觀測類別顯示『⬜ 未取得（非 0 億）』）③投信買超單日文字行（文字寫『連續買超是加碼訊號』，但只吃單日值）。個股層 `section_chips_20d`：20 日集中度／延續性％、吸籌／倒貨／發散、`inst_sanity` 爆量徽章 | FACT |
| Legacy New UI | `src/ui/views/page_market.py::inst_rows`／`_render_x8`：純事實原始表（名稱、淨買賣超億元、『本輪／上一次有效值；資料日』；未觀測寫『無資料（未觀測）』），無燈號、不排序。`page_find`／`_target_blocks` 的產業 Top5 依 `x_yi`（近 N 日法人累計淨流入）排序＝排序耦合 | FACT |
| UI2 現況 | `shared/ui2_contract`、`src/ui2`、`src/services/ui2`（含 `scenarios.py`）對 inst **0 命中**；FAKE 六場景無法人假資料。完全未呈現 | FACT |
| 資料來源與更新 | 即時：`fetch_institutional`→TWSE BFI82U（NAS Squid proxy，`ttl=TTL_30MIN`，`_parse_bfi82u_rows`，回 `InstNetDict`〔`shared/inst_net.py`，含 `unobserved_net`〕）。口徑 `shared/inst_labels.py`：外資＝外資及陸資，**不含**外資自營商。git 追蹤檔 `data_cache/finmind_inst.parquet`：4939 列、2006-09-29～2026-11-09，欄位 `date`／`foreign_buy`(億元)／`source`／`fetched_at`，**只有外資，無投信、無自營商**。`source` 4920 列為 `…:Foreign`（舊口徑，2017-12-18 前含外資自營商）、19 列為 `…:Foreign_Investor`。更新：`update_macro_history.yml` cron `0 9 * * *`（UTC）→`publish_data_pr` 開 `auto/data-macro-history` PR | FACT |
| canonical service | `macro_cache_reader`：`load_parquet_safe`、`read_cache_metadata`、`compute_cache_staleness('finmind_inst')`（登記 daily）；`load_extreme_risk_legs` 內 `_leg_series` 只輸出 `foreign_5d_yi`／`foreign_date`。**無『最新交易日外資億元＋as_of＋stale』專用函式**。三類（外資／投信／自營）只能來自 BFI82U 單日（`cl_data['inst']`，session 路徑，L1 取數），**不是 parquet** | FACT |
| as_of／stale／missing | parquet 路徑：`compute_cache_staleness`，`STALE_DAYS_DAILY=7` 日曆天；`metadata.datasets.finmind_inst` 無 `fetch_outcome` 欄（失敗訊息落地處 NOT VERIFIED）。今日 11-11、最新列 11-09，屬 7 日內，**INFERENCE：非 stale**。單日路徑：`InstNetDict.unobserved_net` 區分未觀測與 0 | FACT／INFERENCE |
| 公式與投資判讀耦合 | 同一資料餵 `foreign_net` 燈（`shared/lamp_direction_thresholds.py`）、總經紅綠燈、市場評估外資訊號；±100 億 inline literal；建議行動文字＝判讀語言。**本專案法人柱狀圖『正＝綠、負＝紅』，與台股紅漲綠跌相反** | FACT |
| 測試 | 檔名：`test_inst_sanity`、`test_inst_outlier_wiring_v19_135`、`test_batch_z33`(`_inst`)、`test_batch_z40`、`test_x2_dl_f1_s56_inst_missing_name`、`test_b2_consumer_consistency`、`test_macro_traffic_light_none_inst`、`test_lamp_foreign_net_wiring` | FACT（檔名）；內容未逐一讀、未執行＝NOT VERIFIED |
| NOT VERIFIED | TWSE BFI82U／FinMind 授權與再散布條款；2017-12-18 前後口徑斷點是否在任何下游被處理；`fetch_outcome` 落地處 | NOT VERIFIED |

### 1.2 融資餘額（margin）

| 面向 | 內容 | 級別 |
|---|---|---|
| 舊 UI | `margin_card`（`src/ui/render/macro_ui_components.py`）：大字『N 億』，>3400 紅『高危』、>2500 黃『警戒』、其餘綠『安全水位』，None→『⏳ 抓取中』。`section_chips` 三色結論＋建議行動（紅：全面減碼、去槓桿；綠：可積極布局；判定用 `>=`）。另 `section_warroom` 風險警示、`psy_checklist`『融資安全(<2500億)』、`daily_checklist`、`market_assessment_apply._append_margin_signals`、`shared/macro_buckets` `DangerSpec('margin', yellow=2500, red=3400)` | FACT |
| Legacy New UI | `tab_macro_v2` `ChartCard('margin')`：全史日序列（億），疊 SSOT 門檻線，四態。IA v2 `page_market::_render_x8`：原始值表『融資餘額（大盤）N 億』＋固定註記『融資燈門檻已失準；歷史單位混用區間屬資料疑義』（**寫死文字，不論資料是否乾淨皆顯示**）；本輪沒值沿用 `_last_margin` 標『上一次有效值』 | FACT |
| UI2 現況 | 三處目錄對 margin **0 命中**；FAKE 無融資假資料。完全未呈現 | FACT |
| 資料來源與更新 | `data_cache/finmind_margin.parquet`：4939 列，欄位 `date`／`margin_balance`(int64，**元**)／`source`／`fetched_at`，2006-09-29～2026-11-09；最新 539,915,741,000 元＝**5,399 億**；全史 900.7～6,533 億。`source` 字串 `FinMind:TaiwanStockTotalMarginPurchaseShortSale:MarginPurchaseMoney:TodayBalance`。即時 `fetch_margin_balance` 備援鏈（以碼為準）：FinMind→MI_MARGN〔TWSE〕→HiStock→Goodinfo→Yahoo→鉅亨，`TTL_30MIN`，回純 float、**無 as_of**。更新同 1.1（macro-history cron） | FACT |
| canonical service | **無融資專屬 L3 service**。圖用序列 `macro_cache_reader.load_v2_chart_series()`→`{'margin': Series(億)}`，其 `.attrs` 帶 `is_stale`／`stale_reason`／`as_of`／`age_days`／`upstream_error`。單值 `cl_data['margin']` 無 as_of | FACT |
| as_of／stale／missing | 序列路徑具備（見上）；單值路徑沒有。相鄰日期最大間隔 13 天、多在 2 月（春節，**推測**） | FACT／NOT VERIFIED（春節成因） |
| 單位混用與防線 | 成因（`shared/margin_schema.py` docstring）：舊 cron 取多 name 列（元／張／不明）去重，2006-07-17～2026-08-04 共 4929 列，約 40% 元、36% 張、25% 不明。已修在來源：`extract_margin_money_series` 只取 Money 列與當日餘額欄；`margin_money_to_yi` ÷1e8 並過 sanity [500, 10000] 億，不過回 None。現檔 0 列落 sanity 外。**8 月混用列是修掉或重建＝NOT VERIFIED** | FACT／NOT VERIFIED |
| **資料疑義旗標缺口** | 『資料疑義』目前**只是 UI 寫死文字，資料層無逐列旗標**。v3 §02 要求的強制標記**未在資料層落實** | FACT |
| 公式與投資判讀耦合 | 門檻已失準：`shared/relative_thresholds.py` 寫明 5,148 億已超兩線、燈永遠紅；最新 5,399 億。另有 `margin_leverage_ratio`（融資／總市值）。`MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI=3400.0`、`MARGIN_BALANCE_WARN_THRESHOLD_YI=2500.0`（`shared/signal_thresholds.py`）。紅黃綠與建議行動文字＝判讀語言，**UI2 不應沿用** | FACT |
| 測試 | 檔名：`tests/test_b3_margin_schema.py`、`test_h1_margin_label_and_registry.py`、`test_pr_n5_fetch_margin.py`（只讀名稱、未執行） | NOT VERIFIED（內容與結果） |
| UI2 若呈現必須沿用 | 只取 Money 列、÷1e8、sanity 過濾、失敗回 None | FACT（既有防線） |
| 其他 | 憲法 §2.1 寫『TWSE→HiStock→Wearn』，與碼不同，以碼為準（見 BACKLOG）。FinMind／TWSE 等授權與再散布條款 | NOT VERIFIED |

### 1.3 板塊資金流（sector_flow）

| 面向 | 內容 | 級別 |
|---|---|---|
| 舊 UI | `app.py` 第 4 tab『🌊 板塊資金潮汐』→`tab_sector_flow.py::render_tab_sector_flow`：Plotly 泡泡圖，X＝近 5 交易日累計淨流入(億)、Y＝動能(近 5 日均−前 5 日均，億/天)、大小＝近 20 日 abs(淨額)(億)。四象限：漲潮＝紅、輪動＝黃、退潮＝綠、觀望＝藍，附白話（『資金外移前兆』『觸底觀察』）＝判讀語言。持股板塊金框⭐。圖上無 Top-N。舊頁尾『快取更新於 {updated_at}』是 cron 時戳**非資料日**（舊版仍如此；修改須客戶核准並更新 z60 指紋） | FACT |
| Legacy New UI | `src/ui_v2/page_find.py` 的 `find.sector_flow` 與 `page_target`／`_target_blocks`（`F.load_sector_flow`、`build_sector_flow_card`＝TG-05 一帶）共用同一 service。產業 Top5 依 `x_yi` 排序＝排序耦合（見 1.1）。『與評分／行動無耦合』**NOT VERIFIED**（未逐檔讀 `page_target` 與 `build_sector_flow_card`） | FACT／NOT VERIFIED |
| UI2 現況 | 三處目錄對 sector_flow **0 命中**；FAKE 無板塊假資料。完全未呈現 | FACT |
| 資料來源與更新 | `data_cache/sector_flow/{daily_net.parquet, bubble_latest.json, metadata.json, ticker_sector.json, industry_raw.json}`。`daily_net` 欄位 `date`／`sector`／`net_amt_yi`／`foreign_yi`／`trust_yi`／`dealer_yi`／`n_stocks`／`twse_ok`／`tpex_ok`／`source`／`industry_ok`／`industry_scheme`／`fetched_at`，1716 列、2026-09-11～2026-11-09（37 日）。`metadata` 現值：`last_updated=2026-11-09`、`updated_at=2026-11-09T19:57Z`、`warnings=[]`、`last_error=null`、coverage `n_sectors=46`／`n_unclassified=0`／`n_excluded_foreign_ccy=4`（`n_dropped_missing_price=15761` 含義 NOT VERIFIED）、`bubble_window` 20 日、`tpex_complete=true`、`n_absent_cells=53`。producer：`scripts/update_sector_flow.py`＋`update_sector_flow.yml` cron `30 9 * * *`（UTC）→`publish_data_pr` 開 `auto/data-sector-flow` PR。上游：TWSE／TPEX 三大法人與收盤＋官方產業別（`t187ap03_L`／`mopsfin_t187ap03_O`）＋FinMind 產業補位，scheme `z43-official-code-v1` | FACT |
| canonical service | L1 `src/data/sector_flow/reader.py::read_sector_flow_cache(strict, today)`；L3 `src/services/sector_flow_service.py::get_sector_flow_view`，回 `ok`／`sectors[x_yi, y_yi, size_yi, quadrant, …]`／`is_stale`／`stale_reason`／`meta_updated_at`／`observation_date`／`tpex_complete`／`n_absent_cells`。**service 會混入持股高亮 `highlight_sectors`**，純事實層需用 reader 或剝離 | FACT |
| as_of／stale／missing | DEC-148 D1：`reader._compute_staleness` 只看 `metadata.last_updated` 距台北今日 >`SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS=4` 為 stale；缺／壞／未來⇒stale 且 `observation_date=None`，`updated_at` 不頂替。舊/Legacy 行為：stale 時 warning 但仍顯示快照（**不 fail-closed**）；`tpex_complete≠True`→灰字『目前僅含上市資料』；交易日 <10→『🕓 資料不足』 | FACT |
| 公式與投資判讀耦合 | 象限、白話、持股金框、Y 動能（均值差）＝判讀／個人化層；UI2 純事實卡不應含 | FACT |
| 測試 | 檔名：`test_d1_sector_flow_observation_date`、`test_sector_flow`、`test_sector_flow_stage2`（未執行） | NOT VERIFIED（內容與結果） |
| NOT VERIFIED | TWSE／TPEX／FinMind 授權與再散布；`n_dropped_missing_price` 含義；Open PR #1125（sector-flow 資料 PR）PIT 未獨立判定 | NOT VERIFIED |

---

## §2 UI2 現行契約與落點約束（FACT）

- **治理**：`PROJECT_RULES.md` 2026-11-08 Old UI First 五步驟；五頁、Dark-only、頂部兩列導覽（DEC-146）。
- **市場頁順序**（DEC-157）：首屏組＋今日主要風險→日 K 主圖／空槽→核心指標卡（TWII／VIX／US10Y／利差／DXY／PMI）→OneBrain→其餘。`MARKET_CARD_IDS` 固定 6 張（多或少即 raise）。
- **sections**：`onebrain`(L1)／`why`(L2)／`detail`『指標明細（16 項）』(L3)／`raw`(L3)＋`kbar`。`views/_page.py::render_sections` 預設**不渲染** L2／L3，只有 `SHOWN_FOLDS` 三項（`target.conditions`、`me.digest`、`me.registry`）會收合顯示。
- **現況**：三項資料在 `shared/ui2_contract`、`src/ui2`、`src/services/ui2`（含 `scenarios.py`）0 命中；FAKE 六場景無法人／融資／板塊假資料；Primary 空槽只在無 `kbar` 時出現，不適合承載。
- **守衛**：G2／G2F（`real_feed` 精確名稱白名單 `G2F_IMPORT_ALLOWLIST`，目前僅 `get_twii_trend_view`、`get_macro_regime` 與 `real_canonical` 名稱）／G4／G9；`ui2-browser` lane（Streamlit 1.56／1.59.2）。
- **手機餘裕**：390×844 `nav_margin_after_risk=168.8px`，門檻 160px，**餘裕僅 8.8px**（`viewport_measurements.json`）。插在風險與日 K 之間必破；放日 K 之後不影響此錨點，但仍須過 `content_not_covered_by_nav` 與 `market_stress_reachable`。
- **畫面結構門檻**：新增 section／卡片／欄位＝畫面結構改變，須先出**文字線框草稿**等客戶拍板（`CLAUDE.md` §-1.5 v3 §03-2①）。只放進 `detail`／`raw` 則畫面 0 變更。
- **回滾**：預設 FAKE，Real 由 `ui2_feed` 切換，`app.py` production 不引用；還原白名單與 feed 即可。

---

## §3 接線設計（proposed；全部為『提案、未授權』）

通用鏈：`git 追蹤 parquet／reader（唯讀，不呼叫 fetcher）` → `canonical L3 唯讀服務（proposed）` → `UI2 VM（proposed）` → `市場頁`。

輸出共通欄位（proposed）：`value`（億）、`as_of`、`is_stale`、`stale_reason`、`source`、`state ∈ {loaded, stale, missing, unavailable, partial}`。

| 項目 | proposed L3 檔／函式 | 輸入 | 沿用防線／限制 |
|---|---|---|---|
| margin | 新 L3（檔名待定）`get_margin_fact_view` | `macro_cache_reader.load_v2_chart_series()['margin']` 最新點與 `.attrs` | Money 列／÷1e8／sanity／失敗回 None；不引用 3400／2500 門檻與紅黃綠；不重算趨勢。『資料疑義』須由**資料層旗標**產生（現缺；不得寫死文字）→ 後續 Gate |
| inst（僅外資） | 新 L3 `get_inst_foreign_fact_view` | `data_cache/finmind_inst.parquet` 最新列＋`compute_cache_staleness('finmind_inst')` | 只外資；附口徑註記（`source` 欄：`…:Foreign` 含外資自營商〔2017-12-18 前〕、`…:Foreign_Investor` 不含）；**投信／自營商 parquet 無**，三類需 BFI82U 單日 session 路徑＝headless 不可 → 標缺口 |
| sector_flow | 新 L3 `get_sector_flow_fact_view`（或直接以 reader） | `read_sector_flow_cache` 取最新交易日 `net_amt_yi` Top／Bottom N＋coverage（`n_sectors`、`tpex_complete`、`n_absent_cells`） | 不含象限、動能 Y、白話、持股高亮（剝離 `highlight_sectors`）；stale 時於 UI2 **fail-closed 顯示 stale 狀態**，語意待客戶確認 |

**不重算投資訊號**：不新增強弱、趨勢、分數、排名；不介入私有持股／Risk Cap；session-free；no look-ahead（只取已落地的最新列）；no second pipeline（只讀既有 cron 產物）。

**涉及改動檔案清單（若日後授權；現不動）**：`src/services/ui2/real_feed.py`、`G2F_IMPORT_ALLOWLIST`（G2F 白名單）、`RealFeedSnapshot`、`real_canonical`、`market_vm`（或新 section 規格）、新 L3 service 檔、FAKE 對稱假資料（須帶 FAKE 標示）。測試：`real_canonical` 四態映射、margin 單位（÷1e8／sanity）、G2F teeth（白名單反向守衛）、`ui2-browser` 手機 390／桌機 1440 量測。

**回滾**：還原 G2F 白名單、`real_feed` 與新 service；Real 預設關閉（`ui2_feed` 切換），`app.py` production 不受影響。

**與既有四頁資料契約相依**：`MARKET_CARD_IDS` 固定 6 張不得改（新資料不得當第 7 張核心卡）；`SHOWN_FOLDS` 白名單若要顯示新 section 需擴；`detail`『指標明細（16 項）』數量若變動需同步契約與測試。

---

## §4 三方案比較

| 面向 | A1 僅文件映射＋誠實未提供 | A2 下一批另行授權：最小唯讀 L3 adapter＋UI2 純事實卡 | A3 擴大到法人／融資／產業趨勢訊號判讀與打分 |
|---|---|---|---|
| 正確性／風險 | 零 runtime 風險；無新可見值 | 低～中：單位（融資）、口徑（外資含／不含自營商）、stale 語意、手機 8.8px 餘裕 | 高：投資語意、PIT、資料授權；本批**不核准** |
| 速度 | 最快（已完成於本文） | 中（INFERENCE：2 步，含客戶拍板線框） | 慢 |
| Token／維護成本（INFERENCE） | 0 檔程式 | 估 5～8 個程式檔＋3～5 個測試檔、QA 2～3 輪 | 大量；含資料授權與 PIT 稽核 |
| 對 UI2 切換幫助 | 無新值，市場頁仍缺三項 | 補齊 Old-UI-First 缺口中最基本的純事實 | 超出切換所需 |

**AI 推薦（非客戶裁示）：A2，且分兩步。**

1. **步驟 1＝docs-only 文字線框草稿**：新 section 位置建議放在**日 K 與核心指標卡之後**，避免侵蝕 8.8px 餘裕；需客戶拍板。或選擇只進 `detail` 區（畫面 0 變更）。
2. **步驟 2＝授權後最小實作**。初版範圍建議：margin（億＋as_of＋stale）、sector_flow 最新交易日淨額 Top／Bottom N、inst 僅外資（parquet）。三類法人與融資『資料疑義』資料層旗標列為後續 Gate。

**A2 的前置**：客戶裁示（線框；是否納入 inst 僅外資；紅綠語意沿用或統一〔本專案法人柱正綠負紅，與台股紅漲綠跌相反〕；是否納融資）；各上游授權與再散布條款（NOT VERIFIED）。

---

## §5 殘餘 NOT VERIFIED 與缺口清單

1. 全部測試只讀檔名，**未執行、未讀內容**。
2. 各上游（TWSE／TPEX／FinMind／Yahoo／HiStock 等）授權與再散布條款。
3. 8 月融資混用列是修掉或重建；相鄰日期最大間隔 13 天（2 月）成因為推測。
4. `metadata.datasets.finmind_inst` 無 `fetch_outcome`，失敗訊息落地處未知。
5. 三類法人（外資／投信／自營）headless 缺口：parquet 僅外資。
6. 融資『資料疑義』資料層逐列旗標缺（目前僅 UI 寫死文字）。
7. 融資備援鏈與憲法 §2.1 不一致（以碼為準）。
8. `page_target`／`build_sector_flow_card` 與評分／行動『無耦合』未驗證；`n_dropped_missing_price=15761` 含義。
9. Open PR #1124～#1126 PIT 未獨立判定（#1126 PIT NOT VERIFIED）；#1119 HOLD。
10. Cloud UI2、真機、ui2-browser 實測皆未做（本批 docs-only）。
11. 本文所有事實為 agent 唯讀盤點，未經人工複驗。
