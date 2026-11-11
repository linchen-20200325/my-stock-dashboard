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


---

## 9. B8：NAS 中繼站備援查證（2026-11-11；只追加；不改 §1～§8 任何字）

> **客戶新增指示 B8（2026-11-11 對話原文）**：「如果連不上線，記得要用 NAS 中繼站，可以參考舊 UI 的方式。」
> **授權範圍（僅此）**：官方網站（TWSE／TPEX／FinMind）直連不通時，**唯讀**參考舊 UI 既有的 NAS 中繼做法，查證授權條款原文。
> **不授權**：修改網路架構、新增服務、改 Secrets、繞過安全限制；自建第二套 Proxy；修改 NAS Server、新增端點、放寬認證、新增排程。**NAS 成功只代表網路可達，不代表再散布已授權，也不代表 PIT 合格。**
> **複驗程度**：本節為單組（執行 AI）產出，未經第二組獨立複驗（§-2 規則 6）。符號引用＝檔案＋符號，不寫行號。**不輸出任何 Secret／金鑰／內網位址的值，只記「是否已設定」。**

### 9.1 查證路徑與結果（2026-11-11，本沙箱）

| # | 路徑 | 實測 | 結果 | 原因／備註 |
|---|---|---|---|---|
| 1 | **Direct（直連）** | 對 TWSE 使用條款頁、TPEX 版權頁、FinMind 官網與 `finmind.github.io/Disclaimer`、`data.gov.tw/license`、`openapi.twse.com.tw` 各 GET 一次（亦以既有 `fetch_url()` 對 TWSE 條款頁測一次） | **失敗** | 本沙箱唯一對外出口是 agent proxy（Claude 沙箱代理，**不是** repo 的 NAS Squid）；對上述官方網域回 `CONNECT tunnel failed, response 403`（政策拒絕）。與上輪（`ENOTFOUND`）一致，失敗型態不同但同為網域不在放行名單 |
| 2 | **既有 Proxy（repo 的 NAS Squid，`get_proxy_config`）** | `get_proxy_config()` 回 `None` | **未測試** | `PROXY_URL`／`NAS_PROXY_URL`／`HTTP_PROXY` 皆未設定（見 §9.3）。**不得**把環境變數 `HTTPS_PROXY`（agent proxy）當作 NAS Squid 使用或冒充 |
| 3 | **NAS 中繼站（`nas_relay_fetch`）** | `get_nas_relay()` 回 `None`；`nas_relay_fetch()` 回 `None`（未發出任何請求） | **未測試** | NAS 連線資訊（`NAS_BASE_URL`／`NAS_RELAY_URL`／`NAS_API_KEY`）在本環境**皆未設定**；依程式設計「未設定則自動跳過」。不自行填值、不自建替代中繼 |
| 4 | **官方 GitHub（`raw.githubusercontent.com`）** | FinMind README GET | **成功（HTTP 200）** | 與上輪相同，僅得 README 三句（見 §1.4）；**不是**官網條款全文 |

**結果**：官方條款頁**一頁都沒取得**。B8 指示的 NAS 備援路徑在本環境**不可執行（未配置）**，不是「執行後被拒」。維持 NOT VERIFIED，**不突破**。

### 9.2 舊 UI NAS 中繼做法的實際契約與安全限制（FACT，唯讀讀檔）

來源：`src/data/proxy/proxy_helper.py`（`fetch_url`、`get_nas_relay`、`nas_relay_fetch`、`get_proxy_config`）、`src/data/proxy/nas_server.py`（`/proxy` 端點、`_auth`、`_assert_public_url`）、`SPEC.md` §9.7。

| 面向 | 契約 |
|---|---|
| 呼叫順序（`fetch_url`） | ① 若有 Squid 設定則先走 Squid（SSL `verify=False`）；② Squid 失敗（ProxyError／403）→ 降級直連；③ 最後手段 → NAS 中繼。**NAS 中繼是純失敗路徑增益**，未設定時行為與沒有它完全一致 |
| 設定讀取順序（Squid） | `st.secrets` 的 `PROXY_URL` → `NAS_PROXY_URL` → `[proxy]` 區段；其次環境變數 `PROXY_URL` → `NAS_PROXY_URL` → `HTTP_PROXY` → `http_proxy`。⚠️ **風險（FACT）**：若環境剛好設了 `HTTP_PROXY`（例如某些沙箱），`get_proxy_config` 會把它當 Squid 用。本環境該變數**未設定**，故未觸發 |
| 設定讀取順序（NAS 中繼） | 環境變數 `NAS_BASE_URL`／`NAS_RELAY_URL` ＋ `NAS_API_KEY`；缺 base 時再查 `st.secrets` 同名鍵；base 為空→回 `None`（跳過） |
| 中繼端點 | `GET`／`POST {NAS_BASE_URL}/proxy?url=<目標>`；NAS 端 server-side 代抓並**原樣轉回** Status／Content-Type／Body |
| 認證 | 請求標頭 `X-API-Key`（對應 NAS 端環境變數 `NAS_API_KEY`）。**NAS 端若未設 key，`/proxy` 無認證開放**（程式啟動時印警告；硬性拒絕啟動屬部署行為，由客戶決定）。⚠️ **本節不評估客戶實際 NAS 是否設了 key（NOT VERIFIED）** |
| 目的主機限制 | **沒有「主機白名單」**：`_assert_public_url` 只擋 scheme 非 http／https、無 host、以及解析到私有／loopback／link-local／保留／多播／未指定位址（SSRF 防護，每一跳轉址都檢查，最多 6 跳）。**公開網址（含 TWSE／TPEX／FinMind／data.gov.tw）原則上放行**。已知限制：不防 DNS rebinding（程式註解自陳） |
| 逾時 | client 端預設 `timeout=15`（`fetch_url` 轉呼叫時傳入自身 timeout）；NAS 端對目標 `timeout=20` |
| 傳輸安全 | `SPEC.md` §9.7 與 `nas_server.py` 檔頭的設定範例為 `http://…:8765`（明文 HTTP，**範例而非實際值**）；client 端 `requests.get(..., verify=False)`。**INFERENCE**：若實際部署為 HTTP，API Key 與回傳內容在傳輸途中未加密；實際 scheme **NOT VERIFIED**（本環境無設定可查） |
| 快取／退避 | `fetch_url` 有 300 秒 URL 快取（只快取 HTTP 200）；未見指數退避 |
| 用途定位 | 為繞過**資料中心 IP 被官方來源 403**（NDC、CIER、Google News 等）而設；是**取數**管道，**不是授權／再散布機制** |
| GitHub Actions | 多支 workflow 以 secrets 名稱 `PROXY_URL`／`NAS_BASE_URL`／`NAS_API_KEY` 注入（例：`probe_tw_sources.yml`、`update_sector_flow.yml`、`update_macro_history.yml`）。**是否已在 GitHub 端設定：NOT VERIFIED**（本沙箱無權限、亦不應嘗試讀取 secrets） |

### 9.3 本環境 NAS 連線資訊是否已配置（僅 True／False，未列印任何值）

