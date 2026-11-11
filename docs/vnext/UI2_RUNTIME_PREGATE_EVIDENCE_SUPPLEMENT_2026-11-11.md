# UI2「市場資金與籌碼」runtime 前置 Gate 證據補強（方案 B；docs-only）— 2026-11-11

> **性質**：補強 `docs/vnext/UI2_RUNTIME_PREGATE_RESEARCH_2026-11-11.md`（以下稱「既有研究」），**不另起架構、不取代**；既有研究原文不改。**不是接線授權**。
> **客戶裁示（2026-11-11 對話原文）**：「同意 B」＝方案 B：UI2「市場資金與籌碼」**先完成唯讀證據補強，不進行正式 UI runtime 接線**。範圍＝Coverage／板塊／ETF 家族、PIT、TWSE／TPEX／FinMind 授權、G-F2～G-F6 與接線 Gate 阻塞、研究文件＋三方案比較＋SSOT 只追加。**不授權**任何程式、投資規則、資料來源、UI runtime、Schema 修改。
> **基準**：main `d601b5f`；量測日 2026-11-11（`today=2026-11-11`）；資料日 2026-11-09。符號引用＝檔案＋符號，不寫行號（`CLAUDE.md` §8.2.A.0 規則 1）。
> **來源與複驗程度**：本文由三份單組研究員證據（Coverage／PIT／授權；未入 repo）彙整。**撰寫組已對其關鍵數字與引用做抽查（見 §8），但仍是單組，未經第二組獨立複驗**（§-2 規則 6）；其「全稱結論」只能當待驗事項。
> **標籤**：VERIFIED FACT（本回合實跑／讀檔／抽查）／INFERENCE／NOT VERIFIED／RECOMMENDATION（非裁示）。
> **固定原則**：Missing≠0；`fetched_at`≠`release_date`；git commit time 不得冒充發布時間；標籤數不是個股覆蓋率；板塊三大法人合計≠大盤外資淨額。

---

## 0. 結論先行

| # | 結論 | 標籤 |
|---|---|---|
| 1 | **本回合未關閉任何一個客戶 Gate。** DG-COV／DG-PIT／DG-LIC／DG-SCOPE／WIRING-GATE 全部維持「待客戶裁示」；證據補強只讓選項更清楚、讓 NOT VERIFIED 的邊界更精確 | 事實 |
| 2 | 「41 板塊」是**近 20 交易日窗口內出現過的標準化標籤聯集**，不是官方產業分類總數；未觀測 3 個（化學生技醫療、電子工業、未分類）是**單檔偶發標籤**，最新日無列；窗口 53 個缺席格**全部且僅**來自此 3 板塊。故 38／41 偏向反映標籤噪音，不是 3 個大類板塊缺資料 | VERIFIED（數字）／INFERENCE（噪音解讀） |
| 3 | **現有資料算不出個股覆蓋率**（`daily_net.parquet` 無個股代碼；診斷計數僅留最近一次 cron）。因此任何「覆蓋率 %」門檻目前**沒有可計算的分子分母**；本文不提任何百分比 | VERIFIED |
| 4 | `n_dropped_missing_price=15761` 是**最近一次 cron（1 個交易日）**的有法人列但無有效收盤股日數，非累計、非視窗；**不代表遺失 15761 檔股票**；其證券組成 NOT VERIFIED | VERIFIED（範圍）／NOT VERIFIED（組成） |
| 5 | PIT：三資料集都只有「資料日」與「系統抓取時間」；**官方發布時點、第三方上架時點、修訂版本皆無證據**；`fetched_at` 對近期逐日列只是「可得日上界」，對 99.5% 的融資列（bootstrap 批）無意義 | VERIFIED（欄位）／NOT VERIFIED（發布日） |
| 6 | 授權：TWSE／TPEX **全部 NOT VERIFIED**；FinMind 僅取得 GitHub README 三句原文（範圍有限，非官網條款全文）；OGDL 僅為搜尋摘要線索，**不是原文** | NOT VERIFIED（含部分） |
| 7 | G-F2～G-F6 的 Gate 表內容全部屬 Digest／headless 範圍；**無任何已讀文件把它們列為市場資金與籌碼區塊的前提**（此為 INFERENCE，仍須客戶確認）。真正直接阻塞的是 DG-COV／PIT／LIC／SCOPE＋WIRING-GATE | INFERENCE |
| 8 | 三方案比較結論與既有研究一致：方案 B（本案已核准）→ 客戶裁示後才可能有 A／C；A、C **僅為未來候選，不是施工授權** | RECOMMENDATION |

