# New UI2｜🎯標的：Old UI First 接線稽核（單檔查詢／基本面候選池／產業資料）

> **研究候選，非授權、非投資判斷。**
> **研究候選，非施工授權。** 基準 main `e909152`（`git fetch origin main` 後以 worktree 讀碼）。延伸（不重複）`NEWUI2_MARKET_TARGET_OLD_FIRST_DATA_CONTRACT_AUDIT_2026-11-09.md` B2/B3/B4、`OLD_UI_FIRST_ADAPTATION_GATE_2026-11-08.md`。程式閱讀 ≠ 今日實測可用；未執行任何網路／runtime；不含投資判斷。

## 0. 先講結論（可驗證的關鍵事實）
- **Old UI 的組裝層住在 L5，UI2 不能 import**：`src/ui/views/_target_blocks.py::load_single`、`src/ui/views/page_find.py::load_screen_result/load_sector_flow`、`src/ui/views/page_inspect.py::classify_kind/load_stock_readout/load_chips/load_profitability/load_valuation` 皆在 `src/ui/**`；`tests/test_ui2_guards.py` G4 禁 `src.ui`/`app`。它們內部呼叫的 L3 才是可重用對象。
- **UI2 現行唯一合法 I/O 檔 = `src/services/ui2/real_feed.py`（G2F）**：精確白名單僅 `get_twii_trend_view`、`get_macro_regime`＋`real_canonical` 名稱；`import X`、`getattr`、`pandas`、`json`、`open`、`datetime`、`st`、`session_state` 與 `register_/apply_/set_/add_to_/save_/write_/...` 前綴全禁（`G2F_IMPORT_ALLOWLIST`、`_G2F_BANNED_NAMES/PREFIXES`）。**接任何標的 L3 必須改此白名單＋同步 mapping＋補負向測試＝需審查的守衛變更**，不是「純接線」。
- `src/ui2/**` 的 session key 限 `ui2_` 前綴（G9）；`src/services/ui2/**`（非 feed）走 G2 純度（禁 `src.data`/`src.compute`/`src.services.*`非 ui2/時鐘/open）。`tests/test_ui2_real_feed.py` 另有 runtime session 紀錄器＋socket guard＋檔案指紋（ALLOWED_UI2_WRITES 僅 5 個 `ui2_*` key）。
- UI2 現況（`real_canonical._target`）：候選 Top10／產業 Top5／lookup 全為 `_not_provided`；搜尋 CTA `disabled_reason="尚未開放查詢"`；`add_watch` 明示不寫入。無任何標的真資料。

