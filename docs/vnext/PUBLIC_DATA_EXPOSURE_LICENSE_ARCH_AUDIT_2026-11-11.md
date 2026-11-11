# 公開 Repository 資料曝露、來源授權與儲存架構唯讀稽核（方案 B；docs-only）— 2026-11-11

> **性質**：唯讀稽核＋三方案比較。**不是法律意見**，不宣告任何用途合法或違法，**不是**資料遷移、刪除、改歷史、改 repo 可見性的授權或建議施工。
> **客戶裁示（2026-11-11 對話原文）**：「客戶已同意方案 B：先執行公開 Repository 的資料曝露、來源授權與儲存架構唯讀稽核，再決定是否修改資料保存方式。」（DEC-171）
> **基準**：main `043a4d21`；查核日 2026-11-11。符號引用＝檔案＋符號，不寫行號（`CLAUDE.md` §8.2.A.0 規則 1）。
> **證據來源與複驗程度**：三份單組研究員證據（曝露盤點／Git 歷史與架構／授權矩陣；未入 repo）。**撰寫組已自行實跑抽查並降級數項（見 §8），仍是單組，未經第二組獨立複驗**（§-2 規則 6）；其全稱句只能當待驗事項。
> **標籤**：FACT（本回合實跑／讀檔）／INFERENCE／NOT VERIFIED／RECOMMENDATION（非裁示）。
> **固定原則**：公開≠違法；API 可取得≠可再散布；條款存在≠適用於該資料集≠本專案已取得授權；網路可達≠授權；不自設門檻；不關閉任何 Gate。
> **安全**：本文與所有證據**未複製任何 Secret、Token、個人資料或資料列內容**，僅記位置、欄位名與計數。

---

## 0. 結論先行

| # | 結論 | 標籤 |
|---|---|---|
| 1 | repo **公開**（非 fork、forks_count=0，查詢時點）。`data_cache/` 現行追蹤 **29 檔、2,298,741 位元組（約 2.30 MB）**；其中**個股級（含股票代碼）15 檔**。無 Secret、個人持股、帳號跡象（regex 範圍內，非專業掃描器） | FACT |
| 2 | **授權證據 A／B／C 三層分開**：條款原文只有 **FinMind**（官方 GitHub Pages 原始檔，版本日期 2026-10-31）取得，且只算 **PARTIALLY VERIFIED**；TWSE／TPEX／MOPS／data.gov.tw／央行／Yahoo **零頁官方原文**；repo 內**找不到任何授權證據**（授權函、契約、方案憑證）。本專案是否商業、方案等級、Cloud 是否公開＝**NOT VERIFIED** | FACT／NOT VERIFIED |
| 3 | FinMind 條款明文：授權**不含**對外再散布、轉售、建置鏡像；對外公開須自行向原資料來源機關取得授權且「非 FinMind 所能授予」；Free／Backer／Sponsor 僅限非商業；任何方案皆禁再散布原始資料；須標示「FinMind」。**這些文字與公開 repo 內保留 FinMind 來源列／序列之間是否衝突，屬客戶／法律專業判斷，本文不下結論** | FACT（原文）／NOT VERIFIED（適用） |
| 4 | **Git 歷史使「停止追蹤」不足以降低曝露**：`data_cache` 歷史共 **1,036 個相異 blob、約 80.0 MB（未壓縮）**，存在於 main、各 `auto/data-*`、`docs/*` 分支與 1,133 個 PR head；2026-06-28 曾 untrack、2026-07-11 又重新追蹤，**移除期間的舊版仍在歷史**。唯有改寫歷史＋GitHub 端清理才可能移除，且 fork／本機 clone／快取不受控 | FACT（clone＋refs/pull）／INFERENCE（GitHub 端行為） |
| 5 | 網站（Streamlit Cloud）讀 **repo checkout 內的 `data_cache/`**（本地檔案 I/O）；程式無 raw.githubusercontent／GitHub API 的 runtime 抓取。若 `data_cache` 離開公開 repo，至少 **8 個 L1／L3 讀取模組＋約 61 個測試檔**直接受影響；現有資源（Google Sheets／NAS／`data` 分支／Artifact）**皆非現成可無縫替換的非公開資料倉** | FACT（受影響清單）／INFERENCE（影響程度） |
| 6 | **高優先級（可能與明文授權限制衝突，交客戶／法律裁示）**：`sector_flow/industry_raw.json`（FinMind＋TWSE＋TPEX 來源列，個股級，歷史 24 版）、`finmind_inst.parquet`／`finmind_margin.parquet`（FinMind 市場級日序列）。**非違規定論** | RECOMMENDATION（優先序） |
| 7 | **更正先前說法**：`industry_raw.json` 內 FinMind 列**不是整列原樣**，每列只保留 `date`／`industry_category`／`type` 三欄；官方部分只保留 `code`／`endpoint`／`market`／`name` 四欄（§4.3）。是否仍屬「原始資料」＝法律判斷 | FACT |
| 8 | **安全事件候選：無可確認事件**（Secret、個人資料）；僅 2 項低度本機路徑觀察與 1 項「選股偏好」觀察（§4.4）。是否另案由客戶決定 | FACT（regex 範圍）／NOT VERIFIED（非專業掃描器；PR-only 物件未掃） |
| 9 | 推薦（**RECOMMENDATION，非裁示**）：先取得 TWSE／TPEX／FinMind 授權的書面答案（三問，§7），**再**決定是否做任何遷移；若客戶要降低曝露面，優先考慮「可逆」的 **方案 C 第一階段**（僅停止新增、不動歷史），不動歷史改寫。**本稽核未動任何檔** | RECOMMENDATION |

---