---

## 1. VERIFIED FACT

### 1.1 Coverage／板塊（`data_cache/sector_flow/`；撰寫組抽查實跑）

| 項目 | 值 | 說明 |
|---|---|---|
| `daily_net.parquet` | 1716 列、37 交易日（2026-09-11～11-09）、**49 個原始標籤**、`industry_scheme` 僅 `z43-official-code-v1` | 抽查重現 |
| 最新日（11-09） | 46 原始標籤列、Σ`n_stocks`＝**2265**、合計 **−920.248 億**、外資分項 −942.438 億 | 抽查重現 |
| 母體／觀測／未觀測 | **41／38／3**；`bubble_latest.json` 的 `sectors`＝41、`n_absent_cells`＝53、`window_size`＝20、`tpex_complete`＝True | 母體＝窗口內任一天出現過的標準化標籤（程式路徑：`scripts/update_sector_flow.py::_write_bubble_json`＋`SECTOR_CANONICAL_ALIASES`） |
| 3 個未觀測板塊在 37 日內的出現 | 化學生技醫療 **1 日**（10-20）；電子工業 **2 日**（10-27、10-30）；未分類 **12 日**（09-14 起至 10-16） | 抽查重現；窗口缺席格 19＋18＋16＝53 |
| 標準化不丟列 | 只重新分組；重複 (date,標籤) 會 raise；合併後金額以 `_isclose` 對帳，不過則 `UNAVAILABLE` | 讀程式（`canonicalize_sector_daily`、`sector_flow_fact_service`） |
| 計數恆等式 | 正＋負＋持平＝已觀測（11＋27＋0＝38）；已觀測＋未觀測＝母體（38＋3＝41）；於建構時強制 | 前研究與本研究一致 |
| `completeness` 語意 | `complete`＝最新日 `twse_ok／tpex_ok／industry_ok` 皆 True **且**視窗 `tpex_complete is True`；與「全覆蓋」無關；缺席類診斷只揭露、不阻擋 | 讀 `_compute` |
| ETF 家族（最新日） | `ETF`＋`上櫃ETF` 合併板塊 **353 檔、−254.286 億**；ETF／ETN／受益證券／存託憑證**全部納入合計**（caveat `scope_includes_etf_etn_and_receipt_labels`） | 抽查重現 |
| `n_member_absent_cells` | 視窗內 0（8 組別名合併成員皆完整）；故「ETF 家族成員缺席」**目前資料不存在**，但 L3 對此情形仍**未揭露**（`I1140-ETF-FAMILY-ABSENT` 為潛在風險） | 讀程式＋metadata |
| 15761 的算式 | 法人列 17119＋911＝18030；−外幣 ETF 排除 4＝`n_stock_days_with_net` 18026；−缺價 15761＝**2265**＝最新日 Σ`n_stocks` | 抽查 metadata 與 parquet 一致；`coverage.n_days`＝**1** |
| 外幣 ETF 排除規則 | `shared/sector_flow_thresholds.py::is_foreign_ccy_code`：`00` 開頭、長度>5、第六碼∈{K,C,M,S}；僅最近一次 cron 計 4 | 讀程式 |
| 板塊合計 vs 大盤外資 | 板塊三大法人合計 −920.2 億；板塊外資分項 −942.4 億；`finmind_inst` 外資 **−900.56 億**；外資分項與大盤差約 **−41.9 億**。數值接近但**口徑不同**（個股張數×收盤價彙總 vs FinMind 彙總金額），**不可並列、加減**（G-10） | 抽查；原研究員寫「−41.8」，本文以實算 −41.87 修為約 −41.9 |
| 選列規則 | `industry_raw.json` 共 3174 碼：`official_match_finmind` 1977、`finmind_no_official` 1188、`official_name` 9 | 抽查重現 |

### 1.2 融資（`data_cache/finmind_margin.parquet`）

| 項目 | 值 |
|---|---|
| 形狀／欄位 | 4939×4：`date／margin_balance（元）／source／fetched_at`；**無 `release_date`** |
| 最新值 | 2026-11-09、539915741000 元＝**5399.157 億**；近 60 筆落在 5340.5～6533.3 億，未觸 sanity 邊界 (500, 10000) |
| 缺日 | 2026-09-11～11-09 的 42 個平日中缺 5 日：09-25、09-28、10-09、10-23、10-26；與板塊缺日**逐日相同** |