## 1. Evidence Matrix
| 項目 | Old caller | L3 | L1 | source／as_of | freshness／PIT | fallback | 缺值處理 | side effects／寫入 | eligibility | UI2 狀態 |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 單檔：判型 | `page_inspect.classify_kind` | 無（直呼 L2 `compute.etf.asset_lag.classify_asset_kind/pick_benchmark`） | — | 代碼字串規則 | 無 | 使用者可覆寫 kind_choice | 空代碼→empty 卡；判型例外→紅態 | 無 I/O（L2 純函式） | 非個股/ETF→unknown 灰卡不硬判 | canonical-only（UI2 不能 import `src.compute`；需 L3/feed 包裝）NOT VERIFIED 是否已有 L3 公開判型 |
| A2 單檔：現價＋財報體檢＋KD | `page_inspect.load_stock_readout`→`_fetch_metrics` | `dividend_station_service.fetch_metrics(code,'stock',failed=)`→`_fetch_stock_metrics` | `data_loader.StockDataLoader.get_combined_data`、`financial_statements_fetcher.fetch_financial_statements`、`get_finmind_token` | 價：yfinance→FinMind→.TWO；財報：FinMind（T2）；`PriceAsOf.from_mapping` 帶價格 as_of | 財報約 45 天延遲，**公告日對齊 NOT VERIFIED**（L3 未見逐筆公告日） | 價失敗/財報失敗分別以 `FAILED_PRICE/FAILED_STATEMENTS` 回報，財報失敗時**不顯示分數/等第** | 缺→None；`mj_score_pct=None`→灰「查完沒有」；抓取失敗→紅，≠0 | **網路＋FinMind token/quota**；`@st.cache_data`（in-memory）；無 session/Sheet 寫入（grep 無命中） | 失敗 leg 不得被當 0／中性 | canonical-only |
| A3 單檔：籌碼／獲利／估值卡 | `load_chips/load_profitability/load_valuation` | `stock_chips_service.get_chips_readout`、`stock_grp_service.get_financial_statements(failed=)`＋`financial_health_engine.analyze_financial_health`、`valuation_service.get_stock_dividends` | 同上＋TWSE/TPEx | FinMind／T1 | 同上；`Data_Gap` 由 L3 判（`GAP_INCOME_STATEMENT`），UI 不重判 | 抓取失敗→紅且不帶「無此股財報」句 | 損益表整張缺≠0 | 網路＋token；無寫入 | 三格只吃損益表 | canonical-only |
| B1 候選：基本面初篩 | `page_find._load_survivors` | `fundamental_screener_service.get_fundamental_prescreen/get_fundamental_survivors/get_survivor_ids(refresh=False)` | `fundamentals_snapshot_loader.load_fundamentals_snapshot`（讀 `data_cache/fundamentals/{sii,otc}_{roc}Q{s}.parquet`＋`latest.json`）＋L2 `run_fundamental_prescreen` | MOPS 全市場季快照（cron `update_fundamentals.yml`）；as_of＝`meta.roc_year/season`；`updated_at`＝抓取時（非資料日） | 無逐檔公告日；TTL_1DAY；**L3 無快照過期旗標**（`latest_published_quarter` 僅 `shared/staleness`、`forward_test` 引用）→ 過期判定 NOT VERIFIED | 快照缺→`FileNotFoundError`（strict 加 `snapshot_missing`）；去年同季缺→三率三升判 False | NaN 比較→False（不 fillna）；金融業因無營收自然被排除 | **純本地讀檔**；`refresh=True` 才清 cache；無網路／session／寫入 | 4 項 AND：負債比<0.5、三率 YoY 同時嚴格升、淨流動值>0、EPS>0（`DEBT_RATIO_MAX/EPS_MIN/PRESCREEN_REQUIRED_PASSES`） | **可 as-is 唯讀重用**（僅 B1 需 feed 白名單擴充）；canonical-only |
| B2 候選：排名 | `page_find.load_screen_result` | `get_ranked_picks(factors,…,auto_fetch=False,regime=)`→`composite_rank_candidates(drop_unscored=True)`→`_apply_bear_market_filter` | 輸入組裝需 pe_map（`valuation_service.get_pe_name_maps`→TWSE `BWIBBU_d`/TPEX OpenAPI）、`run_shortage_scan`、`run_rs_leader_scan`、`build_trend_map` | 因子：eps_high=存活池**單季 EPS**；trend=跨季快照；pe/shortage/rs 需網路 | 綜合分為「有資料因子」百分位平均，需有資料因子數 > 0.5×有效因子數（`SCREENER_MIN_FACTOR_COVERAGE_RATIO=0.5`） | 因子輸入失敗→該因子不計分，勾選因子失敗→UI 轉紅「選股中止」 | 缺因子＝None 空白**不是 0**；`drop_unscored` 排除未評分；note 揭露「因子實際覆蓋 N/M」 | **`auto_fetch=True`（預設）會觸發缺貨/RS 掃描＝網路＋FinMind quota**；cron/MCP 用；UI2 若呼叫須固定 `auto_fetch=False` 且自行不傳 shortage/rs；regime 為 bear/caution 才套空頭濾網（`THROTTLE_VETO_REGIMES`），無 RS 資料時 note 須寫「未套用」 | 排名規則（因子公式、0.5 涵蓋門檻、drop_unscored、空頭濾網）**不得改**；僅 `eps_high`/`trend` 兩因子可無網路 | preview-slot（候選卡 Preview） |
| B3 候選：缺貨 | `page_find._load_shortage` | `shortage_screener_service.run_shortage_scan(refresh=False,max_scan=50)` | `fetch_batch_monthly_revenue`/`fetch_monthly_revenue`（FinMind＋OpenAPI 備援）、`fetch_quarterly_shortage_frame`、存活池 | FinMind T2；`meta.fetched_at/source/pool_source` | 月營收契約 DEC-151/152：`BATCH_SOURCE_MONTH_KEY_VERIFIED=False`→批次路徑公告時點資格 NOT VERIFIED、全市場 STRONG 不恢復；OpenAPI 僅最新月快照不可當歷史 | 兩候選池皆取不到→空＋note；L1 確定失敗不入快取（`_CandidatePoolFetchFailed/_DeepScanFetchFailed`） | **n_ok**（`有效訊號數`/`_n_signals_ok`、`資料資格`、`缺值原因`）；n_ok=0→`TIER_INSUFFICIENT` 不入榜（`_RANKABLE_TIERS` 不含）；n_ok 1~3 且弱→「（部分證據 n/4，非確定）」；月份鍵未驗證→④月營收項上限 5 分 | **網路＋FinMind token**；掃描上限 50 檔；cache 1 天 | 0 分≠缺值；`缺貨：無評估資料`字樣（`SHORTAGE_NO_ROW_TEXT`）；G1 顯示欄不進排序 | canonical-only／不建議 UI2 直接觸發 |
| C1 產業：板塊資金潮汐 | `page_find.load_sector_flow`（`get_sector_flow_view`）／`_target_blocks.map_bundle` | `sector_flow_service.get_sector_flow_view(strict=True)` | `src/data/sector_flow/reader.read_sector_flow_cache`（讀 `data_cache/sector_flow/{bubble_latest,metadata,ticker_sector}.json`） | cron `update_sector_flow.yml`；as_of＝`observation_date`＝`metadata.last_updated`（嚴格 YYYY-MM-DD）；`updated_at`/`meta_updated_at`＝cron 執行時（**不可當資料日**） | D1/DEC-148：觀測日缺/不可解析/晚於今日/與 updated_at 矛盾→`is_stale=True`；距今>4 日曆日（`SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS`）過期 | 無 bubble→`ok=False`（灰「尚未產生」，非紅）；strict 下壞檔→raise | 板塊 `unavailable`/`n_absent_cells`（缺席不補 0）；`tpex_complete is not True`→須標「僅含上市」 | **不傳 stock_sheet_id、`use_active_selection=False`、`etf_tickers=None`＝純本地讀檔**（`_collect_stock_watchlist_tickers(None)` 回 []）；`use_active_selection=True` 會走 `holdings_service.get_holdings`（Sheet 讀）→UI2 禁用 | 無 highlight ≠ 無持股（未讀 Sheet 時 `highlight_sectors` 恆空，不得顯示「無持股」）；未知代號→「未分類」不 highlight | canonical-only；**可 as-is 唯讀（固定三個預設參數）** |
| C2 產業對映 | `_target_blocks._load_screen_bundle` | `target_industry_service.get_ticker_sector_map()` | 同 reader（strict） | `ticker_sector.json` | 同上 | `available=False`＝對映檔缺（≠查無此股） | 對不到不放 key，顯示 ⬜ | 純本地讀 | — | canonical-only |
| D 加入觀察 | `_target_blocks`/`app` | `watchlist_service.add_picks_to_watchlist(name,tickers)`、`get_watchlist_add_context` | `gsheet_portfolio._get_active_stock_sheet_id/list_stock_watchlists/add_to_stock_watchlist` | Google Sheet（T5） | — | 無 sheet→raise | — | **Google Sheet 讀＋寫**（讀取 `get_watchlist_add_context` 亦 Sheet 讀） | — | **STOP**（UI2 target 明文禁寫；G2F 禁 `add_to_`/`set_`；`get_holdings`/`get_sheet_*` 亦在禁名單） |