## 1. 公開資料清單（`git ls-files data_cache`＝29 檔；FACT 抽查重現）

「個股級」＝檔內含股票代碼欄或 key。「第三方原始內容」只描述**來源與加工程度**，不構成法律定性：序列／聚合／轉換／內部運算。Workflow 縮寫：M＝update_macro_history、S＝update_sector_flow、F＝update_fundamentals、FT＝update_forward_test、MFT＝update_macro_forward_test。Runtime reader 取自研究員 `git grep`（**單組、動態拼接路徑可能漏掃**；本回合僅抽查 `industry_raw.json` 無 runtime reader）。

| # | 路徑 | 格式／大小(B) | 來源（程式實證） | 性質 | 個股級 | 含第三方原始內容 | runtime 使用 | workflow |
|---|---|---|---|---|---|---|---|---|
| 1 | `.gitkeep` | 空／0 | — | 佔位 | 否 | 否 | — | — |
| 2 | `finmind_inst.parquet` | parquet／79,113 | FinMind `TaiwanStockTotalInstitutionalInvestors` | 轉換（市場級日序列，4,939 列） | 否 | 轉換序列 | 是（macro_cache_reader→多個 service） | M |
| 3 | `finmind_m1m2.parquet` | parquet／11,018 | **央行 CBC** EF15M01（檔名含 finmind 為歷史沿用） | 轉換（月序列＋衍生 gap） | 否 | 轉換序列 | 是（以 macro_cache_reader 定義；實際消費者未確認） | M |
| 4 | `finmind_margin.parquet` | parquet／74,055 | FinMind `TaiwanStockTotalMarginPurchaseShortSale` | 轉換（市場級日序列，4,939 列） | 否 | 轉換序列 | 是 | M |
| 5 | `forward_test/picks.parquet` | parquet／5,678 | 內部運算（選股網凍結）；進場價端點未追 | 內部運算（100 列、51 檔、5 cohort） | **是（51 檔，含中文名）** | 內含進場價（來源 NOT VERIFIED） | 是（forward_test_store） | FT（裸 push） |
| 6 | `fundamentals/latest.json` | json／208 | 內部 metadata | 診斷計數 | 否 | 否 | 是 | F |
| 7–12 | `fundamentals/otc_114Q1…115Q2.parquet`（6 檔） | parquet／61,828～64,492 | MOPS `ajax_t163sb04`＋`ajax_t163sb05` | 轉換（個股×季，15 欄，875～891 列） | **是** | 轉換（解析自 HTML 彙總表） | 是（fundamentals_snapshot_loader） | F（裸 push） |
| 13–18 | `fundamentals/sii_114Q1…115Q2.parquet`（6 檔） | parquet／75,165～79,022 | 同上 | 轉換（1,059～1,083 列） | **是** | 同上 | 是 | F（裸 push） |
| 19 | `health_watchlist.json` | json／446 | 使用者追蹤清單模板 | 設定模板（`stocks=[]`，0 檔） | 否（空） | 否 | 讀取（update_health_history 排程已停用） | — |
| 20 | `macro_forward_test/signals.parquet` | parquet／17,880 | 內部規則輸出（47 列×25 欄）；含 1 欄 Yahoo 衍生 `twii_close` | 內部運算 | 否 | 內含 1 欄第三方衍生值 | **無 runtime reader**（僅 cron 讀寫） | MFT |
| 21 | `macro_last_good/tw_pmi.json` | json／291 | data.gov.tw dataset 6100 | 轉換（單筆最後良值） | 否 | 轉換 | 是（macro_core durable fallback） | M |
| 22 | `metadata.json` | json／1,107 | cron 診斷 | 診斷 | 否 | 否 | 部分 | M |
| 23 | `sector_flow/bubble_latest.json` | json／15,105 | 由 #24 聚合（41 板塊） | **聚合** | 否 | 聚合 | 是（sector_flow reader→UI） | S |
| 24 | `sector_flow/daily_net.parquet` | parquet／72,048 | TWSE T86＋MI_INDEX／TPEX insti＋otc（source 欄） | **聚合**（板塊×日 1,716 列；**無股票代碼欄**） | 否 | 聚合（個股列僅在記憶體加總） | 是 | S |
| 25 | `sector_flow/industry_raw.json` | json／875,758 | FinMind `TaiwanStockInfo`＋TWSE `t187ap03_L`＋TPEX `mopsfin_t187ap03_O` | **混合**：來源列（精簡欄位）＋選列結果 | **是（3,174 碼）** | **是（來源列，FinMind 3 欄／官方 4 欄；見 §4.3）** | **無 runtime reader**（僅 cron 沿用上一份） | S |
| 26 | `sector_flow/metadata.json` | json／3,019 | cron 診斷計數 | 診斷 | 否 | 否 | 是 | S |
| 27 | `sector_flow/ticker_sector.json` | json／85,070 | 由 #25 `chosen.label` 衍生 | 轉換（代碼→產業標籤，55 種） | **是（3,174 碼）** | 轉換 | 是 | S |
| 28 | `tw_pmi.parquet` | parquet／4,528 | data.gov.tw dataset 6100（國發會） | 轉換（月序列，172 列） | 否 | 轉換 | 是 | M |
| 29 | `twii_ohlcv.parquet` | parquet／208,470 | **Yahoo Finance** `^TWII` chart 端點 | 轉換（加權指數日 K，4,913 列） | 否 | 轉換序列（逐日原值） | 是 | M |

**小計（FACT）**：parquet 18、json 10、空檔 1；**個股級 15 檔**＝#5、#7～#18、#25、#27；合計 2,298,741 B，`industry_raw.json` 占約 38%。TWSE／TPEX 的**個股級原始交易列（T86、MI_INDEX、TPEX insti）未落地**，只落地板塊聚合與診斷計數。