### 1.3 PIT 欄位與時點

| 項目 | 事實 |
|---|---|
| 三資料集（融資、`finmind_inst`、板塊）時間類欄位 | 只有資料日 `date` 與抓取時間 `fetched_at`；**無** observation_date／release_date／available_at／updated_at 欄（metadata 有整檔 `updated_at`／`last_updated`） |
| bootstrap 批 | 融資 4939 列中 **4912 列**（99.5%）的 `fetched_at` 皆為 `2026-09-24T13:25:11`，對可得日**無意義**；只有最新約 27 列為逐日抓取時點（抽查 4912 重現） |
| 補抓例 | 融資 2026-11-05 資料列的 `fetched_at`＝`2026-11-06T14:09:34`，與 11-06 同批（即 11-05 當日 cron 未入列，隔日補入）；原因 NOT VERIFIED |
| 最新列抓取時點 | 融資 11-09：2026-11-09T19:40:31Z（＝台北 11-10 03:40） |
| cron | `update_macro_history.yml`：`0 9 * * *` UTC（台北 17:00）；`update_sector_flow.yml`：`30 9 * * *` UTC（台北 17:30）。實際抓取時間落在 UTC 13:25～19:57，與排程差數小時，**成因 NOT VERIFIED** |
| git 時間 | 融資 parquet 最近 commit `4432d5a7`，2026-11-10T08:46:18+08:00＝**資料 PR 合併時間**，晚於抓取約 5 小時；repo 為 shallow clone。**不得充發布時間** |
| 覆蓋規則 | 融資 `_merge_dedupe keep="last"`（新值覆蓋舊值，不留版本）；融資增量 `start=last+1`（已存日不重抓）；板塊「本次寫入日先刪舊列」。程式**不保存修訂版本** |
| stale 規則 | 板塊：`SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS`＝**4** 日曆日；融資：`STALE_DAYS_DAILY`＝**7** 日曆日；兩者皆不看交易日曆 |

### 1.4 授權（僅 FinMind README，經 `raw.githubusercontent.com` 取得，逐字）

| 原文 | 出處 |
|---|---|
| 「本專案提供的所有內容均用於教育、非商業用途。資料僅供參考，使用者依本資料交易發生交易損失需自行負責……」 | FinMind 官方 GitHub README |
| 「使用者須遵守臺灣證券交易所『交易資訊使用管理辦法』等交易資訊管理相關規定。」 | 同上 |
| 英文：Broker branch data「for your own use only under every plan… must not be retransmitted or provided to third parties in any form.」（**僅限券商分點資料**；本專案所用兩資料集非分點資料） | 同上 |

> **範圍有限聲明**：以上只是 README 三點，**不是**官網「免責聲明與資料授權」頁（`finmind.github.io/Disclaimer`）、也不是服務條款全文，未涵蓋各資料集授權、付費方案、Cloud 公開展示與衍生聚合。**不得**從中推出「已獲授權」或「已被禁止」。

### 1.5 接線面（只讀核對，**不改**）

| 項目 | 現況 |
|---|---|
| `G2F_IMPORT_ALLOWLIST`（`tests/test_ui2_guards.py`） | 僅准 `market_twii_view_service.get_twii_trend_view`、`allocation_service.get_macro_regime`、`real_canonical` 具名集合；無 `margin_fact_service`／`sector_flow_fact_service` |
| `real_feed`／`RealFeedSnapshot`／`real_canonical` | 現讀 TWII、regime、日 K 三類事實；`RealFeedSnapshot` 在 `real_canonical.py`；守衛 `WIRED_PATHS` 在 `tests/test_ui2_real_feed.py` |
| Market VM | `src/services/ui2/market_vm.py::MARKET_CARD_IDS` 六張（twii、vix、us10y、spread、dxy、pmi），數量或順序不符即 `ValueError` |
| 版面 | `src/ui2/views/market.py` 已含 `ONEBRAIN_SECTION_ID="onebrain"` 的 L1 渲染；`render_sections(skip={"onebrain"})` 仍被呼叫；`SHOWN_FOLDS` 不變（G-2） |
| 視窗量測 | `docs/vnext/newui2_realfeed/viewport_measurements.json` 為**舊量測**（2026-11-10，git sha `1f3c489`），不含新區塊 |