| 變數名 | 已設定？ |
|---|---|
| `NAS_BASE_URL` | **False** |
| `NAS_RELAY_URL` | **False** |
| `NAS_API_KEY` | **False** |
| `NAS_PROXY_URL` | **False** |
| `PROXY_URL` | **False** |
| `HTTP_PROXY`／`http_proxy` | **False**（`HTTPS_PROXY` 為 True，但屬 agent proxy，與 repo NAS 無關） |
| `.streamlit/secrets.toml` | 不存在（僅有 `secrets.toml.example`） |

**結論**：本環境**未合法配置**NAS 中繼；未自行補值、未用 agent proxy 冒充、未建第二套中繼，亦未修改任何 Secrets／設定。

### 9.4 授權表更新

**無變動。** 本次未取得任何新的官方條款原文：

| 來源 | §3／§1.4 結論 | §9 後 |
|---|---|---|
| TWSE | NOT VERIFIED | **不變**（NOT VERIFIED） |
| TPEX | NOT VERIFIED | **不變** |
| data.gov.tw／OGDL-Taiwan-1.0 | NOT VERIFIED（僅二手線索） | **不變** |
| FinMind | 僅 README 三句（範圍有限） | **不變**；官網 Disclaimer 未取得 |

> **取代 §3 的哪一項**：**無**。§3 的 N-1～N-4 全部維持原狀。DG-LIC 維持 NOT VERIFIED。

### 9.5 邊界聲明（避免誤讀）

1. **網路可達 ≠ 已授權。** 即使日後 NAS 中繼讀到條款頁，也只證明「能讀到該頁」；再散布／公開展示／衍生聚合是否被允許，須逐字讀條款並標明**適用的資料集**。
2. **網路可達 ≠ PIT 合格。** 能抓到資料不產生 `release_date`；`fetched_at`≠`release_date` 的原則不變。
3. **官方頁面讀取 ≠ 資料取用同意。** 條款頁是公開 HTML；經 NAS 抓條款頁與經 NAS 抓行情資料是兩件事，後者不在 B8 範圍。
4. **INFERENCE（AI 推論，須客戶／法律判斷）**：repo 現行 production 取數（cron／NAS 路徑）能運作，**不構成**授權證據；是否「非商業」、是否公開提供衍生檔，仍屬 §7 第 1 項待裁示。

### 9.6 仍 NOT VERIFIED，與客戶可選的解封方式（皆為選項，非本批授權）

| # | 仍 NOT VERIFIED | 可選解封方式（客戶決定） |
|---|---|---|
| 1 | TWSE 條款／openapi 授權／交易資訊轉載限制 | (a) 客戶貼上官方條款原文；(b) 客戶放行沙箱網域（`www.twse.com.tw`、`openapi.twse.com.tw`）；(c) 客戶提供**已合法配置 NAS 的執行環境**，並明確授權在該環境以既有 `nas_relay_fetch`／`fetch_url` 做唯讀 GET（仍不改任何程式、Secrets、排程） |
| 2 | TPEX 版權頁／openapi／data.gov.tw | 同上（網域：`www.tpex.org.tw`、`openapi.tpex.org.tw`、`data.gov.tw`） |
| 3 | FinMind 官網 Disclaimer／服務條款 | 同上（網域：`finmind.github.io`、`finmindtrade.com`） |
| 4 | OGDL-Taiwan-1.0 原文 | 同上（`spdx.org` 或 data.gov.tw 授權頁） |
| 5 | 實際 NAS 是否設 API Key、是否 HTTPS、GitHub secrets 是否已設 | 客戶自行確認（本沙箱無權限且不應讀取） |

> 備註：repo 內既有 `probe_tw_sources.yml` 為手動探針，但其腳本不含條款頁網址（`grep` 條款／版權關鍵字 0 命中）；要用它抓條款頁需改腳本，**屬程式修改，本批未授權**，僅記錄不執行。

**DG-LIC 維持 NOT VERIFIED；WIRING-GATE 仍未授權；B8 不改變任何 Gate。**


---

## 10. Coverage 母體定義收斂（2026-11-11；只追加；不改 §1～§9 任何字）

> **客戶裁示（2026-11-11 對話原文，DEC-169）**：「同意先收斂 Coverage 母體並補上 TWSE、TPEX、FinMind 官方條款證據。僅授權 docs-only 查證與 GitHub SSOT 更新；其餘 Gate 保持 HOLD。」
> **性質**：docs-only 研究；**不是**採用新母體、**不是**設定門檻、**不是**接線授權。本節**不提任何 coverage 百分比**。
> **複驗程度**：本節由一份單組研究員證據（未入 repo）彙整；撰寫組已抽查其關鍵數字（見 §12），**仍是單組，未經第二組獨立複驗**（§-2 規則 6），其全稱結論只能當待驗事項。符號引用＝檔案＋符號，不寫行號。
> **標籤**：VERIFIED FACT（本回合實跑／讀檔）／INFERENCE／NOT VERIFIED／RECOMMENDATION（非裁示）。

### 10.1 現行母體的形成過程（可追溯鏈）

| 步 | 內容（檔案＋符號） | 標籤 |
|---|---|---|
| a | 兩條來源併用：FinMind `TaiwanStockInfo` 原始列（`market_close_fetcher::_finmind_industry_rows`）；官方 openapi 公司基本資料（`_official_industry_codes`；上市 `t187ap03_L` 1099 檔、上櫃 `mopsfin_t187ap03_O` 897 檔；只讀「代號」「產業別代碼」兩欄）。`industry_raw.json` 存全部原始列＋官方列＋選列結果，共 **3174 碼** | VERIFIED（撰寫組抽查：官方非空 1996＝1099＋897） |
| b | 選列 `select_industry_records`：官方碼→官方名（`shared/industry_codes.py::OFFICIAL_INDUSTRY_CODE_NAMES`）；FinMind 有相符列用 FinMind 名，否則官方名；官方查無→FinMind 決定論選列。分布：`official_match_finmind` 1977／`finmind_no_official` 1188／`official_name` 9 | VERIFIED（抽查重現） |
| c | 股日→板塊 `src/compute/sector_flow.py::compute_sector_daily_net`：法人列∩有效收盤（>0）；無對映→「未分類」；外幣 ETF 排除 | VERIFIED（讀程式＋metadata） |
| d | 別名標準化 `canonicalize_sector_daily`＋`SECTOR_CANONICAL_ALIASES`（版本 `z43-v1`，8 組合併）；不丟列 | VERIFIED |
| e | 母體＝窗口（20 交易日）內**任一天出現過**的標準板塊（`scripts/update_sector_flow.py::_write_bubble_json`）＝**41**；觀測＝最新日有列＝**38** | VERIFIED |
| 追溯斷點 | ① `daily_net.parquet` 不存個股代碼；② `industry_raw.json` 只存最新一份快照（git 追蹤歷史僅 2 個 commit，repo 為 shallow，更早版本 NOT VERIFIED）；③ 37 個資料日中 **19 日**的列 `fetched_at` 皆為 2026-10-12（Z43 回補批）——**歷史列用的是回補當下的產業對映，不是各日的 PIT 對映** | VERIFIED（①③抽查重現；②讀 `git log`） |

**母體組成（分類算術）**：41＝**34 個官方產業名**（名稱屬官方碼表 36 個非空名之一，且官方快照內≥1 成員）＋**4 個證券類別標籤**（ETF、ETN、受益證券、存託憑證；存託憑證的官方碼 91 其官方名稱為空）＋**3 個偶發標籤**（不屬前兩類）。**標籤：VERIFIED（算術；抽查依同一規則重現 34／4／3）；該規則是研究員自訂的判別，不是官方分類。**