## 2. 可否 as-is 唯讀重用（UI2 觀點）
- **可（本地讀檔、無網路／session／寫入；仍需 feed 白名單擴充）**：`get_fundamental_prescreen/survivors/survivor_ids(refresh=False)`、`describe_snapshot_coverage(meta)`（純函式）、`build_trend_map(refresh=False,strict=True)`、`get_ranked_picks(['eps_high'] 或 ['trend'], survivors_df=…, auto_fetch=False)`、`get_sector_flow_view(strict=True)` 預設參數、`get_ticker_sector_map()`。
- **不可／不宜**：`fetch_metrics`、`get_financial_statements`、`get_chips_readout`、`run_shortage_scan`、`run_rs_leader_scan`、`get_pe_name_maps`（皆網路＋FinMind quota/proxy，非 UI2 current 的「無網路」承諾）；`get_ranked_picks(auto_fetch=True)`；`refresh=True`（清共用 cache＝影響其他 session）；`get_sector_flow_view(use_active_selection=True | stock_sheet_id=…)`；`add_picks_to_watchlist`/`get_watchlist_add_context`。
- **L3 不可 as-is 的原因**：Old UI 將「因子輸入組裝／失敗分類／文案」放在 L5（`page_find.load_screen_result`），L3 `get_ranked_picks` 只負責排名；若 UI2 自行組裝＝新寫一套錯誤語意（違反 Old UI First §2 與 §4 B）。