---

## 2. INFERENCE

| # | 推論 | 依據 | 若錯的風險 |
|---|---|---|---|
| I-1 | 3 個未觀測板塊是 FinMind 單源分類標籤的偶發採用（噪音），不是缺價／缺抓 | `industry_raw` 中兩者的成員碼為 `finmind_no_official`；FinMind 對同碼回多筆互相矛盾分類（抽查：2330 同回「半導體業」「電子工業」）；視窗內 TPEx 皆 ok | 若實為真實資料缺漏，DG-COV 的判讀要重做 |
| I-2 | 「38／41」比例會隨偶發標籤浮動，以比例為門檻會被噪音主導 | 母體定義＝窗口內任一天出現即入 | 門檻選項 C1 的實用性降低 |
| I-3 | 15761 主要是法人檔（T86 `ALL`）涵蓋遠多於「每日收盤行情」表的證券（疑為權證等） | 17119 vs 1381 的量級差 | 列級組成未落地，可能含應納入普通股 |
| I-4 | 三資料集缺日完全一致，較可能是休市而非缺抓 | 缺日逐日相同 | **證據強度弱於研究員原述**：融資與外資同為 FinMind、同一 cron，不是獨立路徑；僅「FinMind」與「TWSE／TPEX 板塊」兩條路徑一致；且無休市表比對 |
| I-5 | 連假（例如 09-24→09-29）下板塊 4 日門檻可能誤判 stale；融資 7 日、板塊 4 日不一致，同一今日可能一個 stale、一個非 stale | 規則不看交易日曆 | 畫面出現互相矛盾的新鮮度提示 |
| I-6 | 「資料日≤今日」不證明「當時已公布」；L3 無「盤後是否已可得」判斷 | 讀 L3 規則 | PIT 語意被讀成比實際更強 |
| I-7 | 若 parquet 公開於 GitHub 或 Cloud 且被視為「再散布」，FinMind「非商業」與 TWSE 規範可能構成風險；若 TWSE／TPEX openapi 掛 data.gov.tw 並採 OGDL-Taiwan-1.0，依搜尋摘要允許重製、散布、改作、需顯名 | 僅 README 三句＋搜尋摘要 | **線索不是原文**；是否涵蓋 rwd 網頁 JSON 未知 |
| I-8 | G-F2～G-F6 不阻塞市場資金與籌碼區塊 | Gate 表內容皆為 Digest／headless（持股授權、A2 stale、v2 schema、production caller、登入）；本區塊為公開市場資料、顯示層、不進 Digest | 若客戶另有語意（例如要求區塊先過登入），須回頭重列 |
| I-9 | 排除 ETF 後板塊合計約 −666 億（ETF 約占合計 27.6%） | 由 `rows` 算術 | 僅算術，不構成業務結論；ETF 標籤依 FinMind label，與交易所分類是否一致 NOT VERIFIED |
| I-10 | 若接線，最小面積方案 A 速度較快、Token 較低 | 依需動檔案數推估 | 非實測 |

---

## 3. NOT VERIFIED