### 10.2 三個偶發標籤：證據與未解

| 標籤 | 37 日內出現日 | 檔數／金額 | 與官方分類的關係 | 未解（NOT VERIFIED） |
|---|---|---|---|---|
| 化學生技醫療 | 僅 2026-10-20（1 日） | 1 檔、+0.843 億 | **不是官方產業名**（官方有「化學工業」21、「生技醫療業」22）；成員碼 8 個，皆 `finmind_no_official`；FinMind 同碼各回 2 列（舊名＋此標籤） | 哪一檔、為何僅 1 日、為何官方查無 |
| 電子工業 | 10-27、10-30（2 日） | 各 1 檔、金額 ≤0.008 億 | **是官方碼表名（代碼 13），但官方現況 0 成員**（`industry_codes.py` 自陳 ISIN 查無、保留只因下拉有）；成員碼 46 個，皆 `finmind_no_official` | 哪一檔產生金額微小的列；46 碼為何多數官方查無 |
| 未分類 | 12 日（09-14～10-16；窗口內 4 日） | 每日 1 檔、金額 ≤0.0004 億 | 哨兵值（有法人列＋收盤但代碼不在對映）；`industry_raw` 內無任何碼標為未分類 | 哪一檔；為何 10-16 後消失（碼被補入？下市？）；前 9 筆在 10-12 回補批寫入 |

| 補充事實 | 標籤 |
|---|---|
| 窗口總股日 **44769**，3 偶發標籤合計 **7 股日**；全 37 日總股日 82768、3 標籤合計 **15 股日**；最新日（11-09）3 標籤無列，合計不受影響。**僅算術，非業務結論。** | VERIFIED（抽查重現） |
| 3 標籤出現日 `twse_ok／tpex_ok／industry_ok` 皆 True；窗口 `tpex_complete`＝True。故非「TPEx 缺」；「非缺抓」為 INFERENCE（`unresolved_days` 只留最近一次 cron） | VERIFIED／INFERENCE |
| 機制（INFERENCE）：「母體＝窗口內出現過」＋FinMind 對同碼多列且互相矛盾（`industry_raw`：3174 碼中 **1000** 碼回≥2 種標籤，其中官方有收錄 **810** 碼；例 2330 同回「半導體業」「電子工業」）＝偶發標籤進入母體的機制。研究員另推測「化學生技醫療」「電子工業」可能是證交所類股指數類別名被 FinMind 同時當個股標籤（`industry_raw` 內有 32 個 FinMind `Index` 類股指數鍵）——**未證實** | VERIFIED（計數）／INFERENCE（機制） |
| 規則性判別：「標準板塊名∈官方產業名且官方快照≥1 成員」不靠人工名單即可把 3 標籤分出來 | VERIFIED（抽查重現） |

### 10.3 四種「覆蓋」的區分（本文不估算任何一種的比率）

| 覆蓋 | 分子／分母 | 現有資料能否算 | 標籤 | 要算還需要什麼（皆屬新儲存／新來源，**未授權**） |
|---|---|---|---|---|
| **板塊標籤覆蓋** | 最新日有列的標準板塊數／母體標準板塊數 | **可算**：38／41（恆等式建構時強制）；**分母隨母體定義而變** | VERIFIED | 母體定義經客戶裁示 |
| **個股覆蓋** | 進入板塊個股數／應涵蓋個股數 | **不可算**：分子只有各板塊 `n_stocks` 加總（2265），無代碼清單；分母（官方可交易普通股清單＋上市／下市日）repo 無 canonical 形式 | NOT VERIFIED | 每日逐檔落地（股號、板塊、是否有法人列、是否有有效收盤）＋官方上市櫃清單與適用日期＋授權確認 |
| **交易金額覆蓋** | 進入板塊成交金額／全市場成交金額 | **不可算**：`daily_net` 的 `net_amt_yi` 是**三大法人淨買賣超金額，不是成交金額**；repo 無被丟棄 15761 股日的成交金額，也無全市場成交金額落地 | NOT VERIFIED | 逐檔成交金額（含被丟棄列）與大盤成交金額；分子分母需同口徑 |
| **市值覆蓋** | 進入板塊市值／全市場市值 | **不可算**：無股本／流通股數／市值欄 | NOT VERIFIED | 逐檔股本（PIT）×價；上市日期；ETF 是否計入需客戶定義 |

> 「38／41」「15761」「2265」皆**不是**個股／金額／市值覆蓋。15761 僅最近一次 cron（`coverage.n_days`＝1）的有法人列但無有效收盤股日數，非累計，組成 NOT VERIFIED。

### 10.4 COV-A／B／C 比較表

> 三者皆**僅為研究候選，不是施工授權**（DEC-167／DEC-169）。

| 驗收維度 | **COV-A** 近 20 日動態聯集＋強制揭露（現況） | **COV-B** 官方分類當候選母體 | **COV-C** 只用已驗證穩定分類集合，「標註不剔除」 |
|---|---|---|---|
| 母體有明確來源 | 有（窗口內標準標籤）；但來源含 FinMind 偶發標籤 | 官方碼表有；**僅涵蓋公司**，ETF／ETN／受益證券無官方產業碼 | 有：官方名集合＋證券類別標籤＋原始證據；每個板塊附來源類別 |
| 分子分母可重現 | 可（`daily_net`＋別名表；恆等式強制） | 分母可由 `industry_raw` 重算；**逐檔分子不可** | 板塊層可重現；個股層同 B 不可 |
| PIT／版本可追溯 | 母體**每日可能不同**；對映非 PIT（§10.1 斷點③） | 無生效日／版本 | 規則可版本化，但輸入快照無 PIT |
| 新上市／下市／分類變動 | 自動進出母體（偶發標籤同理） | 官方家數相對探針時點已漂移（上市＋4、上櫃＋4，引自研究員對 repo 內探針紀錄的比對；未獨立重驗）；repo 不存上市日期 | 新標籤自動歸入「未驗證」而非靜默吸收 |
| TWSE／TPEX 差異 | `daily_net` 無市場欄，看不到 | 兩 openapi 共用同一代碼體系（repo 內引述，**本回合無法重驗上游**）；以官方碼為鍵可免別名 | 同 B（需新程式） |
| ETF／ETN／存託憑證口徑 | 全納入合計（已有 caveat） | **無官方產業碼**，需另採證券類別（未進資料） | 單列「證券類別型」，不與產業混算 |
| 缺價／缺漏可觀測性 | 缺席格有（53），但**全數來自 3 偶發板塊**，判別力低 | 同左；另需補官方母體缺席 | 缺席可分「驗證類／未驗證類」，53 格可歸因 |
| 全市場合計誤讀風險 | 中：38／41 看似缺 3 個大類 | 高：易被讀成「官方全市場」 | 低～中：仍非全市場，須揭露 |
| 保留原始 Evidence | 是（不丟列） | 若剔除官方查無者＝**丟證據** | 是：未驗證者保留原始標籤、天數、檔數 |
| 正確性 | 中（口徑清楚、母體含噪音） | 低（涵蓋與證據皆不足） | 中高（理論），**需新增實作與驗證** |
| 風險 | 低（現況） | 高（授權 NOT VERIFIED、覆蓋不全） | 中（分類規則誤判；FinMind 標籤易變） |
| 速度／Token（INFERENCE） | 最快、最低（零改動） | 慢：需新來源、授權、儲存 | 中：純函式＋測試，不需新來源 |
| 授權狀態 | 現況，不需新授權 | 需資料來源／儲存（**未授權**） | 需程式變更（**未授權**） |