**非 `data_cache` 的公開追蹤資料（FACT）**：`git ls-files` 其餘位置**無** parquet／csv／db／sqlite／pkl／xlsx；**554 個 PNG（68,349,543 B，約 65 MiB）皆在 `docs/vnext/`**，其中 76 個路徑含 `real`。抽查 1 張真實流程截圖（`phase5_target/p5_2/app_target_realflow_big50_390_tall.png`）：畫面可見個股代碼、板塊資金條與財報／估值數字——**公開 repo 另以截圖形式保存行情／基本面衍生畫面**；其餘截圖未逐張看（NOT VERIFIED）。另有 `ring1_report.txt`、`scripts/_out/margin_units_report.txt` 等診斷輸出（見 §4.4）。

---

## 2. 來源授權矩陣（A／B／C 三層分開）

- **A 層**＝條款原文是否已查到？**B 層**＝該條款是否適用本專案實際用到的資料集？**C 層**＝本專案是否**已取得**授權（需有證據）？
- 取得途徑：僅 `raw.githubusercontent.com`（官方 GitHub）可達；TWSE、TPEX、data.gov.tw、MOPS、央行、Yahoo 官方站在沙箱一律 `CONNECT` 被拒（撰寫組本回合重測 TWSE／TPEX／data.gov.tw：連線碼 000）。**NAS 中繼＝未測試**（`NAS_*`、`PROXY_URL` 本環境皆未配置；沙箱 `HTTPS_PROXY` 是 agent proxy，非 NAS，未冒充）。二手搜尋摘要一律 INFERENCE，不當原文。

| 來源 | 實際用於（落地檔） | A 條款原文 | B 資料集適用 | C 本專案已取得授權 | 主要限制訊號（皆非定論） |
|---|---|---|---|---|---|
| **FinMind** | #2、#4、#25（來源列）、#27（衍生） | **PARTIALLY VERIFIED**（官方 GitHub Pages 原始檔，版本日期 2026-10-31；官網即時頁不可連） | PARTIAL（逐資料集頁無額外來源機關限制句；單組不存在性判斷） | **NOT VERIFIED** | 非商業方案／禁再散布原始資料與鏡像／對外公開須另取得原機關授權／須標「FinMind」 |
| TWSE（rwd JSON、openapi） | #24（聚合）、#25（官方列） | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | INFERENCE（搜尋摘要）：條款稱禁自動化下載；『交易資訊使用管理辦法』未取得 |
| TPEX（網頁 JSON、openapi） | #24、#25 | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | INFERENCE：條款第五條稱禁自動化下載；部分 openapi 資料集在 data.gov.tw 標 OGDL v1（**未見原頁，是否即本端點未驗**） |
| MOPS（`t163sb04`／`t163sb05`） | #7～#18 | NOT VERIFIED（搜尋**找不到** MOPS 自身條款） | NOT VERIFIED | NOT VERIFIED | 無線索；是否沿用 TWSE 條款**未知，不得合併推論** |
| data.gov.tw 6100（國發會 PMI） | #21、#28 | PARTIAL（OGDL 僅 SPDX **轉錄本**，非原頁） | NOT VERIFIED（需看該資料集頁授權欄與顯名文字） | NOT VERIFIED | OGDL 若適用：重製／散布／改作條款明文，但**強制顯名**，未顯名視為自始未授權（轉錄本） |
| 央行 CBC（EF15M01） | #3 | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | INFERENCE（摘要）：宣告採 OGDL v1＋註明出處；摘要自承另一版本宣告未提；EF15M01 是否在範圍未驗 |
| Yahoo Finance（`^TWII`、yfinance） | #29、#20（`twii_close`）、#5（進場價為主） | NOT VERIFIED | NOT VERIFIED（本專案走未公開文件的 chart 端點） | NOT VERIFIED | INFERENCE（第三方 yfinance README，非 Yahoo）：稱 personal use only |

### 2.1 FinMind 條款原文（逐字；本回合對官方原始檔即時重抓，四頁 SHA-1 與證據檔**完全相同**）

| ID | 出處 | 逐字摘錄 | 判讀 |
|---|---|---|---|
| Q4 | 「免責聲明與資料授權說明」§三 | 「本服務之授權不包含將本服務提供之資料對外再散布、轉售，或建置實質等同於本服務之鏡像服務。」 | **明文禁**；`industry_raw.json` 等是否屬「資料再散布」＝法律判斷 |
| Q5 | 同上 §三 | 「使用者如有將資料對外公開、再散布或提供予第三方之需求，應自行確認並取得原資料來源機關所要求之相應授權；此類授權非 FinMind 所能授予或代為取得。」 | **FinMind 條款不能替代 TWSE／TPEX 授權** |
| Q8 | 「使用條款與隱私權政策」§4 | 「使用者不得將即時資料直接呈現於 web、App 等對外介面，亦不得對外再散布原始資料或建立實質等同於本服務之鏡像服務。」 | 「對外介面」未定義；本專案所用資料集非即時分類 |
| Q9 | 「方案與價格」使用授權表 | Free／Backer／Sponsor：非商業 ✅、商業 ❌、「再散布原始資料、建立鏡像 API」❌（Sponsor Pro 亦 ❌）；「需標示資料來源『FinMind』」需要 | 方案等級 NOT VERIFIED |
| Q10 | 「商業使用 Q&A」 | 「請勿直接再散布原始資料，或架設鏡像 API。」「請標示資料來源「FinMind」。」 | — |
| Q2／Q3 | 免責聲明 §一／§二 | 「使用者須遵守臺灣證券交易所『交易資訊使用管理辦法』等交易資訊管理相關規定。」「使用者如將透過本服務取得之資料用於對外用途，亦應依相關授權條款，以適當方式標示原資料提供機關。」 | 該辦法全文**未取得** |
| Q6 | 免責聲明 §三 | 券商分點類「僅供使用者自行使用…均不得以任何形式再傳輸或提供予第三人」 | **僅分點類；本專案未使用，不自動套用他資料集** |
| Q11 | FinMind README／LICENSE | 「本專案提供的所有內容均用於教育、非商業用途。」；LICENSE＝Apache-2.0 | Apache-2.0 **只管 SDK 程式碼，不是資料授權** |