| # | 項目 | 說明 |
|---|---|---|
| N-1 | **TWSE 使用條款、openapi 授權、交易資訊轉載限制** | 官方站在沙箱不可連（解析失敗／代理 403）；**全 NOT VERIFIED** |
| N-2 | **TPEX 版權與 openapi／data.gov.tw 授權** | 同上；網頁 JSON 與 openapi 授權是否一致亦未知 |
| N-3 | FinMind 官網免責聲明、各資料集授權、付費方案、Cloud 公開展示與衍生聚合 | 只有 README 三點，範圍有限（見 §1.4） |
| N-4 | **OGDL-Taiwan-1.0** | 僅 WebSearch 二手線索，**不得當原文**；是否適用本專案取數 NOT VERIFIED |
| N-5 | 官方發布日／時點、FinMind 上架延遲、事後修訂與未定稿風險 | repo 內「14:30／17:00／17:30」為經驗值，非官方引文，**不得作 release 時點** |
| N-6 | 缺日是否為休市（含 09-25、09-28、10-09、10-23、10-26） | repo 有 `twse_holiday_fetcher.py` 但**無落地休市表**，且該模組自陳不含臨時休市、未以真實回應比對 |
| N-7 | 3 偶發板塊「哪一檔、哪天」產生列、為何消失 | `daily_net` 不存個股代碼 |
| N-8 | 15761 缺價列的證券組成；2384（有收盤代碼）與 2265（進板塊）差 119 筆原因 | 列級資料未落地 |
| N-9 | 外幣 ETF 排除規則（第六碼 K／C／M／S）是否涵蓋全部；被排除 4 檔身分；歷史排除量 | 不可得 |
| N-10 | 興櫃是否含於法人來源；ETF／ETN 標籤與交易所清單一致性 | 無法分辨 |
| N-11 | 板塊合計 vs 大盤外資差額的來源端成因；TWSE BFI82U 官方金額未對帳 | 來源端定義未驗 |
| N-12 | cron 早退或失敗時 `metadata.coverage` 與 `data_date` 脫鉤的實際發生情形 | 僅讀程式，未模擬 |
| N-13 | 融資是否可稱「全市場」；`MARGIN_SOURCE_TEXT` 字樣需對齊 | `I1140-MARGIN-SOURCE-TEXT` |
| N-14 | 歷史融資單位混用（元／百萬元／億）僅驗最新點 | `I1140-MARGIN-UNIT-MIX` |
| N-15 | 390×844／1440×900 新區塊首屏與捲動；Streamlit Cloud；iOS／Android 真機；Playwright；`role="group"`＋`aria-label`（G-8）無障礙測試 | 新區塊不存在；舊量測不適用 |
| N-16 | 本文及三份證據全文的第二組獨立複驗 | 未做 |

---

## 4. RESIDUAL BLOCKERS

> 依「直接阻塞／間接依賴／其他專案 Gate」分組。**Digest／OneBrain 的 Gate 不是市場頁前提**，已歸入第三組。「是否阻塞」欄凡屬推論一律標 INFERENCE。

### 4.1 直接阻塞 UI2「市場資金與籌碼」

| ID | 內容 | 阻塞性質 | 狀態／裁示者 |
|---|---|---|---|
| **DG-COV**（`I1140-COVERAGE-MIN`） | 板塊最低 coverage 門檻（是否顯示合計、涵蓋多少以下隱藏） | 業務語意；**未裁示，本文不自設百分比** | 客戶 |
| **DG-PIT** | 無 `release_date` 下，是否接受以「資料日＋系統抓取時間（明示非發布時點）」作為時間揭露 | 業務語意＋證據不足 | 客戶 |
| **DG-LIC** | TWSE／TPEX／FinMind 資料於 Cloud 呈現與衍生聚合的授權確認 | 客戶／法務；技術無法代決 | 客戶／法務 |
| **DG-SCOPE** | 日後若進入接線，先融資一項（A）、或融資＋板塊（C） | 範圍＝資源與優先序（§8.4 step 4，須附推薦） | 客戶 |
| **WIRING-GATE**（`I1144-WIRING-GATE`） | 是否正式授權 UI2 runtime 接線（feed／section／allowlist 變更） | DEC-164 G-9 明確「未核准」 | 客戶；**維持未授權** |
| `I1140-MARGIN-SOURCE-TEXT` | 文案「全市場融資」字樣與「不得稱全市場」精神對齊 | 接線前必處理的文案 | 總管＋客戶（文案） |
| `I1140-ETF-FAMILY-ABSENT` | 家族成員缺席時 L3 未揭露（目前資料 0 缺席，屬潛在） | 接線 Gate 重審 | 總管提案 |
| `I1140-SECTOR-CRON-SCOPE` | 診斷計數是「最近一次 cron」範圍，文案不得寫成整窗 | 接線文案約束 | 總管 |
| `I1140-SECTOR-UNOBS-LABELS`／`-DROPPED-PRICE` | 偶發標籤成因、15761 組成（本文已釐清範圍，成因仍 NOT VERIFIED） | 影響 DG-COV 判讀 | 總管（獨立一組查證） |
| `I1140-MARGIN-UNIT-MIX` | 僅在取歷史序列／趨勢時觸發；只顯示最新點不阻塞 | 條件式 | 總管 |
| 接線必要條件（不是 Gate，是施工前提） | 新增 `margin_fact_service`／`sector_flow_fact_service` 具名 import 至 `G2F_IMPORT_ALLOWLIST`；`real_feed` 新增隔離讀取；`RealFeedSnapshot` 與 `real_canonical` 新增欄位與四態映射；Market VM 新增 L1 section（不動 `MARKET_CARD_IDS`）；`views/market.py` 於 OneBrain 下方渲染；`WIRED_PATHS` 納入；FAKE 對稱占位帶 FAKE 標示；5 頁頂部導航不變；390／1440 重測；Cloud／Playwright／真機驗證 | 全屬**未授權**的程式變更 | 待 WIRING-GATE |