**COV-B 不可採的依據（撰寫組抽查重現）**：官方產業代碼只涵蓋 1996 家公司（上市 1099＋上櫃 897），**不含 ETF／ETN／受益證券**；現行最新日 378／2265 股日落在 ETF 家族六個標籤（ETF 238、上櫃ETF 115、ETN 11、指數投資證券(ETN) 3、受益證券 4、存託憑證 7）；官方查無的碼另有 1188（其中興櫃 394 碼、4 位數上市櫃碼約 186～190〔見 §12 降級〕）。純官方當母體會得到「看似完整的分類」卻掩蓋這些無歸屬者，違反 §1。

### 10.5 推薦（RECOMMENDATION；非裁示）

| 項 | 內容 |
|---|---|
| 現階段 | **暫不改母體**：維持「近 20 交易日窗口內任一天出現的標準板塊」＝41；不改別名、不改算法、不改門檻 |
| 日後揭露合計的最低限度 | **COV-A 強制揭露**：資料日、採樣窗口（20 交易日）、觀測數／母體數、未觀測清單、「不代表全市場」、診斷計數為最近一次 cron 範圍、板塊合計≠大盤外資淨額（G-10） |
| 若客戶要求避免偶發標籤誤導 | 研究候選＝**COV-C「標註不剔除」**：母體＝窗口聯集不變；每個標準板塊附規則化「來源類別」——① 官方產業 ② 證券類別型 ③ **未驗證**（保留原始標籤、出現天數、n_stocks，單列計數，**不刪、不併、不補零**）；合計＝全部列，另附分類小計。優點：「是否偶發」從人工判斷改為可重現規則；新怪標籤自動落入③；維持 G-3 恆等式 |
| **不選 COV-B 的理由** | 缺 ETF 家族；無版本／適用日／授權證據；剔除官方查無者＝丟證據；易被誤讀為官方全市場 |
| 也不推薦「直接排除偶發標籤」 | 排除＝丟證據，違反 §1 |

### 10.6 PIT／分類版本必要條件（若日後走 COV-C 或 COV-B）

| # | 條件 | 現況 |
|---|---|---|
| 1 | 每份分類快照帶抓取時間＋來源端點＋版本標記，且可回溯「某日的列使用了哪一份」 | 有 `industry_raw.fetched_at`／`industry_scheme`，但**只留最新一份**；**歷史列用回補當下的對映，而非各日 PIT 對映**（§10.1 斷點③） |
| 2 | 官方分類的適用／上市日期（或明示無此資訊並降級揭露） | 無（repo 只讀兩欄；官方 openapi 是否提供上市日期欄 NOT VERIFIED） |
| 3 | 規則版本號（類比 `z43-v1`）；規則變動遞增 | 「來源類別」規則尚不存在 |
| 4 | 新標籤預設落入「未驗證」，不得自動併入或刪除 | 無（現行：自動進母體） |
| 5 | 逐檔層級要有每日個股清單才能談個股覆蓋 | 無（未授權） |
| 6 | 上游條款（TWSE／TPEx／ISIN／FinMind）確認 | 見 §11：FinMind PARTIALLY；TWSE／TPEx NOT VERIFIED |

### 10.7 是否具備設定 coverage 門檻的基礎

| 門檻型態 | 判斷 | 標籤 |
|---|---|---|
| 現有**可計算**的量 | 板塊標籤層：觀測數、母體數、未觀測清單、`n_absent_cells`、`tpex_complete`、`is_stale` | VERIFIED |
| 以比例設門檻（38／41） | **沒有穩定分母**：分母含偶發標籤，且各板塊大小差異懸殊（最新日每板塊 3～238 檔），標籤數比例對大小板塊一視同仁 | INFERENCE |
| 以類別條件設門檻（非百分比） | 有基礎但**需 COV-C 先落地**（例如「未觀測板塊是否全落在『未驗證』類」＝布林條件） | RECOMMENDATION |
| 以個股／金額／市值設門檻 | **無基礎**（§10.3 全 NOT VERIFIED） | NOT VERIFIED |
| 門檻值本身 | 屬業務語意，**須客戶裁示**；**本文不建議任何數值** | — |

### 10.8 尚缺證據

1. 3 偶發標籤各是哪一檔、哪天、為何出現與消失（需逐檔落地或回溯當日 FinMind 快照）。
2. 15761 缺價列的證券組成；2384（有收盤碼）與 2265（進板塊）相差 119 的原因。
3. 官方 openapi 是否含上市日期／異動欄；官方產業碼表新增、改名的生效日。
4. 官方查無的 4 位數上市櫃碼是否為下市／更名／未收錄；FinMind `date` 欄語意。
5. 興櫃 394 碼是否可能出現在法人來源。
6. ETF 家族 FinMind 標籤與交易所證券類別是否一致。
7. TWSE／TPEx 使用與再散布條款（§11）。
8. origin 上是否已有比 2026-11-09 更新的 canonical data（研究員與撰寫組皆未 `git fetch` 比對）。
9. 本節全部判斷的第二組獨立複驗。

### 10.9 下一個需客戶裁示的問題（商業語言；附 AI 推薦，非裁示）

| # | 問題 | 選項 | AI 推薦 |
|---|---|---|---|
| 1 | 日後若顯示板塊資金，「涵蓋多少」你想看哪一種數字？ | ① 板塊個數（現況，可算）／② 個股檔數／③ 成交金額／④ 市值（②③④目前**算不出**，需先授權逐檔資料落地與官方母體來源） | ①，並明確標示「不是個股涵蓋率」；②～④ 暫不做 |
| 2 | 對「只出現 1～2 天的怪標籤」要怎麼處理？ | A 維持現況計入母體＋揭露／B 計入但標為「未驗證類別」不刪（COV-C）／C 直接排除 | A（現階段不改）；若要處理選 B，**不選 C**（排除＝丟證據） |
| 3 | 若選 B：是否授權之後（另案、另 Gate）實作「來源類別」規則與測試？ | 授權／暫不 | 暫不；待 #1、#2、授權（DG-LIC）與時間語意（DG-PIT）有結論 |

---

## 11. 官方授權對照矩陣（2026-11-11；只追加；不改 §1.4／§3／§9 任何字）

> **性質**：授權條款**原文蒐證**，**不是法律意見**，不宣告任何用途合法或違法，不構成「已取得再散布授權」。
> **複驗程度**：由一份單組研究員證據彙整；撰寫組已抽查 FinMind 引文與原檔一致，並**對 FinMind 官方 GitHub 原始檔做了即時重抓、位元組比對**（見 §12）。**仍是單組，未經第二組獨立複驗。**
> **與 §1.4／§3 N-3 的關係**：§1.4 寫「FinMind 僅 README 三句」、§3 N-3 寫「官網條款 NOT VERIFIED」是**當時的事實**；本節因取得 FinMind 官方 GitHub Pages 原始檔而**更新讀法**（FinMind 由「僅 README」升為 PARTIALLY VERIFIED）。§1.4／§3 原文不改；TWSE／TPEX／data.gov.tw 的 N-1、N-2、N-4 **維持**。
> **證據等級**：VERIFIED／PARTIALLY VERIFIED／NOT VERIFIED／INFERENCE／RECOMMENDATION。