**FinMind 自述（非證據）**：Disclaimer 稱其合法使用基礎含「與資料來源機關另行簽訂之資訊使用契約」；契約內容與是否涵蓋本專案轉載＝**NOT VERIFIED**。

### 2.2 C 層：本專案授權證據與來源標示現況

| 項 | 結果 | 標籤 |
|---|---|---|
| repo 內授權證據（授權函、書面同意、使用契約、方案憑證） | 研究員 grep（授權函／書面同意／使用契約／交易資訊使用）僅命中證據補充文件本身；無 `LICENSE*` 資料授權目錄 | 未見／NOT VERIFIED（grep 單組，**不證明 repo 外不存在**） |
| FinMind 方案等級、是否商業、Cloud 是否公開／收費 | repo 僅見 secret 名 `FINMIND_TOKEN`，不可判定 | NOT VERIFIED |
| FinMind 要求的來源標示字樣 | `芬麥` 於 repo `.py`／UI 0 命中（先前輪次 grep；本回合未重做）；`tab_edu` 舊 UI 有「資料來源地圖」列出 TWSE／TPEX／FinMind／Yahoo／MOPS | **僅 grep、未目視頁面 → 未見／NOT VERIFIED**；是否滿足標示條款＝法律判斷 |
| 資料檔層級的來源追溯 | #2～#4、#7～#18、#24、#28、#29 的 `source` 欄逐列標明來源（機器可追溯；本回合讀 parquet 欄位確認） | FACT |
| data.gov.tw／央行顯名聲明 | 未見（grep 單組） | 未見 |

---

## 3. Git 歷史曝露分析

### 3.1 事實（歷史數字由撰寫組以唯讀 bare clone `hist.git`＋`git log --raw`／`rev-list` 重算；**未對遠端重新 clone**，該 bare clone 與 `refs/pull/*/head` 為研究員先前 clone，見 §8）

| 項目 | 值 | 標籤 |
|---|---|---|
| 全 refs commit 數／main commit 數 | 4,673／2,256；PR head 共 **1,133**；branches 12 個（含 `data`） | FACT（重現） |
| `data_cache` 歷史相異 blob（排除 `.gitkeep`） | **1,036**，未壓縮合計約 **80.0 MB**；僅重打包這些 blob 約 4.6 MB | FACT（撰寫組重算；研究員原述 80.56 MB／pack 4.86 MB，降級見 §8） |
| 含 `stock.db`（僅 `data` 分支，1 版 0.79 MB）與 `etf_managers.json`（17 版，非 `data_cache`） | 1,054 blob、約 80.9 MB | FACT（重算） |
| 單檔歷史最大 | `industry_raw.json` **24 版、20.91 MB**（首次追蹤 2026-10-12）；`twii_ohlcv.parquet` 155 版（branches 可達；含 PR head 為 156） | FACT（重現） |
| main 上動到 `data_cache` 的非 merge commit | 335（其中 bot 329）；研究員原述 347／336，差異原因未釐清 | FACT（重算）／降級 |
| 僅在 PR head 可達的 `data_cache` blob | 重算 **7**（研究員原述 5） | FACT（重算）／降級 |
| 曾追蹤→移除→再追蹤 | `908bacab`（2026-06-28）untrack 四個頂層 parquet＋`metadata.json`；`89ddd17d`（2026-07-11）由 cron 重新 `git add -f`；**移除期間舊版仍在歷史** | FACT（重現） |
| 目前 open 的資料發布 PR | #1124／#1125／#1126（`auto/data-*`，皆 open 未合併） | FACT（`gh api`） |

### 3.2 停止公開追蹤後歷史是否仍可取得

| 角度 | 判斷 | 標籤 |
|---|---|---|
| 一般 `git clone`（所有 branch） | 可取得全部資料路徑的歷史 | FACT（研究員 clone 實測；撰寫組以該 clone 重算） |
| `refs/pull/*/head` | 1,133 個 PR head 可取得，含僅在 PR 的資料 blob | FACT |
| raw.githubusercontent／web blob／REST／GraphQL（含 SHA） | SHA 可達即可讀 | INFERENCE（GitHub 一般行為；**未對 raw URL 實測**） |
| fork／他人本機 clone／搜尋引擎或第三方封存 | 不受擁有者控制；forks_count=0 僅是查詢時點 | FACT（forks=0）／NOT VERIFIED（外部 clone） |
| 新 commit 刪檔或 `.gitignore` | **不影響歷史可取得性**（本 repo `908bacab` 即活證） | FACT |
| 改寫歷史（filter-repo／force-push） | 才可能自 branch 移除；PR head 與 GitHub 端可由 SHA 存取的懸空物件須另向 GitHub 清理；**不可逆、須客戶裁示，本任務禁止** | INFERENCE |
| 轉為私人 repo | 歷史與現有 clone 的可得性不同，但 **Streamlit Cloud 是否已有私人 repo 授權、部署追蹤哪個分支＝NOT VERIFIED** | INFERENCE／NOT VERIFIED |