### 4.2 間接依賴（INFERENCE：不直接阻塞，但影響時間語意或版面）

| ID | 與本區塊關係 |
|---|---|
| G-F4（Digest v2 schema／compat／PIT） | 本區塊不進 Digest；惟其「PIT 設計」若將來要求 `release_date`，會回頭影響 DG-PIT 的證據需求 |
| G-F5（production caller 時機） | 管 `assemble_digest` caller，**不是**本區塊前提；但 DEC-164 §四已另行規定「UI2 feed／section 接線」須新 Gate，該 Gate 即 WIRING-GATE |
| G-F3（A2 stale 取向） | 定義 STALE 值能否進 Digest 段；本區塊為顯示層，INFERENCE 不阻塞 |
| 版面高度 | 新區塊會推高 `scroll_end_bottom`，舊量測不適用（N-15） |

### 4.3 其他專案 Gate（**不得**列為市場頁前提）

| ID | 說明 |
|---|---|
| G-F2 headless 持股授權 | Digest 是否消費私有持股；本區塊不含持股 |
| G-F6 登入前置（`NUI2-AUTH-CONTRACT-GATE`） | 持股段／Active Sheet 前置；本區塊為公開市場資料 |
| `I1144-DG-A3`、`I1144-DG-HEALTH` | Digest 配對一致性與 health 範圍；獨立 Gate、未授權 |
| 外資 L3、OneBrain runtime／AI Provider、Digest v2、production caller | 另案；OneBrain 僅是本區塊的**版面位置參照**（新區塊放其下方），不是本區塊的資料或 Gate 前提 |
| `I1140-` TWII／Digest／macro 路徑項（PRICE-WORDING、FUTURE-ASOF-ASYM、TODAY-TZ、OHLC-GUARD、AI-FUTURE-ASOF、NAN-MID-WINDOW、C12-PATH-NOT-EXHAUSTIVE、MACRO-STATE-NONCANON、REGIME-SET-EQ、MACRO-BARREL-ST、DIGEST-HEALTH-RANGE） | 與融資＋板塊區塊無直接依賴（INFERENCE） |
| #1119 HOLD、#1124～#1126（#1126 PIT 未驗） | 禁止順手處置 |

---

## 5. 三方案比較

> A、C **僅為未來候選，不是施工授權**；客戶已核准的只有 B。

| 項目 | **A 融資優先** | **B 先關閉證據缺口（已核准）** | **C 融資＋板塊** |
|---|---|---|---|
| 內容 | 日後僅接融資一項（一個讀取、一個 VM 欄位、一組守衛） | 唯讀證據補強＋文件＋SSOT 追加；零程式變更 | 日後依線框接融資與板塊全套 |
| 正確性 | 中高：僅最新點單位／sanity 已驗，歷史混用未驗；授權 NOT VERIFIED | 最高：不產生新顯示 | 中：衍生聚合顯示條件、ETF 家族揭露、偶發標籤解讀、與大盤外資口徑混淆風險 |
| 風險 | 低～中 | 最低 | 中～高 |
| 速度（INFERENCE） | 快 | 本案已完成；之後等裁示 | 慢（約為 A 的數倍） |
| Token（INFERENCE） | 低 | 已耗 | 高（測試面與版面重測） |
| 先決 Gate | DG-LIC、DG-PIT、WIRING-GATE；不需 DG-COV | 無（已核准） | DG-COV、DG-PIT、DG-LIC、WIRING-GATE 皆須先裁示 |
| 授權狀態 | **未授權** | **已授權**（「同意 B」） | **未授權** |

---

## 6. RECOMMENDATION（AI 推薦；非裁示）