### 11.1 取得途徑與限制

| 途徑 | 結果 |
|---|---|
| TWSE（`www.twse.com.tw`、`openapi.twse.com.tw`）、TPEX（`www.tpex.org.tw`）、`data.gov.tw`、`finmindtrade.com`、`finmind.github.io` 官網 | 沙箱 agent proxy 一律 `CONNECT` 被拒（HTTP 403／連線失敗）；撰寫組抽查重測 4 個主機（TWSE、TPEX、data.gov.tw、finmindtrade）皆失敗。**零頁原文**。NAS 中繼未配置（§9），未使用 |
| `raw.githubusercontent.com`（官方 GitHub） | **成功**：FinMind 官方 GitHub 組織下 `FinMind/FinMind`（README、LICENSE）與 `FinMind/FinMind.github.io`（`master` 分支，即官網 `finmind.github.io` 的發布原始檔；README 本身連到該網站）的 Disclaimer、PrivacyPolicy、CommercialUse、Pricing、逐資料集說明頁 |
| SPDX 授權清單（`spdx/license-list-data`） | 成功，取得 OGDL-Taiwan-1.0 **轉錄本**；**不是** data.gov.tw 原頁 |
| WebSearch | 僅摘要；列為 INFERENCE 線索，**不當原文** |

### 11.2 FinMind 條款原文（逐字；版本日期 2026-10-31；來源＝官方 GitHub Pages 原始檔，非官網即時頁）

> 頁內版本日期 2026-10-31 與 2026-11-11 官網即時頁是否相同：**NOT VERIFIED**（官網不可連）。

| ID | 出處 | 逐字摘錄 | 等級 |
|---|---|---|---|
| Q1 | 「免責聲明與資料授權說明」§一 | 「其餘資料，FinMind 依各資料來源機關公布之公開揭露或開放資料規範使用。」 | VERIFIED（FinMind 條款） |
| Q2 | 同上「臺灣證券交易所交易資訊」 | 「本服務所提供之臺灣證券交易所交易資訊，資訊來源：臺灣證券交易所「TWSE」，本資訊由芬麥數據股份有限公司處理提供。」「使用者須遵守臺灣證券交易所『交易資訊使用管理辦法』等交易資訊管理相關規定。」 | VERIFIED |
| Q3 | 同上 §二 來源標示 | 「使用者如將透過本服務取得之資料用於對外用途，亦應依相關授權條款，以適當方式標示原資料提供機關。」 | VERIFIED |
| Q4 | 同上 §三 使用者之授權範圍 | 「本服務之授權不包含將本服務提供之資料對外再散布、轉售，或建置實質等同於本服務之鏡像服務。」 | VERIFIED |
| Q5 | 同上 §三 | 「使用者如有將資料對外公開、再散布或提供予第三方之需求，應自行確認並取得原資料來源機關所要求之相應授權；此類授權非 FinMind 所能授予或代為取得。」 | VERIFIED |
| Q6 | 同上 §三 | 「券商分點類資料之來源機關對其利用另有限制：該類資料僅供使用者自行使用，不論所訂閱之方案為何，均不得以任何形式再傳輸或提供予第三人。」 | VERIFIED（**僅分點類**；本專案未使用） |
| Q7 | 同上 §四 | 「FinMind 不就資料之正確性、完整性或時效性，於原始揭露形式之範圍外另作保證。」「本文件不構成法律意見。」 | VERIFIED |
| Q8 | 「使用條款與隱私權政策」§4 | 「使用者不得將即時資料直接呈現於 web、App 等對外介面，亦不得對外再散布原始資料或建立實質等同於本服務之鏡像服務。」 | VERIFIED |
| Q9 | 「方案與價格」使用授權表 | Free／Backer／Sponsor：個人、學術、web／app 開發等**非商業**用途 ✅；SaaS、AI、web／app、公司內部系統等**商業**用途 ❌；整合至產品用於商業行為 ❌。Sponsor Pro 商業 ✅。**「再散布原始資料、建立鏡像 API」兩欄皆 ❌**；「將即時資料直接呈現於 web、App 等對外介面」兩欄皆 ❌；「需標示資料來源『FinMind』」兩欄皆「需要」 | VERIFIED |
| Q10 | 「商業使用 Q&A」 | 「請勿直接再散布原始資料，或架設鏡像 API。」「請標示資料來源「FinMind」。」 | VERIFIED |
| Q11 | FinMind README（GitHub） | 「本專案提供的所有內容均用於教育、非商業用途。」；LICENSE＝Apache-2.0 | VERIFIED（字面；Apache-2.0 **只管 SDK 程式碼，不是資料授權**） |
| Q12 | 逐資料集說明頁 | 「如需對外展示，請自行向來源機關取得相應授權」**僅出現在券商分點／大額類資料頁**（Chip 頁 9 處，抽查計數一致）；本專案所用資料集頁內**未見**此額外限制句 | VERIFIED（出現處）／單組不存在性判斷（未見處） |
| Q13 | OGDL-Taiwan-1.0（**SPDX 轉錄本**） | 「各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸……編輯、改作」；「應以符合附件所示「顯名聲明」要求之方式，明確標示原資料提供機關之相關聲明；未盡顯名標示義務者，視為自始未取得開放資料之授權。」 | **PARTIALLY VERIFIED**（轉錄本，非 data.gov.tw 原頁；是否適用本專案取數 NOT VERIFIED） |

**FinMind 自述（非證據）**：Disclaimer §一稱其合法使用基礎含「與資料來源機關另行簽訂之資訊使用契約」。這是 FinMind 的自述；**契約內容與是否涵蓋本專案的轉載＝NOT VERIFIED**，不得推論本專案受其保護。

### 11.3 逐資料集對照矩陣

「—」＝無原文可引；凡「個人使用／Cloud 公開顯示／重製／改作／衍生聚合／再散布」格無原文者＝**未確認**。

#### 11.3.1 TWSE／TPEX／data.gov.tw（全部無原文）