### 3.3 資料發布機制（`.github/workflows` 實證，FACT）

| workflow | 頻率（UTC cron） | 寫回方式 |
|---|---|---|
| update_macro_history | 每日 09:00 | `scripts/publish_data_pr.py` → `auto/data-macro-history`＋PR（人工合併） |
| update_sector_flow | 每日 09:30 | `auto/data-sector-flow`＋PR |
| update_macro_forward_test | 平日 09:40 | `auto/data-macro-forward-test`＋PR |
| update_fundamentals／update_forward_test | 季更（8 個 cron 日）／每月 2 日 | **仍為裸 `git push`**；下一次排程是否被 branch protection 擋下＝NOT VERIFIED（本帳號無權讀 protection） |
| update_health_history | schedule 已註解停用 | 裸 push |
| export_db | 每日 21:00 | **`git push -f origin _pub:data`**（orphan 單 commit，`data` 分支，**同為公開**） |

`.gitignore` 對 `data_cache/*.parquet` 預設忽略，僅白名單四個頂層 parquet；其餘靠 `--force-add`。Actions artifact／cache：僅 UI 證據與 pip，**不保存 `data_cache`**（研究員 grep，單組）。

---

## 4. 風險分級與證據

> 分級依「**是否有明文限制文字可引**」「**個股級／來源列程度**」「**不可逆程度**」排序。**這是優先序，不是違規認定，不下法律定論。**

### 4.1 高優先級（可能與明文授權限制衝突；建議交客戶／法律裁示）

| ID | 項目 | 證據 | 為何列高 | 可逆的降低曝露方案（候選，**未授權施工**） |
|---|---|---|---|---|
| H1 | `sector_flow/industry_raw.json`（875,758 B、3,174 碼；歷史 24 版 20.91 MB）＋衍生 `ticker_sector.json` | FinMind `TaiwanStockInfo` 逐碼 3 欄＋TWSE／TPEX 官方 4 欄；**無 runtime reader**（僅 cron 沿用上一份） | FinMind Q4／Q5／Q8／Q9 明文禁「再散布原始資料」「鏡像」；TWSE／TPEX 條款 NOT VERIFIED；本檔 runtime 不用卻公開保存 | ①停止後續 cron 將來源列寫入公開 repo（保留 `ticker_sector.json` 衍生結果）；②來源列改存非公開位置；皆為**新增行為，歷史不變** |
| H2 | `finmind_inst.parquet`、`finmind_margin.parquet`（各 4,939 列日序列） | `source` 欄標明 FinMind 資料集；歷史各 108 版 | 條款禁再散布原始資料；「市場級單位換算後序列」是否仍屬原始資料**條款未定義**；須標示「FinMind」且 UI 標示現況未見 | ①先補來源標示（屬畫面變更，須線框草稿）；②轉私有儲存；③僅公開經確認可公開的聚合 |
| H3 | **歷史不可撤回**（結構性） | §3.2：移除追蹤不減歷史；PR head 另存 | 任何「現在停止追蹤」只管未來；已公開的版本仍可取得 | 只能先做「停止擴大」；歷史處理屬不可逆，**須客戶拍板**（§5 階段 4） |

### 4.2 中優先級（條款未查、無明文限制可引，或曝露面較窄）

| ID | 項目 | 理由 |
|---|---|---|
| M1 | `fundamentals/` 12 檔＋`latest.json`（MOPS，個股×季，10 個數值欄） | 個股級；MOPS 條款 NOT VERIFIED；有 runtime reader；FinMind 提示財報**原始文件**著作權屬發行公司，但該句針對 PDF，**不直接適用欄位資料**（INFERENCE） |
| M2 | `sector_flow/daily_net.parquet`、`bubble_latest.json`、`metadata.json`（TWSE／TPEX 聚合） | 無個股列；曝露的是聚合；INFERENCE：TWSE／TPEX 條款摘要稱禁自動化下載，**風險點在「抓取行為」，不只在「公開 repo」** |
| M3 | `twii_ohlcv.parquet`（Yahoo）、`macro_forward_test/signals.parquet`（含 Yahoo 衍生欄）、`picks.parquet` 進場價 | Yahoo 條款 NOT VERIFIED；走未公開文件端點；INFERENCE：第三方稱 personal use only |
| M4 | `tw_pmi.parquet`／`macro_last_good/tw_pmi.json`（data.gov.tw）、`finmind_m1m2.parquet`（央行） | OGDL 可能適用但**須顯名**；repo 未見顯名聲明；適用性 NOT VERIFIED |
| M5 | 554 張 PNG（約 65 MiB，`docs/vnext/`） | 抽查 1 張可見個股代碼與數字；內容性質與上述資料同類，其餘未看 |
| M6 | `forward_test/picks.parquet`（51 檔、100 列） | 內部運算，非持股；可揭露策略偏好（低度）；**不可重建**（§-1.5.F 判定 3(5)），任何刪除屬客戶裁示 |

### 4.3 對先前說法的更正（先前文件原文不改，自本節起有效讀法如下）