1. **維持方案 B 停點**：不寫程式、不接線，停在 WIRING-GATE。
2. **不得自行放行**授權（DG-LIC）、PIT（DG-PIT）或最低 coverage（DG-COV）；沉默不等於同意。本文**不自設任何 coverage 百分比或門檻值**。
3. 若客戶日後要前進，推薦順序：先裁 DG-LIC／DG-PIT → 再裁 DG-SCOPE（推薦 A）→ 最後才討論 DG-COV 與板塊。理由：板塊的母體定義含偶發標籤（I-1、I-2），**在客戶釐清「母體口徑」前，任何比例門檻都沒有穩定分母**。
4. 接線若獲授權，UI 文案須遵守：資料日外露；`fetched_at` 明示為「系統抓取時間，非官方發布時點」；不稱全市場；38／41 與未觀測清單同時揭露；不排序；不與「大盤外資淨買賣超（僅外資）」並列加減；缺值不補 0。

---

## 7. 待客戶裁示

| # | 問題（商業語言） | 選項 | AI 推薦（非裁示） |
|---|---|---|---|
| 1 | TWSE／TPEX／FinMind 資料在雲端呈現與加總，是否先取得官方條款原文再決定？ | 先確認（客戶放行沙箱網域或貼條款原文）／風險自負先行 | 先確認 |
| 2 | 沒有「來源發布時間」，只顯示「資料日＋我們抓到的時間」可以嗎？ | 接受（明示非發布時點）／不接受 | 接受並明示；屬客戶語意 |
| 3 | 板塊沒涵蓋全部標籤時，還要不要顯示「合計」？ | C0 只揭露／C1 比例上限（客戶給值）／C2 指定必有板塊／C3 永不顯示合計；亦可先裁「母體要不要排除偶發標籤」 | 先裁母體口徑，再談門檻；數值由客戶定 |
| 4 | 日後若進入接線，先接融資一項還是兩項？ | A／C | A（融資先） |
| 5 | 是否另開新 Gate 授權 UI2 runtime 接線？ | 授權／暫不 | 暫不，待 1～3 |

---

## 8. 撰寫組抽查與降級紀錄

**抽查範圍（實跑）**：`daily_net.parquet`（形狀、日數、標籤數、最新日 2265／−920.25／−942.44、3 偶發板塊出現日、ETF 353／−254.29）、`bubble_latest.json`（41、53、20）、`metadata.json`（`coverage` 全欄位）、融資／外資 parquet（最新值、4912 bootstrap 列、近 60 筆區間、缺日）、`industry_raw.json`（3174／選列分布／2330 雙標籤）、`SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS`＝4、`STALE_DAYS_DAILY`＝7、`MARKET_CARD_IDS`、`G2F_IMPORT_ALLOWLIST`、cron 排程、FinMind README 三句。**未抽查**：近 6 日板塊 vs 外資差額序列、`per_day` 逐項細節、GitHub Actions 執行紀錄、`twse_holiday_fetcher` 內部。

| # | 原證據項 | 處置 | 原因 |
|---|---|---|---|
| 1 | 3 偶發板塊成因判定為「分類」（VERIFIED／NOT VERIFIED 混標） | **降為 INFERENCE**（I-1） | `daily_net` 無個股代碼，無法確認是哪一檔；僅有成員碼對照 |
| 2 | 「母體含偶發標籤，n_unobserved 反映標籤噪音而非真實板塊沒資料」 | 標為 INFERENCE（I-1、I-2） | 因果解讀，非直接觀測 |
| 3 | 「三個獨立抓取路徑一致，傾向休市」 | **降級並加註**（I-4） | 融資與外資同為 FinMind 同 cron，只剩兩條獨立路徑；無休市表 |
| 4 | 「`unresolved_days=[]` 故非缺抓」 | 降為 INFERENCE | 該欄只保留最近一次 cron，無法排除歷史缺抓 |
| 5 | FinMind 個人使用「VERIFIED（僅限字面）」 | **降為 INFERENCE** | README 宣告「教育、非商業」，並未明文許可個人使用或展示 |
| 6 | 外資分項與大盤差 −41.8 億；排除 ETF 後 −666.0 億 | **數字修正** | 抽查實算 −41.87→約 −41.9；ETF＋ETN 後約 −665.9，僅排 ETF 約 −666.0 |
| 7 | 前研究 §4.1「G-F2～G-F6 不阻塞本線」 | 維持 INFERENCE，並加列「若客戶另有語意須重列」 | 仍為推論 |
| 8 | 授權：WebSearch OGDL 線索 | 維持 NOT VERIFIED（二手） | 非原文 |
| 9 | 三份證據全文結論 | 維持「單組、未複驗」 | §-2 規則 6；本文抽查不等於獨立複驗 |