| 資料集 | 來源（程式實證） | 落地檔（git 追蹤） | 官方條款原文 | 證據等級 | 備註 |
|---|---|---|---|---|---|
| TWSE T86（三大法人買賣超日報） | `www.twse.com.tw` rwd 網頁 JSON | 聚合入 `sector_flow/daily_net.parquet` | — | **NOT VERIFIED** | 僅有二手線索：FinMind 稱須遵守『交易資訊使用管理辦法』（Q2）。**不得以 FinMind 通則回推 TWSE 授權** |
| TWSE MI_INDEX（收盤行情） | 同上 | 僅用於換算金額，不存個股列 | — | **NOT VERIFIED** | 同上 |
| TWSE BFI82U／FMTQIK／MI_MARGN | 同上 | 落地情形未逐一確認 | — | **NOT VERIFIED** | 同上 |
| TWSE openapi（`t187ap03_L`、holidaySchedule、exchangeReport） | `openapi.twse.com.tw` | `sector_flow/industry_raw.json`（官方列）、`ticker_sector.json` | — | **NOT VERIFIED** | 該 API 站是否自有授權聲明、是否掛 data.gov.tw 並適用 OGDL：未知。**不得把 OGDL 套到 T86／MI_INDEX** |
| TWSE MOPS（`t163sb04`）／mis `all_etf` | `mops.twse.com.tw`、`mis.twse.com.tw` | `fundamentals/{sii,otc}_*.parquet` 等（個股級） | — | **NOT VERIFIED** | MOPS 條款獨立於 TWSE 主站，未查 |
| TPEX insti／afterTrading | `www.tpex.org.tw` 網頁 JSON | 聚合入 `daily_net.parquet` | — | **NOT VERIFIED** | 不得把 TWSE 條款套 TPEX；網頁 JSON 與 openapi 授權是否一致未知 |
| TPEX openapi（`mopsfin_t187ap03_O`） | `www.tpex.org.tw/openapi/` | `industry_raw.json`、`ticker_sector.json` | — | **NOT VERIFIED** | 搜尋摘要稱上櫃公司基本資料在 data.gov.tw 標 OGDL v1（INFERENCE，**未見原頁**）；該端點是否即該資料集未知 |
| data.gov.tw 6100（國發會 PMI） | `data.gov.tw/api/v2/rest/dataset/6100` | `tw_pmi.parquet`、`macro_last_good/tw_pmi.json` | — | **NOT VERIFIED**（OGDL 文字 PARTIALLY） | 需看**該資料集頁**的授權欄與顯名文字 |

**WebSearch 線索（INFERENCE，非原文）**：搜尋摘要稱 TWSE 網站使用條款禁止未經同意以自動化裝置、指令碼、爬蟲程式下載網站資料，並稱出版品載明資訊用戶不得轉讓他人、須與證交所簽使用契約；稱 TPEX 另有獨立網站使用條款含類似自動化下載禁止。若屬實，與本專案 cron 程式化抓取 rwd JSON 直接相關，**但屬摘要線索，未見原文，不得據以下結論**。TAIFEX 條款不適用本專案。

#### 11.3.2 FinMind（官方 GitHub 原始檔；PARTIALLY VERIFIED）

| 資料集 | 逐資料集頁可證事實 | 個人使用 | Cloud 公開顯示 | 重製／改作 | 衍生聚合 | 再散布原始資料 | 來源標示 | 未確認 | 等級 |
|---|---|---|---|---|---|---|---|---|---|
| `TaiwanStockTotalInstitutionalInvestors`（外資日序列 → `finmind_inst.parquet`） | 資料區間 2004-04-01 起；FinMind 自述更新時間「星期一至五 15:00，實際更新時間以 API 資料為主」；頁內無來源機關限制聲明 | 非商業方案 ✅（Q9） | Q5：對外公開須**自行**取得原資料來源機關授權；Q8：禁「即時資料」於對外介面（本資料非即時分類）。**是否構成「對外介面」文字未定義** | 條款未逐項列 | 條款未明文禁止聚合；Q4／Q8 禁「原始資料再散布／鏡像」 | **禁**（Q4、Q8、Q9 兩欄皆 ❌） | 須標「FinMind」（Q9、Q10）；TWSE 資訊字樣見 Q2；對外用途須標原資料提供機關（Q3） | 本專案所持方案／Token 等級；專案是否商業；此資料集的實際來源機關（頁內未寫明） | **PARTIALLY VERIFIED** |
| `TaiwanStockTotalMarginPurchaseShortSale`（融資 → `finmind_margin.parquet`） | 資料區間 2001-01-01 起；FinMind 自述更新「星期一至五 21:00」；頁內無額外限制 | 同上 | 同上 | 同上 | 同上 | 同上 | 同上 | 同上；單位混用屬資料品質議題（`I1140-MARGIN-UNIT-MIX`），非授權議題 | **PARTIALLY VERIFIED** |
| `TaiwanStockInfo`（板塊產業別 → `industry_raw.json` 的 FinMind 原始列、`ticker_sector.json`） | 「列出台灣所有上市、上櫃、興櫃的股票名稱、代碼和產業類別」；自述更新「每天 1:30」；頁內無限制聲明 | 同上 | 同上 | 同上 | `industry_raw.json` 內含 FinMind **全部原始列**（個股級）＝原始列落地於公開 repo | 同上 | 同上 | 原始列入 git 是否為「再散布原始資料」＝**法律判斷**，不下結論 | **PARTIALLY VERIFIED** |
| 券商分點類（9 頁） | 「僅供訂閱用戶自行使用……」；對外展示須取得來源機關授權 | ✅ 自用 | **禁** | — | — | **禁** | — | **本專案未使用**（grep 無 TradingDailyReport）；**分點條款不自動套用至他資料集** | VERIFIED（範圍） |
| `finmind_m1m2`、`twii_ohlcv` | `finmind_m1m2.parquet` 的 `source` 欄為 CBC EF15M01，`twii_ohlcv.parquet` 為 Yahoo `^TWII` | — | — | — | — | — | — | **不在 TWSE／TPEX／FinMind 三家範圍**，各自條款**另查**（央行、Yahoo） | **NOT VERIFIED** |

> **FinMind 自述更新時間**（15:00／21:00／1:30）是其服務排程宣稱，**不是官方發布時點，不等於 `release_date`**，不得用來滿足 DG-PIT。

**FinMind 條款≠TWSE／TPEX 條款**：FinMind 條款約束的是「使用者與 FinMind 之間」；Q4／Q5 明講對外公開須由使用者向**原資料來源機關**取得授權，且「非 FinMind 所能授予」。因此 FinMind 條款的取得**不能**替代 TWSE／TPEX 條款，也**不能**證明本專案已獲再散布權。Apache-2.0 只涵蓋 FinMind SDK 程式碼（Q11），不涵蓋資料。

**教育／非商業聲明的解讀**：README 稱「教育、非商業」（Q11）；方案表區分非商業與商業（Q9）。「Cloud 公開展示個人儀表板」是否屬非商業、是否算「對外介面」，文字**未定義**，須客戶／法律專業判斷，不得直接當允許或禁止。

### 11.4 repo 公開與 `data_cache` 落地面（僅陳述事實；不做法律結論）