| # | 先前說法 | 更正（撰寫組實跑） |
|---|---|---|
| 1 | 補充文件 §11.3.2／§11.4 與授權證據稱 `industry_raw.json` 含 FinMind「**全部原始列**」 | 實測：FinMind 列共 4,381 筆，**每列僅 `date`／`industry_category`／`type` 三欄**（以 `stock_id` 為 key，不存公司名）；官方列 1,996 碼，**僅 `code`／`endpoint`／`market`／`name` 四欄**（產業代碼與產業名稱，無公司名稱、無公司基本資料）。但它仍是「個股代碼 × 第三方分類列」逐檔落地；**是否構成條款所稱原始資料＝客戶／法律判斷** |
| 2 | 盤點證據「`data_cache` 合計約 2.0 MB」 | 實測 2,298,741 B＝約 **2.30 MB** |
| 3 | 歷史「1,036 blob／80.56 MB」同時含 `stock.db` 與 `etf_managers` | 重算：僅 `data_cache`（排除 `.gitkeep`）即 1,036 blob／約 80.0 MB；含二者為 1,054／約 80.9 MB。**blob 數字相同是巧合，口徑不同** |
| 4 | 「僅 PR 的 blob 5 個」「main 347 commit」 | 重算 7／335；差異原因未釐清，不採為已驗證數字 |

### 4.4 安全事件候選（只記位置，不含值）

| 位置 | 觀察 | 等級 |
|---|---|---|
| `data_cache/` 29 檔（工作樹） | 研究員 regex 與撰寫組自行重跑 regex（email、JWT、sk-／ghp_／AIza／AKIA、`token|secret|password|api_key=`、PEM 標頭）**皆 0 命中**；`health_watchlist.json` `stocks=[]`；`industry_raw.json` 的 FinMind URL 不含 token | FACT（regex 非窮盡；加密／編碼型 Secret 偵測不到） |
| Git 歷史（all branches） | 研究員 regex 命中僅 `tests/*` 與 `SECRET_SCAN_CROSSCHECK` 文件中的 `-----BEGIN … PRIVATE KEY` 標頭字串（無金鑰本體）；歷史檔名掃描（`.env`／`secrets.toml`／`*.pem`／`*.key`）0 命中。**研究員 regex 非專業掃描器，PR-only 物件未掃；撰寫組未重跑歷史掃描** | FACT（研究員範圍）／NOT VERIFIED |
| FINMIND_TOKEN 前綴曾於舊 UI 顯示（STATE 自述，v19.170 後改長度） | 是否曾進 git 歷史 | NOT VERIFIED |
| `scripts/_out/margin_units_report.txt`、`ring1_report.txt` | 含**本機磁碟機路徑樣式**（撰寫組計：前者 5 行、後者 2 處；研究員原述 3／2）；無 `Users` 字樣（後者）；非 Secret | 低度；後者其餘內容未逐行讀（NOT VERIFIED） |
| `forward_test/picks.parquet` | 系統選股凍結，非持股；持股在 Google Sheets 不在 git | 低度（策略偏好） |

**結論**：本回合**無可確認的 Secret／個人資料外洩事件候選**，不需另案安全事件；低度路徑觀察與授權風險（§4.1）是否處理屬客戶決策。

---

## 5. 三方案比較

方案定義（**僅研究候選，不是施工授權**）：
- **A**：維持公開 repo 與現行保存方式；僅在確認授權允許後繼續使用（補標示、補授權證據）。
- **B**：repo 維持公開，受限制資料（H1／H2 及客戶指定者）改存非公開儲存。
- **C**：公開端僅保留經確認允許公開的衍生聚合，原始／來源列另存非公開位置。

| 維度 | A 維持現狀＋授權確認 | B 受限資料移非公開儲存 | C 公開端僅衍生聚合 |
|---|---|---|---|
| 授權合規風險 | 取決於授權答案；在答案未知前曝露面**最大且持續擴大**（每日新版） | 降低未來曝露；**歷史不變** | 降低最多（公開端不含來源列）；歷史仍不變 |
| 可追溯 | 最佳（git 即帳本） | 需另建版本／保留（非公開位置的歷史須自管） | 公開端可追溯到聚合；原始層追溯依非公開儲存 |
| PIT／回測 | 現有 `fetched_at`≠`release_date` 缺口不變 | 不改善 PIT；**搬移不得丟 `fetched_at` 與版本** | 同左；聚合檔更不利日後重算 |
| Git 歷史曝露 | 全部既有歷史維持公開 | 既有歷史維持公開；新增停止 | 同 B；另需決定是否改寫歷史（不可逆） |
| Streamlit Cloud 相容 | 現行已可用 | **風險高**：Cloud 讀 checkout 內檔案；非公開來源需新增認證讀取；本專案 Cloud 設定 NOT VERIFIED | 公開聚合仍可用；原始層只給 cron／離線使用，Cloud 影響最小 |
| 需改程式範圍 | 無（補標示屬畫面變更，須線框） | `src/data/sector_flow/reader.py`、`src/data/macro/macro_cache_reader.py`、`src/data/macro/macro_core.py`（durable）、`src/data/macro/macro_fwd_test_store.py`、`src/data/portfolio/forward_test_store.py`、`src/data/stock/fundamentals_snapshot_loader.py`；寫入端 `scripts/update_*.py`／`publish_data_pr.py`／`export_stock_db.py`；`pr-check` 及約 61 個測試檔含 `data_cache`；至少 3 個 service 鏈 | 最小：僅寫入端不再把來源列寫入公開 repo；讀取端（聚合）不變；`industry_raw.json` 無 runtime reader，**H1 可最小改動** |
| 可重用資源 | — | **Google Sheets**：設計為使用者持股／清單，非時間序列倉，配額與大檔未評估；**NAS**：現為即時抓取中繼，**無儲存端點**，可用性無保證；**`data` 分支**：同為公開（force-push 後舊 SHA 仍可能可達）；**Artifact**：受 repo 可見性管控、有保留期、Streamlit 不能直接讀；Actions cache 不適合 | 同 B，但僅需承載來源列（體量小，非 Cloud 讀取路徑） |
| 速度／維運／Token | 最低 | 高：新增儲存、認證、備份、失敗降級；需新 Secret（屬客戶授權） | 中：新增非公開落地位置與其保留規則 |
| 資料遺失與回復風險 | 低 | 中：搬移失誤＝丟歷史；**不可重建檔案**（`picks.parquet`、`signals.parquet`）須先備份 | 低～中：公開端不刪、僅新增；刪除任何公開檔須客戶拍板 |
| 可逆性 | 完全可逆 | 搬移可逆；歷史改寫**不可逆** | 停止新增可逆；歷史改寫不可逆 |