## 3. 資料資格／排名規則（不可更動）
- 候選必須是「存活池」：4 項皆過；缺值判 False（不 fillna）。顯示須帶 as_of＝`民國{roc_year}Q{season}`，`updated_at` 僅標「抓取於」；`possibly_incomplete`（涵蓋率 < 去年同季×0.9，`SNAPSHOT_COVERAGE_WARN_RATIO`）須揭露。
- 綜合分欄：缺因子顯示「資料未取得」（空白，≠0）；`drop_unscored` 排除者不得列入；因子覆蓋 N/M 須顯示；未滿 >50% 因子涵蓋者不進榜。
- 缺貨（若日後顯示）：n_ok=0＝「無法評估（資料不足，不是 0 分）」；n_ok 1~3＝「部分有效證據 n/4」＋缺值原因，弱/中不得寫成確定；`月份鍵未驗證`須帶註記；「缺貨：無評估資料」≠ 低分。
- 產業：觀測日未知/過期須明示「資料日未提供/已過期」，不得用 `updated_at` 頂替；`ok=False` 灰；`unavailable` 板塊不畫；`tpex_complete is not True`標僅含上市。
- 單檔：財報腿失敗＝紅/資料未取得，**不得顯示分數**；查無財報（真沒有）≠ 抓取失敗；價格 as_of 取 `PriceAsOf`。ETF 與個股走不同 L3 契約（ETF fail-loud、個股 best-effort），不得抹平。
- 搜尋結果「可顯示」：僅 canonical 判型為 stock/etf 者；unknown 只顯示灰卡「無法判定」；不得出現買賣點、目標價、加入持股（Risk Cap／strategy 非本頁）。

## 4. 方案比較
| 方案 | 內容 | 正確性／風險 | 速度 | Token | 備註 |
|---|---|---|---|---|---|
| A 重用 canonical L3 | feed 白名單擴充，直呼 B1/C1/C2 L3；單檔不接 | 最高（同源）；風險＝改 G2F 守衛需審查＋新增 snapshot 過期旗標缺口 | 快 | 低 | 候選池 `eps_high`/`trend` 與產業可覆蓋 |
| B 薄唯讀 adapter（`src/services/ui2/`） | 新 L3 組裝 `load_single`/因子輸入＋失敗分類，回純資料給 VM | 中；須與 Old UI 語意等價測試（紅/灰/部分覆蓋）；adapter 在 `src/services/ui2/` 之外才能 import `src.data`，而 G2 禁，故仍須置於 feed 白名單或新增具名 L3 檔＋守衛登記 | 中 | 中高 | 單檔查詢必走此（網路＋token＋多腿失敗語意） |
| C 新來源／重構 | 新 fetcher、改排名/估值/PIT | 最高風險；需 Decision Gate | 慢 | 高 | 未授權，不做 |

**推薦**：候選池與產業用 **A**（先唯讀、本地檔、無網路）；單檔查詢待客戶 Gate 後採 **B**（需網路＋FinMind token，須獨立 G2F 擴充與負向測試）；B3 缺貨維持 canonical-only。理由：A 無新計算；B 的成本集中在失敗語意搬遷。

## 5. 下一步 UI 設計輸入
1. 候選卡狀態：已評分／資料未取得／無法判定／部分涵蓋（N/M）／快照過期（可能不完整）；as_of 欄＝季別（非 cron 時間）。
2. 產業卡：觀測日、stale 理由、僅含上市、`unavailable` 板塊數；highlight 未讀 Sheet 時顯示「未讀取持股」。
3. 查一檔 CTA 啟用前提：載入按鈕 gate（cold 零取數）、結果存 `ui2_` key、失敗不重打（冷卻）、不寫 Sheet。
4. 需客戶 Gate：新增欄位／排序角度／是否顯示單季 EPS 排名（`eps_high` 為單季非 TTM，須標註）。