| 事實 | 值／內容 | 標籤 |
|---|---|---|
| repo 可見性 | 公開（`gh api` 查 repo `.private` 欄位回 `false`；撰寫組抽查重現） | VERIFIED |
| `data_cache` 追蹤檔數 | `git ls-files data_cache` ＝ **29** 檔（含 `.gitkeep`） | VERIFIED（抽查重現） |
| `sector_flow/industry_raw.json` | **875,758 位元組**、3174 碼；含 **FinMind `TaiwanStockInfo` 全部原始列**＋TWSE `t187ap03_L`／TPEX `mopsfin_t187ap03_O` **官方原始列**＋選列紀錄；**個股級** | VERIFIED |
| `sector_flow/ticker_sector.json` | 代碼→產業標籤（選列結果，個股級對照） | VERIFIED |
| `sector_flow/daily_net.parquet`、`bubble_latest.json`、`metadata.json` | 板塊層**聚合**，不含個股列 | VERIFIED |
| `finmind_inst.parquet`、`finmind_margin.parquet` | FinMind 市場級日序列（各 4939 列） | VERIFIED（形狀見 §1.2） |
| `fundamentals/{sii,otc}_*.parquet`（12 檔） | 個股季財報欄位；來源 MOPS `t163sb04`；MOPS 條款未查 | VERIFIED（來源）／NOT VERIFIED（條款） |
| `tw_pmi.parquet`、`macro_last_good/tw_pmi.json` | data.gov.tw 6100 PMI 序列 | VERIFIED（來源） |
| `finmind_m1m2.parquet`、`twii_ohlcv.parquet`、`forward_test/picks.parquet`、`macro_forward_test/signals.parquet`、`health_watchlist.json` | 非三家來源或內部運算 | VERIFIED |
| UI 是否已顯示 FinMind 要求的來源標示（Q9、Q10：「FinMind」；Q2：TWSE 資訊字樣） | 撰寫組 grep `芬麥` 於 repo `.py`／`.md`／`.html`／`.json` **0 命中**；僅 grep，**未目視各頁面** | **未見／NOT VERIFIED** |
| FinMind 本專案方案等級（Free／Backer／Sponsor／Sponsor Pro） | repo 內無法判定 | **NOT VERIFIED** |
| Streamlit Cloud 公開網址與是否收費 | repo 內本輪未確認 | **NOT VERIFIED** |

> **以上僅是事實陳述。** 「公開 repo 內保留 FinMind 個股級原始列／官方 openapi 原始列」與 FinMind Q4／Q8／Q9「再散布原始資料」之間的界線、聚合檔與市場級日序列是否屬「原始資料」、非商業認定、是否須標示來源——**皆為需客戶／法律專業判斷**，本文不下結論，也不建議任何刪檔或改檔（那是客戶範圍決策，§8.4 step 4）。

### 11.5 對 DG-LIC 的影響

| 項 | 結論 |
|---|---|
| FinMind | 由「僅 README 三句」升為 **PARTIALLY VERIFIED**：取得官方 GitHub Pages 條款原文，但**不含**方案等級、來源機關另行契約、官網即時版本；且條款本身說對外再散布須自行取得原資料機關授權 |
| TWSE、TPEX、data.gov.tw | **維持 NOT VERIFIED** |
| DG-LIC | **維持待客戶／法務裁示；未關閉**。網路可達≠授權；條款存在≠特定資料集適用≠本專案已取得再散布權 |

---

## 12. 本輪抽查與降級紀錄、殘餘阻塞、下一步（2026-11-11；只追加）

### 12.1 抽查範圍與結果

**抽查方式**：撰寫組對 `data_cache/sector_flow/*`、`industry_raw.json`、`shared/industry_codes.py`、`shared/sector_flow_thresholds.py` 實跑計算；對 FinMind 官方 GitHub Pages 原始檔做**即時重抓並以 SHA-1 位元組比對**；並重測 TWSE／TPEX／data.gov.tw／finmindtrade 連線。**抽查不等於第二組獨立複驗。**

| # | 項目 | 研究員原述 | 撰寫組抽查結果 | 處置 |
|---|---|---|---|---|
| 1 | 41／38／3、53 缺席格、2265、−920.248 億、`window_size`＝20 | 同 §1.1 | **重現**（41 板塊；最新日 46 原始標籤、Σ`n_stocks`＝2265、合計 −920.248、外資分項 −942.438；`n_absent_cells`＝53） | 維持 VERIFIED |
| 2 | 15761／18026／4／`n_days`＝1 | metadata `coverage` | **重現**（`n_dropped_missing_price`＝15761；`n_stock_days_with_net`＝18026；`n_excluded_foreign_ccy_stock_days`＝4；`n_days`＝1；18026−15761＝2265） | 維持 |
| 3 | 7 股日（窗口）／15 股日（全 37 日） | 3 偶發標籤股日 | **重現**（窗口總股日 44769 中 3 標籤 7；全 37 日 82768 中 15；三標籤出現日數 1／2／12 與窗口內 4 日） | 維持 |
| 4 | 34＋4＋3 組成 | 41＝34 官方＋4 證券類別＋3 偶發 | **依同一規則重現**；但分類屬研究員自訂判別（存託憑證因官方碼 91 名稱為空而歸證券類別；若改依「有官方成員」則為 35＋3＋3）。電子工業與綜合在官方快照 0 成員 | 維持，**註明規則依賴**（§10.1），不寫成官方分類 |
| 5 | `industry_raw.json` 分布 | 官方碼 1996、查無 1188、興櫃 394 | **重現**（官方非空 1996＝上市 1099＋上櫃 897；rule 分布 1977／1188／9；興櫃 394；3174 碼中 1000 碼回≥2 標籤、其中官方有收錄 810；2330 雙標籤） | 維持 |
| 6 | 官方查無的 4 位數上市櫃碼 | **190**（上市 154＋上櫃 36）；其中 FinMind `date` 在 2024-12 者 **86** | 以「官方查無、4 位數碼、FinMind type 為 twse／tpex」重算＝**186**（twse 150＋tpex 36）、2024-12 者＝**82**；標籤前四名（電子工業 43、半導體業 17、金融保險 15、ETF 14）**重現** | **降級**：數字改寫「約 186～190（依碼型啟發式分組，撰寫組重算為 186／82；差 4 與 4 原因未釐清）」，**不採 190／86 為已驗證數字**；成因（下市／更名／未收錄）本就 NOT VERIFIED |
| 7 | 1188 的內部分項（興櫃 394＋ETF 樣式 414＋4 位數 190＋特別股 39＋ETN／受益 42＋TDR 25＋其餘 84） | 碼型啟發式分組 | **僅興櫃 394 與 ETF 樣式約 428（撰寫組啟發式）部分驗證；其餘分項未逐項抽查**；ETF 樣式 414 與撰寫組重算 428 不一致 | **降級**：分項數字不引用，僅引用 1188 總數與興櫃 394 |
| 8 | 37 日中 19 日 `fetched_at`＝2026-10-12（回補批） | 同 | **重現**（19／37） | 維持 |
| 9 | `industry_raw.json` git 歷史僅 2 commit、兩份比對 0 增減 0 變動 | 同 | `git log` 重現 2 個 commit（repo 為 shallow）；**兩份內容比對未重做** | 「0 增減」降為研究員原述，未抽查 |
| 10 | 最新日 ETF 家族 378／2265 | 同 | **重現**（ETF 238、上櫃ETF 115、ETN 11、指數投資證券(ETN) 3、受益證券 4、存託憑證 7＝378） | 維持 |
| 11 | 上市／上櫃家數相對探針漂移（＋4／＋4）、兩 openapi 共用代碼體系、6 個官方碼上市櫃拼寫不同 | repo 內引述／研究員重算 | **未抽查**（探針紀錄與上游皆不可重驗） | 標為研究員原述，於 §10.4 已註明 |
| 12 | FinMind 條款引文 Q1～Q13 | 逐字 | 對 scratchpad 內原檔**逐句 grep 一致**（Q1～Q5、Q6、Q7、Q8、Q9、Q10、Q11、Q13）；Q12 「僅分點頁 9 處」計數一致。**另對 `raw.githubusercontent.com/FinMind/FinMind.github.io/master/{Disclaimer,CommercialUse,Pricing}/index.html` 即時重抓：Disclaimer、Pricing 與原檔 SHA-1 完全相同，CommercialUse 位元組大小相同**；頁內版本日期 2026-10-31 重現 | 維持 PARTIALLY VERIFIED；**來源為官方 GitHub 原始檔，非官網即時頁** |
| 13 | Q9 引文 | 研究員摘要 | 抽查補出原表兩列研究員未列：「整合至產品用於商業行為」Free／Backer／Sponsor 為 ❌；「將即時資料直接呈現於 web、App 等對外介面」兩欄皆 ❌ | 已補入 §11.2 Q9 |
| 14 | OGDL-Taiwan-1.0 | SPDX 轉錄本 | 轉錄本兩條引文重現 | 維持 **PARTIALLY**（轉錄本，非原頁） |
| 15 | repo 公開、`data_cache` 29 檔、`industry_raw.json` 875,758 B | 同 | **重現**（`gh api` `.private`＝false；`git ls-files data_cache` ＝29；檔案大小 875758） | 維持 |
| 16 | TWSE／TPEX／data.gov.tw／finmindtrade 官網 | 全不可連 | 撰寫組重測 4 主機皆失敗（agent proxy 拒絕） | 維持 NOT VERIFIED |
| 17 | 「UI 未見 FinMind 來源標示」 | grep `芬麥` | 撰寫組 grep `芬麥` 0 命中；**僅 grep，未目視頁面** | **降為「未見／NOT VERIFIED」**，不寫成「已確認未標示」 |
| 18 | 「FinMind 逐資料集頁無額外限制」 | 不存在性判斷 | 僅 Chip 頁見 9 處分點限制句（計數一致）；**其餘頁未逐頁重做** | 維持單組不存在性判斷，不得當窮舉 |
| 19 | 兩份證據全文結論 | — | **未做第二組獨立複驗** | 維持「單組、未複驗」 |