**RECOMMENDATION（非裁示）**：
1. 先取客戶／法律對 §7 三問的答案，**答案出來前只做最小風險面的「停止擴大」**（若客戶要求）；
2. 若須動手，優先 **C 的第一階段（H1 來源列不再寫入公開 repo）**——`industry_raw.json` 無 runtime reader，影響面最小、可逆；
3. **不推薦**在答案未知前採 B（改動面大、Cloud 風險高、歷史不變而收益有限）；不推薦先動歷史。

### 5.1 分階段遷移候選（**僅候選；每階段標明不可逆性與是否需客戶拍板；本稽核一階段都未執行**）

| 階段 | 內容 | 可逆？ | 需客戶拍板 | 前置 |
|---|---|---|---|---|
| 0 | 取得授權書面答案（§7 三問）；補 TWSE／TPEX 條款原文 | 可逆 | 是（提供原文／放行網域／法務意見） | — |
| 1 | 停止後續 cron 將 H1 來源列寫入公開 repo（保留衍生 `ticker_sector.json`），並備份既有檔 | 可逆（可還原寫入） | **是**（改 workflow／資料保存方式＝§8.4 step 4 範圍；本裁示明示不含） | 階段 0 | 
| 2 | 補來源標示（FinMind／顯名聲明） | 可逆 | 是（屬畫面變更→線框草稿先行） | 階段 0 |
| 3 | 受限資料改存非公開儲存＋讀取端改造（方案 B／C 完整版） | 搬移可逆；新 Secret／儲存屬新增 | **是**（Secrets、新儲存、Cloud 授權私人 repo 皆需授權） | 階段 0～1 |
| 4 | 改寫 Git 歷史／GitHub 端清理 | **不可逆** | **是（最高等級）**；另須客戶確認 fork／clone 不受控的殘餘 | 階段 0～3 | 
| 5 | 改 repo 可見性（公開→私人） | 可切換但**既有公開事實不可撤回**；Cloud 相容 NOT VERIFIED | **是** | 階段 0 |

---

## 6. NOT VERIFIED 清單

| # | 項目 |
|---|---|
| 1 | TWSE／TPEX／MOPS／data.gov.tw／央行／Yahoo 的條款**原文**與逐資料集適用性；OGDL 原頁；TWSE『交易資訊使用管理辦法』全文 |
| 2 | FinMind 官網即時版本；本專案的 FinMind **方案等級**、與來源機關的另行契約；本專案是否商業；Streamlit Cloud 是否公開／收費；repo 外是否另有授權證據 |
| 3 | 畫面是否顯示 FinMind／顯名聲明（僅 grep，未目視頁面） |
| 4 | Streamlit Cloud 實際部署分支、是否可授權私人 repo、Cloud 讀檔細節 |
| 5 | raw URL／`/commits/<sha>`／孤兒 commit／PR diff 折疊／fork 網路的實際可取得性（INFERENCE） |
| 6 | 歷史 Secret 掃描的窮盡性（研究員 regex、非專業掃描器、PR-only 物件未掃）；FINMIND_TOKEN 前綴是否曾進歷史 |
| 7 | `update_fundamentals`／`update_forward_test` 裸 push 是否被 branch protection 擋下（無權限讀）；`ui2-browser-gate` 是否 required check |
| 8 | `forward_test` 進場價與 `name` 的來源端點；`finmind_m1m2.parquet` 的 runtime 消費者；`industry_raw.json`／`signals.parquet` 是否另有動態路徑讀取（git grep 可能漏掃） |
| 9 | 其餘 553 張 PNG 內容；下游另 repo 對 `data` 分支的讀法；Google Sheets 配額與大檔適用性 |
| 10 | 本文全部結論的**第二組獨立複驗** |

---

## 7. 下一個需客戶裁示的事項

| # | 問題（商業語言） | 選項 | AI 推薦（非裁示） |
|---|---|---|---|
| 1 | 本專案是否屬商業使用？是否對外公開（Cloud 公開網址）？ | 客戶／法務判斷 | 交法務；AI 不下結論 |
| 2 | 公開 repo 內保留個股級來源列（H1）與 FinMind 市場級序列（H2）是否可接受？ | 可接受／不可接受／先取得授權再定 | 先取得 TWSE／TPEX／FinMind 授權的書面答案 |
| 3 | 是否授權 AI 另案提出階段 1（停止擴大）的最小施工方案（含 workflow 變更）？ | 授權另案提案／暫不 | 若客戶偏好降低曝露面，授權另案提案；**不含**歷史改寫 |
| 4 | 條款查證如何取得原文？ | 貼原文／放行沙箱網域／提供已配置 NAS 並授權唯讀 GET／法務 | 先取得原文 |
| 5 | 是否要求補來源標示？ | 要求／暫不 | 待 1～2；屬畫面變更須線框草稿 |
| 6 | 歷史改寫與改 repo 可見性（不可逆／影響 Cloud） | 現階段不討論／另案 | 現階段不討論 |

其餘 Gate（`DG-COV`、`DG-PIT`、`DG-LIC` 最終判斷、`DG-SCOPE`、`I1144-WIRING-GATE`、G-F2～G-F6、Digest A3、`market.health`、外資 L3、OneBrain runtime、UI2 接線）**全部維持 HOLD**；沉默不等於同意。