## 6. NOT VERIFIED
- 今日各來源（FinMind quota、TWSE/TPEx、MOPS、cron）實際可用／資料新鮮度；本稽核未連網、未跑測試。
- 基本面快照在 L3 的過期旗標（是否有人以 `latest_published_quarter` 判）；逐檔公告日對齊（季財報 45 天延遲僅文件記載，未見 per-stock 公告日欄）。
- `classify_asset_kind` 是否已有 L3 公開包裝；`stock_chips_service`/`valuation_service.get_stock_dividends` 內部網路與寫入（僅 grep session_state/to_parquet/write_text 無命中，未逐行讀）。
- `rs_leader_service.run_rs_leader_scan`、`fetch_pe_name_maps` 的快取/退避細節。
- `@st.cache_data` 在 UI2 test harness（socket guard/檔案指紋）下是否與現行測試相容。
- `src/services/ui2/*` 以外任何已存在但未讀的 target preview 場景（`scenarios.py`）內容。

---

## 2026-11-09 QA 補正（附註；原研究內容不改）

> 本節為 append-only 附註；上文任何一行均未改動，原證據保留。不升格任何項目為 approved。以下均已對 origin/main 原碼 grep 核對。

1. **B1 `get_fundamental_survivors` 的 strict 語意**：上文 B1 列寫 `(refresh=False)`。舊 UI `page_find._load_survivors`（`src/ui/views/page_find.py` 約 L1013–1037）實際呼叫 `get_fundamental_survivors(strict=True)`。`src/services/fundamental_screener_service.py` 原碼：
   - `strict=True` 且存活池為空（`surv` 為 None／empty／無 `stock_id` 欄）→ `raise RuntimeError(<排名器 note 原文>)`，帶屬性 `empty_survivor_pool = True`；
   - 季快照讀不到（L1 `FileNotFoundError`）→ strict 下在原例外上加 `snapshot_missing = True` 後原樣往上拋（非 strict 不加屬性）；
   - 預設 `strict=False` 時空池回空表（舊註釋明言這會被畫成「選股完成、0 檔」）。
   → UI2 **不得**把 0 檔存活畫成有效結果而不分辨成因。UI 至少須區分原碼已存在的三態：(i) 空池錯誤（`empty_survivor_pool`；常見成因去年同季快照缺，重按不會變）、(ii) 快照缺（`snapshot_missing`）、(iii) 非 strict 下確實取得的空表／0 檔（僅在成因已查明為有效零時才可呈現為「0 檔」）。舊頁以「檔數 `None`（取不到）≠ 0 檔」區分。本補正不新增任何行為，也未規定 UI2 的具體字樣。
2. **兩個 `classify_asset_kind` 語意不同**（皆已驗證）：
   - L2 `src/compute/etf/asset_lag.py::classify_asset_kind`（上文 A1 所指）回 `'etf'|'stock'|'unknown'`：`00` 開頭→etf；首字為數字→stock；其餘（含空碼、`^TWII`、美股）→`unknown`，不硬判。
   - L0 `shared/dividend_station_thresholds.py::classify_asset_kind` 只有 etf／stock 兩值，**沒有 unknown**：`00` 開頭→ETF；4 碼純數字→個股；4 碼＋單一字母（特別股如 2881A）→個股；**其餘（含美股 BND/VOO 等非台股代號）一律預設 ETF**。
   → 兩者對同一代號可得不同結果（例：美股代號如 `VOO` 或空碼，L2＝`unknown`／無基準，L0＝ETF；L2 先經 `bare_etf_code` 正規化，其細節本次未逐行驗證，NOT VERIFIED）。UI2 **不得互換**使用，亦不得以其一的結果餵給另一者預期的三態分支。
3. **`latest_published_quarter` 的使用者**：除上文列的 `shared/staleness` 與 `forward_test` 外，`scripts/update_fundamentals_snapshot.py`（cron；`from shared.staleness import latest_published_quarter`，約 L163 呼叫）亦使用。補充：`src/compute/screener/forward_test.py` 僅在註解中提及，非實際呼叫；實際定義於 `shared/staleness.py`（約 L689）。結論「L3 無快照過期旗標」經 grep（非 tests 的 `*.py`）仍成立：`src/services` 下無引用。