**未抽查**：官方碼表 36 個非空名逐項、`SECTOR_CANONICAL_ALIASES` 8 組合併的逐組成員、1188 內部其餘分項、TDR 10 檔、32 個 `Index` 鍵、FinMind 其餘逐資料集頁、Streamlit Cloud 部署設定。

### 12.2 本輪「降級／修正」彙整

1. 官方查無的 4 位數碼：190／86 → **約 186～190／約 82～86**，不採為已驗證數字（#6）。
2. 1188 內部分項（ETF 樣式 414 等）：**不引用**（#7）。
3. 34＋4＋3：標明**規則依賴**，非官方分類（#4）。
4. 「UI 未標示 FinMind 來源」：降為**未見／NOT VERIFIED**（#17）。
5. 「兩份 industry_raw 快照比對 0 增減」：降為研究員原述（#9）。
6. 「兩 openapi 共用代碼體系」「家數漂移」：降為研究員／repo 內引述，上游**不可重驗**（#11）。

### 12.3 殘餘阻塞（本輪**未關閉**任何客戶 Gate）

| Gate | 狀態 | 本輪進展 |
|---|---|---|
| **DG-COV** | **HOLD** | 母體形成過程與三偶發標籤證據釐清；COV-A／B／C 比較完成；**未設任何門檻或百分比**；母體口徑待客戶裁示 |
| **DG-PIT** | **HOLD** | 補出「歷史列用回補當下對映」這一 PIT 缺口；`release_date` 仍無；FinMind 自述更新時間≠發布時點 |
| **DG-LIC** | **HOLD** | FinMind PARTIALLY VERIFIED；TWSE／TPEX／data.gov.tw 仍 NOT VERIFIED；repo 公開與 `data_cache` 落地面僅陳述事實，**待客戶／法律專業判斷** |
| **DG-SCOPE** | **HOLD** | 未動 |
| **WIRING-GATE**（`I1144-WIRING-GATE`） | **HOLD／未授權** | 未動 |
| **G-F2～G-F6**、`I1144-DG-A3`、`I1144-DG-HEALTH` 等其餘 Gate | **HOLD** | 未動 |

**仍 NOT VERIFIED**：TWSE／TPEX／data.gov.tw 授權原文與適用資料集；OGDL 原頁；FinMind 官網即時版本、方案等級、與來源機關的另行契約；來源發布日／PIT／修訂；3 偶發標籤個股成因；15761 組成；缺日是否休市；UI 來源標示是否顯示；Cloud、iOS／Android 真機、Playwright／viewport；本節全部結論的第二組獨立複驗。

**本節不得被讀成**：已採新母體、已設門檻、已取得任何資料的再散布授權、已驗證 PIT、已同意接線、「FinMind 條款已涵蓋 TWSE／TPEX」、「repo 公開不構成問題」或「repo 公開構成違規」。

### 12.4 下一步推薦（RECOMMENDATION；非裁示）

1. **維持停點**：不寫程式、不接線，停在 `WIRING-GATE`；其餘 Gate 保持 HOLD。
2. **DG-LIC 解封路徑**（沿用 §9.6，現再補一條）：(a) 客戶貼上 TWSE『交易資訊使用管理辦法』與 TWSE／TPEX 網站使用條款原文；(b) 客戶放行沙箱網域（`www.twse.com.tw`、`openapi.twse.com.tw`、`www.tpex.org.tw`、`data.gov.tw`）；(c) 客戶提供已合法配置 NAS 的環境並明確授權唯讀 GET；(d) **新**：客戶或法務就「是否商業／是否公開對外／是否保留個股級原始列於公開 repo」三問給出判斷（FinMind 條款顯示這三問決定方案等級與是否需向來源機關另取授權）。
3. **DG-COV**：先裁「覆蓋要用哪一種口徑」（§10.9 #1）與「偶發標籤怎麼處理」（#2），再談門檻；數值由客戶定，AI 不提。
4. 若客戶要求最小風險面，個股級原始列是否繼續落地於公開 repo 屬**客戶範圍決策**（§8.4 step 4），本輪不動；AI 推薦僅在客戶明確要求時再另案提方案（附推薦），不主動動工（§-1）。
5. 若日後要求顯示 FinMind 來源標示，屬畫面變更，須先出線框草稿（§-1.5 UI 草稿先行）。

### 12.5 待客戶裁示

| # | 問題（商業語言） | 選項 | AI 推薦（非裁示） |
|---|---|---|---|
| 1 | 覆蓋要看哪一種數字？ | 板塊個數／個股檔數／成交金額／市值（後三者目前算不出） | 板塊個數，並標明非個股涵蓋率 |
| 2 | 怪標籤怎麼處理？ | 維持＋揭露／計入但標「未驗證」不刪／直接排除 | 維持＋揭露；若要處理選「標未驗證」，不選「排除」 |
| 3 | 是否先取得 TWSE／TPEX 條款原文再決定？ | 貼條款原文／放行網域／提供已配置 NAS 環境／風險自負先行 | 先取得原文 |
| 4 | 本專案是否屬商業？是否要公開對外？公開 repo 內保留個股級原始列是否可接受？ | 客戶／法務判斷 | 交法務；AI 不下結論 |
| 5 | 沒有發布時間，只顯示「資料日＋系統抓取時間」可以嗎？ | 接受（明示非發布時點）／不接受 | 接受並明示；屬客戶語意 |
| 6 | 是否另開新 Gate 授權 UI2 runtime 接線？ | 授權／暫不 | 暫不，待 1～5 |

**沉默不等於同意。** 其餘 Gate 保持 HOLD。