---

## 8. 抽查與降級紀錄（撰寫組自行實跑；**不等於第二組獨立複驗**）

| # | 項目 | 研究員原述 | 撰寫組抽查 | 處置 |
|---|---|---|---|---|
| 1 | `git ls-files data_cache` 檔數與大小 | 29 檔、約 2.0 MB（盤點）／2.30 MB（歷史證據） | **29 檔、2,298,741 B** | 檔數維持；**2.0 MB 更正為 2.30 MB** |
| 2 | 個股級 15 檔 | 15 | 讀 parquet／json 欄位：fundamentals 12、`picks`（51 檔）、`industry_raw`（3,174 碼）、`ticker_sector`（3,174 碼；55 種標籤）→ **15** | 維持 |
| 3 | repo 公開 | `private=false` | `gh api` → `private=false`、`visibility=public`、`fork=false`、`forks_count=0` | 維持 FACT |
| 4 | `industry_raw.json` 結構 | FinMind 4,381 列三欄；官方 1,996 碼四欄；rule 1,977／1,188／9 | **全部重現**（每碼 1～6 列分布 2094／981／76／19／3／1；官方 `endpoint` 與 `official_status` 上市 1,099／上櫃 897） | 維持；**更正先前「全部原始列」讀法**（§4.3） |
| 5 | 各檔列數／欄位 | 各 parquet 列數與欄位 | 逐檔重現（fundamentals 875～1,083 列×15 欄；`daily_net` 1,716×13；`signals` 47×25；`twii` 4,913×8 等）；`daily_net` 無股票代碼欄 | 維持 |
| 6 | PNG 數量與大小 | 554 張、約 67 MB（`du`） | **554 張、68,349,543 B（約 65 MiB）**；全在 `docs/vnext/`；目視 1 張確認含個股代碼與數字 | 大小改用位元組數；其餘未看＝NOT VERIFIED |
| 7 | FinMind 引文 | Q1～Q13 | 對 scratchpad 原檔逐句 grep 一致；Disclaimer／Pricing／PrivacyPolicy／CommercialUse **四頁對官方 raw 即時重抓，SHA-1 與證據檔完全相同** | 維持 PARTIALLY VERIFIED（來源＝官方 GitHub 原始檔，非官網即時頁） |
| 8 | TWSE／TPEX／data.gov.tw 可連性 | 皆不通 | 重測三主機連線碼 000 | 維持 NOT VERIFIED |
| 9 | Git 歷史：全 refs 4,673 commit、main 2,256、PR head 1,133、branches 12 | 同 | `rev-list --all`／`for-each-ref` **重現** | 維持 |
| 10 | 歷史 blob：1,036／80.56 MB／pack 4.86 MB | 含 `stock.db`、`etf_managers` | `data_cache` 排除 `.gitkeep` 即 1,036／約 80.0 MB；重打包約 4.6 MB；含二者 1,054／約 80.9 MB | **降級**：改寫為「1,036 blob／約 80.0 MB（僅 `data_cache`）」，原 80.56 MB 與 4.86 MB 不採為已驗證 |
| 11 | `industry_raw` 24 版 20.91 MB；`twii` 155 版 | 同 | **重現**（24／20.91 MB；branches 可達 twii 155，含 PR head 156） | 維持 |
| 12 | untrack／重新追蹤日期 | 2026-06-28／07-11 | `908bacab` 2026-06-28、`89ddd17d` 2026-07-11 **重現**；`industry_raw` 首次 2026-10-12 重現 | 維持 |
| 13 | 僅 PR 可達 blob；main data_cache commit 數 | 5；347（bot 336） | 重算 **7**；**335（bot 329）** | **降級**：不採研究員數字，差異未釐清 |
| 14 | 13 個 PR 動到 `data_cache` | 同 | **未抽查** | 研究員原述 |
| 15 | workflow 寫回方式（三支 PR、兩支裸 push、`export_db` force-push） | 同 | 讀 workflow：重現；#1124～#1126 `gh api` 確認 open | 維持；裸 push 是否被擋＝NOT VERIFIED |
| 16 | `industry_raw` 無 runtime reader | 同 | `reader.py` 無此名；僅 `market_close_fetcher`（cron 路徑）等引用 | 維持（grep，動態路徑 NOT VERIFIED） |
| 17 | Secret regex 0 命中 | 同 | 工作樹 29 檔自行重跑 regex **0 命中**；歷史掃描**未重做** | 維持（工作樹）；歷史標研究員原述 |
| 18 | 本機路徑觀察 | 3 行／2 處 | 前者 5 行（降級原述）、後者 2 處 | 以撰寫組計數為準，仍為低度 |
| 19 | 「無 Secret／個資事件」「FinMind 條款不替代 TWSE／TPEX」等全稱句 | — | **未做第二組獨立複驗** | 維持「單組、未複驗」 |
| 20 | 歷史 clone 來源 | 研究員 bare clone＋`refs/pull` | 本回合**重用該 bare clone 計算**，未重新對遠端 clone | 數字以 clone 當時為準；遠端之後的新 commit 不含 |

**未抽查**：13 個 PR 的逐一內容、各分支「資料版本可達數」表、61 個測試檔清單、8 個讀取模組的逐檔失敗行為、其餘 553 張 PNG、Streamlit Cloud 設定。

### 8.1 本文不得被讀成

已取得任何資料的再散布授權；已確認違規；「FinMind 條款涵蓋 TWSE／TPEX」；「公開 repo 無問題」或「公開 repo 構成違規」；已授權遷移、刪檔、改歷史、改 repo 可見性；已關閉任何 Gate。
