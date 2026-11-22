# FinMind 融資（`TaiwanStockTotalMarginPurchaseShortSale`）DG-LIC 三層證據表與 I1140 量綱事實摘要 — 2026-11-22

> **EVIDENCE INDEX ONLY｜NOT A GATE DECISION**
>
> | 項 | 內容 |
> |---|---|
> | 日期／基準 | 2026-11-22｜`origin/main` `e2068a68` |
> | 作者 | A（Claude，作者）；**單組作者結論，未經非作者 QA 前不得升格**（`CLAUDE.md` §-2 規則 6） |
> | 性質 | 證據索引：把 repo 內**既有**文件／程式註解／測試已記載的證據，對到 DG-LIC 三層（定義見 `docs/DECISIONS.md` DEC-205）。**不是裁示、不是授權、不是法律意見。** |
> | 不解除 | `DG-LIC`、`DG-PIT`、`DG-COV`、`DG-SCOPE`、`I1144-WIRING-GATE` 全部維持原狀 |
> | 不授權 | 接線、取數、發布、再散布、改 workflow、改資料、改程式 |
> | 本批限制 | 沙箱連不到官方站台，**未重新取得任何條款原文**；所有條款句為 repo 內既有文件的**二次記載**。本批**未讀取、未引用** `data_cache/finmind_margin.parquet` 的任何數值。 |

---

## 1. 範圍與非目的

| 項 | 說明 |
|---|---|
| 範圍 | **一個 dataset**：FinMind `TaiwanStockTotalMarginPurchaseShortSale`；落地檔 `data_cache/finmind_margin.parquet`；L3 讀取層 `src/services/margin_fact_service.py` |
| 不含 | 外資（`finmind_inst`）、季報／財報、TWII／`twii_ohlcv`、板塊資金流、央行 M1B/M2、PMI |
| 非目的 | 不判斷任何用途合法或違法；不判斷「再散布」「對外介面」「原始資料」等詞是否涵蓋本專案行為；不提出刪檔、改架構、改可見性的建議；不做公開／法務結論 |
| 證據等級用語 | **HAVE**＝repo 內有可回查的記載（記載存在 ≠ 適用 ≠ 已取得授權）｜**PARTIAL**＝有記載但有明列缺口｜**MISSING**＝repo 內查無｜**NOT VERIFIED**＝未驗證，不得當前提 |
| DEC-205 對 DG-LIC＝A 的射程（轉述） | 逐資料集三層分列；**不得以使用者承擔風險取代授權**；**不得拿 A 層證據宣稱 C 層獲核准**；既有公開 repo 的 MOPS／FinMind／TWSE／TPEX／Yahoo 歷史資料疑慮，**不因另一份開放資料集標有開放條款而自動解除** |

**三層定義（引 DEC-205「DG-LIC＝A 的限定射程」）**：**A**＝條款可回查；**B**＝條款適用於**實際使用的資料資源／下載路徑**；**C**＝對本專案**公開／儲存／顯名義務**的適用與符合。

**出處縮寫**（檔名＋章節標題；本文不寫行號）：

| 縮寫 | 檔案與章節 |
|---|---|
| SUPP | `docs/vnext/UI2_RUNTIME_PREGATE_EVIDENCE_SUPPLEMENT_2026-11-11.md`：§1.2／§1.3、§3、§11.2「FinMind 條款原文」（Q1～Q13）、§11.3.2「FinMind」、§11.4「repo 公開與 `data_cache` 落地面」 |
| AUDIT | `docs/vnext/PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT_2026-11-11.md`：§2「來源授權矩陣」、§2.1、§2.2、§3「Git 歷史曝露分析」 |
| DPE3 | `docs/vnext/DPE3_TERMS_AND_DPE6_CLOUD_CONFIG_EVIDENCE_2026-11-13.md`：§1.2「現有條款證據」、§1.3「`DG-LIC` 現況」、§1.4「分類」、§2.3、§3 |
| SHEET | `docs/vnext/DATA_WIRING_GATE_DECISION_SHEET_2026-11-12.md`：決策 1～5 與附錄 |
| DEC-n | `docs/DECISIONS.md` 對應條號標題 |
| BACKLOG | `docs/BACKLOG.md`（以列 ID 或段標題標示） |

---

## 2. 三層證據表（核心）

> 條款欄只做簡短轉述；Q 編號沿用 SUPP §11.2。FinMind 條款記載版本日期為 **2026-10-31**，來源為官方 GitHub Pages 原始檔，**非官網即時頁**。

### 2.1 A 層：條款可回查

| # | 條款／事實（簡短轉述） | 現有證據出處 | 狀態 | 缺口 | 誰能提供 |
|---|---|---|---|---|---|
| A1 | FinMind 授權**不含**將資料對外再散布、轉售，或建置實質等同其服務的鏡像 | SUPP §11.2 Q4；AUDIT §2.1 Q4 | PARTIAL | 官網即時頁是否與 2026-10-31 版相同＝NOT VERIFIED；「再散布」是否涵蓋本專案行為＝法律判斷（AUDIT 與 SUPP 均明寫不下結論） | 客戶（貼官網現行頁）／FinMind／法務 |
| A2 | 使用者若需**對外公開、再散布或提供第三方**，應自行向**原資料來源機關**取得其要求的授權；此類授權「非 FinMind 所能授予」 | SUPP §11.2 Q5；SHEET 決策 4 §2 | PARTIAL | 同 A1；原資料來源機關是誰＝見 A9 | 客戶／原機關／法務 |
| A3 | 資料用於對外用途時，須依授權條款以適當方式**標示原資料提供機關**；其餘資料依各來源機關公開揭露或開放資料規範使用 | SUPP §11.2 Q1、Q3 | PARTIAL | 何謂「適當方式」未見；融資的原提供機關見 A9 | FinMind／法務 |
| A4 | 使用條款：不得將**即時資料**直接呈現於 web、App 等**對外介面**，亦不得對外再散布**原始資料**或建立鏡像 | SUPP §11.2 Q8；AUDIT §2.1 Q8；BACKLOG `DGLIC-PER-DATASET-MATRIX` 詳表 ③b（finmind_margin 列標「同上」＝「條款未涵蓋；『即時資料』限制的適用性 NOT VERIFIED」） | PARTIAL | 「即時」「對外介面」「原始資料」**皆未定義**。融資是否屬「即時」：SUPP §11.3.2 對外資列註記「本資料非即時分類」、融資列標「同上」——該註記是撰寫組判斷，**不是條款原文**，一律視為 **INFERENCE**；另 AUDIT §4.1 H2 記「『市場級單位換算後序列』是否仍屬原始資料**條款未定義**」（既有文件分級，見 C2） | FinMind／法務 |
| A5 | 方案表：Free／Backer／Sponsor 限**非商業**；商業用途不在內；「再散布原始資料、建立鏡像 API」各方案（含 Sponsor Pro）皆不含；須標示資料來源「FinMind」 | SUPP §11.2 Q9、Q10；AUDIT §2.1 Q9、Q10 | PARTIAL | 方案表為官方 GitHub Pages 記載；本專案方案等級見 B4 | 客戶／FinMind |
| A6 | Apache-2.0 只涵蓋 FinMind SDK 程式碼，**不是資料授權**；README 另稱內容用於教育、非商業 | SUPP §11.2 Q11 | HAVE（字面）；不適用於資料授權 | 不得拿 Apache-2.0 當資料授權依據 | — |
| A7 | 融資資料集說明頁：自述資料區間與更新時間；**頁內未見額外限制句**（「對外展示須自行向來源機關取得授權」一句僅出現在券商分點類頁，本專案未使用） | SUPP §11.2 Q12、§11.3.2「`TaiwanStockTotalMarginPurchaseShortSale`」列 | PARTIAL | 「未見」屬單組的不存在性判斷；FinMind 自述更新時間**不是**官方公布時點 | QA 複驗／FinMind |
| A8 | FinMind 自述其合法使用基礎含「與資料來源機關另行簽訂之資訊使用契約」 | SUPP §11.2 末段「FinMind 自述（非證據）」；AUDIT §2.1 | NOT VERIFIED | 契約內容、是否涵蓋本專案轉載，repo 內零證據；**不得推論本專案受其保護** | FinMind |
| A9 | 融資資料集的**實際來源機關**及其條款原文（含 TWSE『交易資訊使用管理辦法』全文）；二手線索見 A12 | BACKLOG「2026-11-14｜決策閉環與 Open Items 對帳」之 `DGLIC-PER-DATASET-MATRIX` 列（稱來源機關「可能 TWSE，INFERENCE」）；DPE3 §1.2「TWSE」列；SUPP §11.3.1（TWSE／TPEX／data.gov.tw 全部無原文，並含 WebSearch 二手線索） | MISSING | 資料集頁未載明來源機關；來源機關條款原文 repo 內**零頁** | 客戶（貼原文）／FinMind（書面答覆歸屬）／原機關／法務 |
| A10 | OGDL-Taiwan-1.0（政府資料開放授權條款）：僅有 SPDX 轉錄本，非 data.gov.tw 原頁 | SUPP §11.2 Q13 | NOT VERIFIED（對融資是否適用） | 融資資料集是否掛 data.gov.tw、是否適用 OGDL，無證據；**不得預設套用** | 客戶／法務 |
| A11 | 條款版本：2026-10-31 版之後是否改版；官網即時頁是否相同 | SUPP §11.2 開頭註記；DPE3 §3 | NOT VERIFIED | 官網在沙箱不可達 | 客戶／FinMind |
| A12 | **二手線索（非條款原文）**：(a) FinMind 轉述使用者須遵守 TWSE『交易資訊使用管理辦法』等規定（SUPP Q2）；(b) WebSearch 摘要稱 TWSE 網站條款禁止未經同意以自動化裝置下載網站資料（DPE3 §1.2 與 SUPP §11.3.1 均標 INFERENCE，「不得據以下結論」）。若屬實，與 B 層 cron 定期抓取行為相關（見 B3） | SUPP §11.2 Q2、§11.3.1「WebSearch 線索」；DPE3 §1.2「TWSE」列 | NOT VERIFIED（二手線索） | 管理辦法全文與網站條款原文皆未取得；融資的實際來源機關是否為 TWSE 亦未證實（A9）；**不得以 FinMind 通則回推 TWSE 授權**（SUPP §11.3.1 原話） | 客戶（貼原文）／法務 |

### 2.2 B 層：條款適用於**所用資料路徑**

| # | 條款／事實（簡短轉述） | 現有證據出處 | 狀態 | 缺口 | 誰能提供 |
|---|---|---|---|---|---|
| B1 | 所用 dataset 名與口徑：彙總版長格式，金額列 `MarginPurchaseMoney`（單位元）；cache 欄 `margin_balance` 契約為元 | `shared/margin_schema.py` 模組檔頭與 `MARGIN_DATASET`、`MARGIN_MONEY_ROW_NAME` | HAVE（程式事實） | — | — |
| B2 | 取數路徑：cron `scripts/update_macro_history.py::fetch_finmind_margin` → `_finmind_get`，**直連 FinMind API（檔頭自陳不走 NAS／proxy chain）**；憑證走 HTTP header、由 workflow secret `FINMIND_TOKEN` 供應。**本批未讀 Secrets** | `scripts/update_macro_history.py` 模組檔頭、`_finmind_get` docstring；`.github/workflows/update_macro_history.yml` | HAVE（程式事實） | 直連事實不等於條款允許或禁止（條款沒有針對該路徑表態＝見 B3） | — |
| B3 | 條款是否有針對**「唯讀 API 比對」**的專門條文——DPE3 原文用語為「未見針對『唯讀 API 比對』的專門條文」。⚠️ **註記：「cron 定期抓取（本專案 B2 的實際行為）」與「唯讀對帳」是不同行為**（DPE3 §1.3「概念落差」：`DG-LIC` 原始問題是呈現／再散布，DPE-3 問的是唯讀對帳）；本列**沒有**證據涵蓋「cron 定期抓取」是否有專門條文 | DPE3 §1.2「FinMind」列；DPE3 §1.3「概念落差」段；DPE3 §3「NOT VERIFIED 與限制總表」 | PARTIAL | 單組掃描（INFERENCE）；**未見 ≠ 不存在**；「定期程式化抓取」本身有無條款表態，repo 內無任何文件查過 | QA 複驗／FinMind |
| B4 | 本專案所持 FinMind 方案等級（Free／Backer／Sponsor／Sponsor Pro） | SUPP §11.4 倒數列；AUDIT §2.2 | NOT VERIFIED | repo 內僅見 secret 名 `FINMIND_TOKEN`，不可判定 | 客戶 |
| B5 | 本專案是否屬**商業**使用（`I1144-LIC-THREE-QUESTIONS` 第 1 問） | BACKLOG「Issue #1144」段 `I1144-LIC-THREE-QUESTIONS`；DPE3 §1.3「`I1144-LIC-THREE-QUESTIONS`」列（「repo 內查無客戶回答」） | MISSING | 客戶尚無回覆記載 | 客戶／法務 |
| B6 | 融資資料集涵蓋範圍（是否含上櫃；能否稱「全市場」） | SHEET 決策 1 §2；BACKLOG `I1140-MARGIN-SOURCE-TEXT`；DEC-193 | NOT VERIFIED | 決定「來源機關是誰、資料口徑是否等同全市場」 | FinMind 官方說明／客戶 |
| B7 | 來源歸屬記載衝突：`DATASTATION.md` 資料來源表「融資餘額」列記為 TWSE OpenAPI `MI_MARGN`；cache 實際取自 FinMind | `DATASTATION.md` 融資餘額列；DEC-193（稱「DATASTATION／finmind provenance 衝突仍 OPEN」）；BACKLOG「2026-11-18 I1140-MARGIN-SOURCE-TEXT」段 | 衝突 OPEN | 哪份記載代表現行取數，需核對（本文不裁定） | 專案 AI 另案核對（需任務觸發，§-1）／客戶 |
| B8 | **另一條取用路徑（不在本表範圍）**：舊 UI 即時 fallback `src/data/daily/daily_data_fetchers.py::fetch_margin_balance`，依 docstring 為 FinMind → MI_MARGN → HiStock → Goodinfo → Yahoo → 鉅亨網 | 該函式 docstring；`tests/test_pr_n5_fetch_margin.py` 檔頭；DPE3 §1.4(b)（其餘 T3 站台零條款證據） | OUT OF SCOPE／NOT VERIFIED | 本表只覆蓋「cache 路徑」；其餘站台條款零證據 | — |

### 2.3 C 層：公開、儲存、顯名義務

| # | 條款／事實（簡短轉述） | 現有證據出處 | 狀態 | 缺口 | 誰能提供 |
|---|---|---|---|---|---|
| C1 | repo 公開性：**至少** SUPP §11.4（11-11；稱 `gh api` 查得 `private=false`，標 VERIFIED）、AUDIT §0／§3（11-11）、SHEET 決策 4 §2、DEC-171（11-11）稱公開；BACKLOG `DGLIC-PER-DATASET-MATRIX` 詳表與 DEC-184 (三)（**11-14**）稱「repo 公開性為派工提示語陳述，工具無法獨立確認＝NOT VERIFIED」 | SUPP §11.4；AUDIT；SHEET 決策 4 §2；DEC-171；BACKLOG 詳表「整體（FACT）」段；DEC-184 (三) | PARTIAL（**既有文件措辭不一致，且時點不同：11-11 vs 11-14**） | 本批無網路，**未重驗**；現時可見性需有網路環境重查 | QA（有網路環境）／客戶 |
| C2 | 公開 repo **追蹤**該 parquet：本批實跑 `git ls-files data_cache` 列出 `data_cache/finmind_margin.parquet`（僅檔名，未讀內容）；`.gitignore` 有該檔的例外條目。**既有文件分級（轉述，不下結論）**：(1) AUDIT §4.1 **H2**（高優先級）把 `finmind_margin.parquet`（連同 `finmind_inst.parquet`）列為「可能與明文授權限制衝突；建議交客戶／法律裁示」，列高理由為：條款禁再散布原始資料、「市場級單位換算後序列」是否仍屬原始資料**條款未定義**、須標示「FinMind」且 UI 標示現況未見，並記該檔歷史有 **108 版**（git 歷史；AUDIT 自述，本機淺層複製無法複驗）；AUDIT §4 前言明寫「這是優先序，不是違規認定，不下法律定論」。(2) BACKLOG `DGLIC-PER-DATASET-MATRIX` 詳表（finmind_margin 列「同上」＝繼承 finmind_inst 列）：**③a 公開 GitHub 儲存**＝「字面禁止對外再散布（條款未提 GitHub／儲存）；需向原來源機關取得授權」；**③c 衍生／聚合**＝「條款未涵蓋（不等於允許）」，且該表對融資列註記「為選取欄位，非計算聚合」 | 本批 `git ls-files`；`.gitignore`；AUDIT §4.1 H2；BACKLOG 詳表 ③a／③c；SUPP §11.4 | HAVE（追蹤事實）／既有文件分級＝高優先（非認定） | 是否構成「再散布原始資料」＝**法律判斷**，AUDIT、SUPP §11.4 皆明寫不下結論；「條款未提 GitHub／儲存」＝條款沉默，**不等於允許** | 客戶／法務 |
| C3 | Git 歷史：`data_cache` 歷史版本留存於 git 歷史，「停止追蹤」不減少已公開歷史 | AUDIT §3；DEC-171 | PARTIAL（前輪結論；歷史數字本機無法複驗） | 本機為淺層複製，歷史數字無法複驗（SHEET 決策 4 §2 自陳）；本文**不引用**其數字 | — |
| C4 | **非 L3 的既存消費面**（本批 grep 新發現，單組）：(a) 舊 UI `src/ui/tabs/tab_macro_v2.py` 的 `margin` 走勢卡（卡片說明「2006 迄今」）經 `macro_v2_service.get_chart_series` → `macro_cache_reader.load_v2_chart_series` 讀本 cache；(b) `src/ui/views/page_today.py` 的方向燈載入器（`_LAMP_DIRECTION_LOADERS`）讀同一序列；(c) 舊 `tab_macro` 另經 `src/services/macro_fetch_orchestrator.py` 呼叫 `fetch_margin_balance`（B8 的即時 fallback，FinMind 為第一源）進舊 UI——**非 cache 路徑**，此處僅註明存在，**清單未窮舉**。export_db 見 C4-export | 以上各檔（grep 見 §7） | HAVE（程式事實） | 這些畫面**是否在 Cloud 實際渲染**＝**NOT VERIFIED**；是否屬 DG-LIC「呈現／再散布」範圍＝待客戶／法務判斷。與 I1140 的交叉註記見 §3.1 | 客戶（Cloud 實況）／法務 |
| C4-export | **export_db 獨立面**：`scripts/export_stock_db.py` 把 `margin` 表（讀 `finmind_margin.parquet`，帶 §3.2 sanity gate）寫入 SQLite stock.db；`.github/workflows/export_db.yml` 檔頭自述每日以 `git push -f` 發布到本 repo `data` 分支，**供下游使用**；`export_stock_db.py` 檔頭點名一個下游 repo（**檔頭自述，未驗證**；本文不抄名稱）。AUDIT §3.3 記 export_db 為「每日 21:00、`git push -f origin _pub:data`、`data` 分支**同為公開**」，並把「下游另 repo 對 `data` 分支的讀法」列 NOT VERIFIED。**export_db 不在 DEC-185 暫停的三支（`update_macro_history`／`update_sector_flow`／`update_macro_forward_test`）之內**；`docs/DECISIONS.md`、`docs/BACKLOG.md` 對 `export_db` 的 grep 為 0 命中＝**查無暫停記載（單組 grep）** | `scripts/export_stock_db.py` 檔頭；`.github/workflows/export_db.yml` 檔頭；AUDIT §3.3「資料發布機制」、§6；DEC-185；本批 grep | HAVE（檔頭自述與 AUDIT 記載）；**export_db 現況＝NOT VERIFIED** | 是否啟用、`data` 分支現況、下游實際是誰與如何使用＝未驗；**本文不下「構成再散布」的結論**（法律判斷）；此面與 `update_macro_history` 的暫停無關，暫停該產線不代表此面停止 | 客戶（實況）／法務 |
| C5 | L3 `margin_fact_service`：檔頭自陳**目前 0 production caller**；測試 `test_scope_guard_not_wired_to_ui_or_real_feed` 守衛；本批重跑 grep 亦無 `src`／`app*.py`／`shared`／`scripts` 引用 | `src/services/margin_fact_service.py` 檔頭；`tests/test_margin_fact_service.py`；DEC-193；本批 grep | HAVE | **只指 L3 service 與 UI2 路徑**，不涵蓋 C4 的既存面 | — |
| C6 | 顯名：Q3／Q9／Q10 要求標示「FinMind」／原資料提供機關。repo 現況：(a) DEC-193 把 L3 `MARGIN_SOURCE_TEXT` 改為中性字樣，**不含「FinMind」**（該決議是移除未證實宣稱，**不是**處理顯名義務）；(b) SUPP §11.4 稱 grep `芬麥` 0 命中、未目視頁面；(c) 本批 grep：`tab_macro_v2.py` 無「FinMind」字串，其 `margin` 卡說明字串不含來源名；`page_today.py` 的「FinMind」僅見於說明文字（docstring） | DEC-193；SUPP §11.4；本批 grep | L3 路徑 MISSING；其他 UI 畫面 NOT VERIFIED | 未目視實際畫面；間接路徑（registry、資料診斷頁）未查。**日後若接線，顯名字樣與位置屬 UI 文字變更，須先出文字線框**（`CLAUDE.md` §-1.5.D §03-2 ①）；**另注意：既有測試 `tests/test_margin_fact_service.py::test_source_text_has_no_unverified_claims` 明禁 `MARGIN_SOURCE_TEXT` 含「FinMind」字樣——日後若要在該字串顯名，會與此守衛衝突，須有意識的決策（含守衛如何同步），不是順手改字串** | 客戶（線框拍板）／法務（必要字樣） |
| C7 | repo 內是否有授權函、書面同意、使用契約、方案憑證 | AUDIT §2.2 第一列；DPE3 §1.2 末列 | MISSING（單組 grep；不證明 repo 外不存在） | — | 客戶／FinMind |
| C8 | Q5 所指「向原資料來源機關取得對外公開授權」：本專案是否已取得 | BACKLOG `DGLIC-PER-DATASET-MATRIX`「缺的最小證據」：finmind_margin＝FinMind 對來源機關歸屬的書面答覆＋來源機關授權 | MISSING | 同上 | 客戶／FinMind／原機關 |
| C9 | Streamlit Cloud 公開網址、是否收費 | SUPP §11.4 末列；DPE3 §2.3、§3 | NOT VERIFIED | repo 內無 Cloud 設定證據 | 客戶 |
| C10 | 產線（定期取用／發布）：`update_macro_history.yml` 為本 cache 產線；2026-11-14 起 `disabled_manually`；恢復條件**未裁示** | DEC-185；BACKLOG `WORKFLOW-PAUSE-3-DATA`（HOLD） | HAVE（2026-11-14 時點記載） | 此後 Actions 實況**未重驗**（本批無網路） | 客戶（恢復與否）／QA（有網路環境重查） |
| C11 | 既有整體分級：DEC-184 (三) 記 #1124 五檔（含 `finmind_margin.parquet`）「**無任何一檔有『明示允許』的逐字依據**；DG-LIC／DPE-3 證據不足，維持未解除」；其中 `finmind_margin` 在 main 上為**既有狀態，不是已放行** | DEC-184 (三)；BACKLOG `DGLIC-PER-DATASET-MATRIX` 詳表「整體（FACT）」 | HAVE（2026-11-14 時點記載；兩組，非法律結論） | 這是「沒有明示允許的證據」，**不是**「有明示禁止的認定」；兩者皆非法律結論 | — |

---

## 3. I1140-MARGIN-UNIT-MIX：量綱／單位**既有事實**摘要

> 只引 repo 內既有記載；**本批未對真 parquet 做任何新分析、未執行任何測試**。

### 3.1 現況描述（BACKLOG 與決策單）

| 項 | 既有記載 | 出處 |
|---|---|---|
| 缺口本體 | 融資歷史**內部單位混用僅驗最新點**（FACT）；對應 v3 §02「資料疑義」逐列旗標缺口；觸發條件＝取用歷史序列／趨勢前 | BACKLOG「Issue #1140｜三批完成登記與新缺口」段 `I1140-MARGIN-UNIT-MIX` 列 |
| 屬性 | 資料品質議題，**非授權議題**。⚠️ **用語差異**：SUPP §3 N-14 寫的是「元／百萬元／億」單位混用；`shared/margin_schema.py` 與 B3 事故記載的是「**張／元**」混口徑——兩者**不同**，本文不把它們視為同一件事，亦未驗證 N-14 所稱的百萬元混用是否另外存在 | SUPP §11.3.2 融資列「未確認」欄；SUPP §3 N-14；`shared/margin_schema.py` 檔頭 |
| 條件式 | 只顯示最新值時不觸發；一旦要做歷史序列即觸發 | SHEET 決策 5 §2「B」表「歷史融資單位混用」列；SHEET 決策 3 附加條件 X |
| 交叉註記（INFERENCE） | I1140 的觸發條件為「取用歷史序列／趨勢前」。**既存路徑可能已成立該條件**：舊 UI `tab_macro_v2` margin 卡自述「日資料 2006 迄今」、`export_stock_db.py` 的 sanity gate 檢查**全列**（檔頭：「全列須 ∈[500,10000]億，否則整表略過」）。這是依程式註解的推論，**NOT VERIFIED**（未驗實際取用方式與歷史列內容；本批刻意未讀 parquet）；**不構成** I1140 已被觸發或已解的認定 | `src/ui/tabs/tab_macro_v2.py` margin 卡說明；`scripts/export_stock_db.py` 檔頭；BACKLOG `I1140-MARGIN-UNIT-MIX` |

### 3.2 程式註解與憲法所載的單位／口徑事實

| 項 | 內容 | 出處 |
|---|---|---|
| 原始口徑 | FinMind 該 dataset 為彙總版**長格式**：同一天多列，靠 `name` 分口徑；金額列單位**元**，張數列單位**張**（量級差距大，永不當金額） | `shared/margin_schema.py` 模組檔頭 |
| B3 事故 | 舊 cron 欄位偵測照個股寬格式寫，造成序列「張／元」混口徑；檔頭另記載當時的列數與比例（**本文不重述**）；修復＝選列／選欄／單位判定抽成 L0 SSOT 純函式，cron 與即時路徑共用 | `shared/margin_schema.py` 檔頭；`tests/test_b3_margin_schema.py` 檔頭「事故回顧」 |
| 單位鐵則 | 金額列 `TodayBalance`＝元，÷`TWD_PER_YI`（1e8）＝億；parquet `margin_balance` 欄契約＝元；L1 reader 輸出億元；L3 `margin_fact_service` 不再換算、不 round | `shared/margin_schema.py`；`macro_cache_reader.load_v2_chart_series` docstring；`margin_fact_service` 檔頭 |
| 昨日欄排除 | 採用昨日餘額欄會讓整條序列日期錯位一天；`is_today_balance_col` docstring 將其歸為 §2.3 PIT 類問題（原文措辭見該 docstring），故一律排除 | `shared/margin_schema.py::is_today_balance_col` docstring |
| sanity 區間 | 開區間（下限 500、上限 10000，單位億；端點本身拒收），常數 `MARGIN_BALANCE_SANITY_MIN_YI`／`MARGIN_BALANCE_SANITY_MAX_YI`；函式 `margin_sanity_ok`、`margin_money_to_yi`、逐列 `margin_twd_sanity_mask` | `shared/signal_thresholds.py`；`shared/margin_schema.py`；`margin_fact_service` 判定順序第 4 項 |
| L3 範圍 | 只判**最新一點**＋`.attrs`；只回事實不下判斷；`source` 為描述性常數，**不宣稱列級 provenance** | `src/services/margin_fact_service.py` 檔頭 |
| 憲法規則 | `CLAUDE.md` §4.1 單位陷阱表列「元 vs 百萬元 vs 億」；§1.A 第 2 點：融資餘額歷史單位混用區間須強制加註「資料疑義」，**不得靜默通過，也不得自行猜單位換算掉** | `CLAUDE.md` §4.1、§1.A |
| 他路徑單位不同 | 舊即時 fallback 中 TWSE `MI_MARGN` 為仟元÷100,000＝億（與 cache 路徑的元÷1e8 不同） | `tests/test_pr_n5_fetch_margin.py` 檔頭 |

### 3.3 既有測試（只列名稱與用途；本批**未執行**）

| 測試檔 | 既有案例（節選）與用途 |
|---|---|
| `tests/test_b3_margin_schema.py` | 長格式只選金額列與當日欄；張數列、昨日欄不被選；中文 name 變體；寬格式相容且拒絕寬鬆 fallback；sanity 開區間邊界；逐列 mask 標出張數列；cron 在 sanity 違反時 raise 且不寫檔；export gate 拒收混口徑與退化資料、髒表略過整表；AST 守衛三個消費者引用同一 SSOT |
| `tests/test_margin_fact_service.py` | 判定順序 1～9；reason→state 單一對照；sanity 邊界與 ×1e3 位移、張數量級被拒；未來日；`as_of` 對帳；stale 邊界；重複日期 fail closed；中性字樣字面釘住且禁「全市場／每日更新／FinMind」；範圍守衛（未接 UI／`real_feed`）。**另有兩個讀真 cache 的案例**（`test_real_cache_pinned_snapshot`、`test_real_cache_crosscheck_with_independent_computation`）：本文不引其斷言值 |
| `tests/test_h1_margin_label_and_registry.py` | 融資卡 label 隨 SSOT 門檻常數變動（label 不手打門檻） |
| `tests/test_pr_n5_fetch_margin.py` | 即時 fallback 函式簽章與 re-export 守衛（無 I/O） |

> ### 結語（必讀）
> **sanity／單位檢查通過 ≠ DG-LIC／DG-PIT／DG-COV 通過；不證明歷史口徑正確。**
> 上列檢查（最新點 sanity、逐列 mask、cron 守門）是**資料品質防線**；歷史既有列是否已逐列校正，本文**未驗**，`I1140-MARGIN-UNIT-MIX` 仍為 open。

---

## 4. 其他 Gate 狀態一覽（皆為既有記載；本文不改任何一項）

| Gate／項 | 既有記載的狀態 | 出處 | 備註 |
|---|---|---|---|
| **DG-PIT** | DEC-205：**B＋X**——僅顯示最新值的**資料日**；`fetched_at` 僅內部稽核證據，**絕不**作官方公布日；**不得**拿缺 `published_at` 的資料做歷史序列、比較、回測、訊號 | DEC-205；SHEET 決策 3 | DEC-205 對個股季報 MVP 的原句為「這是限制可呈現範圍，不是證明季度 PIT 已通過」，本文只借其精神：B＋X 限制可呈現範圍，**不證明融資 PIT 通過**。融資 cache 只有資料日與抓取時間，**無官方公布時間欄、不保存修訂版本**（SUPP §1.3） |
| **DG-COV** | 決策單：**只接融資不需回答 DG-COV**；「只接融資的路線不受影響」 | SHEET 決策 1 §2（標 INFERENCE）；決策 2 §6 | 此為**條件式**：前提是 DG-SCOPE 選到「只接融資」，而 DG-SCOPE 尚無客戶回覆（下列） |
| **DG-SCOPE** | HOLD；決策單僅有 **AI 推薦**（若要前進，第一步為只接融資），**非客戶裁示** | SHEET 決策 1 §4（RECOMMENDATION）；BACKLOG 各 Gate 清單 | 單組讀 DEC-205 原文：其射程僅 DG-PIT 與 DG-LIC，未含 DG-SCOPE；本批 grep DECISIONS／BACKLOG 命中處**均為「仍 HOLD」類記載**，未見客戶 DG-SCOPE 回覆（單組，QA 請自行通讀） |
| **I1144-WIRING-GATE** | **仍未授權**；DEC-205 明寫「不授權正式資料發布或 UI2 接線」；前置研究完成 ≠ 接線授權 | BACKLOG「Issue #1144」段 `I1144-WIRING-GATE`；DEC-205 | 融資在 UI2／`real_feed` 仍 0 引用（DEC-193；§2.3 C5） |
| **producer（產線）** | DEC-185：`update_macro_history.yml` 等三支為 `disabled_manually`（2026-11-14）；恢復條件未裁示 | DEC-185；BACKLOG `WORKFLOW-PAUSE-3-DATA` | **Actions 現況＝NOT VERIFIED**（本批無網路）。⚠️ **`export_db` 不在 DEC-185 暫停的三支內**（C4-export；DECISIONS／BACKLOG 查無暫停記載＝單組 grep，現況 NOT VERIFIED） |
| **#1124** | HOLD（含 `finmind_margin` 在內的五檔整包資料 PR；`DG-LIC`／`DG-PIT` 未解除） | BACKLOG「九個 Open 項目對帳」之 PR #1124 列；`DGLIC-PER-DATASET-MATRIX` | 此為 2026-11-14 時點記載；GitHub 現況**未重驗** |

---

## 5. 待客戶／法務判斷清單（不下任何法律結論）

| # | 待判斷事項（商業語言） | 提供者 | AI 不得代答 | 關聯列 |
|---|---|---|---|---|
| 1 | ⚠️ **既存面（含 export_db）是否納入審查範圍**：舊 `tab_macro_v2` 走勢卡、`page_today` 方向燈、舊 `tab_macro` 即時路徑，以及 **`export_db` 每日發布到公開 `data` 分支供下游使用（不在 DEC-185 暫停三支內）**——這些面與「L3 零引用」是兩件事；Cloud 是否公開、是否收費 | 客戶 | **是**（範圍取捨屬客戶；AI 只能補盤點事實） | C4、C4-export、C9 |
| 2 | 公開 repo 追蹤這份融資 parquet（及其 git 歷史），與 FinMind 條款（再散布、對外公開、須向來源機關取授權）的關係如何；既有文件分級（AUDIT H2、BACKLOG ③a／③c）如何看待 | 客戶／法務 | **是**：AI 不判斷是否構成「再散布」 | A1、A2、A4、C2、C3、C11 |
| 3 | 本專案是否屬商業使用；所持 FinMind 方案等級 | 客戶（可回「交法務」） | **是** | A5、B4、B5 |
| 4 | 若日後在畫面顯示融資，「FinMind」與原資料提供機關的顯名位置與字樣（涉 UI → **須先出文字線框**，客戶拍板後才可寫 UI 程式碼；並涉既有測試禁字守衛，見 C6） | 客戶（線框拍板）／法務（必要字樣） | **是** | A3、C6 |
| 5 | 融資資料集的實際來源機關歸屬，與對外公開所需的來源機關授權／FinMind 書面答覆；TWSE 條款原文（A12 二手線索） | 客戶／FinMind／原機關 | **是** | A8、A9、A12、C8 |
| 6 | **DG-SCOPE 回覆**（決策單：範圍選項 A～D；AI 推薦只接融資僅為推薦） | 客戶 | **是** | §4 |
| 7 | **接線授權**（`I1144-WIRING-GATE`）；前置條件不因本表完成而成立 | 客戶 | **是** | §4 |
| 8 | **產線 workflow 是否恢復**、陳舊 queued Run 是否取消 | 客戶 | **是**（DEC-185：重新啟用、取消 Run 皆未授權） | C10 |

---

## 6. 本文件不是什麼

1. **不是授權**：不授權接線、取數、定期取用、發布、再散布、啟用 workflow、改 `data_cache`、改 Cloud／NAS／Secrets。
2. **不是放行**：不解除 `DG-LIC`／`DG-PIT`／`DG-COV`／`DG-SCOPE`／`I1144-WIRING-GATE`；本表任一格填 HAVE，都不得被引用為「已放行」「條款已確認」「接線就緒」「合規」。
3. **不是法律意見**：不判斷任何用途合法或違法；A 層有條款記載 ≠ B 層適用 ≠ C 層已取得授權。
4. **不證明歷史口徑正確**：sanity／單位檢查是資料品質防線，不替代授權與時間語意（見 §3 結語）。
5. **不改任何程式、資料、測試、workflow、其他文件**：本批只新增這一個檔案。
6. **單組作者結論**：全文為作者單組整理，所有「出處存在」與「轉述正確」須由非作者 QA 重跑 §7 核對；未經 QA 前不得升格為裁示依據。

---

## 7. 可重現驗證（範圍限 docs 與程式註解／檔頭；於 repo 根目錄執行）

```bash
# 1. DEC 標題存在
grep -n "^### DEC-\(169\|171\|184\|185\|193\|205\)｜" docs/DECISIONS.md

# 2. SUPP 章節與 Q 條款列
S=docs/vnext/UI2_RUNTIME_PREGATE_EVIDENCE_SUPPLEMENT_2026-11-11.md
grep -n "^### 1.3\|^### 11.2\|^#### 11.3.2\|^### 11.4\|^### 11.5" "$S"
grep -n "^| Q\(1\|3\|4\|5\|8\|9\|10\|11\|12\|13\) |" "$S"
grep -n "FinMind 自述（非證據）\|TaiwanStockTotalMarginPurchaseShortSale" "$S"
grep -n "N-14" "$S"

# 3. AUDIT／DPE3／SHEET 章節與關鍵句
grep -n "^## 2\.\|^### 2.1\|^### 2.2\|^## 3\." docs/vnext/PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT_2026-11-11.md
grep -n "^### 1.2\|^### 1.3\|^### 1.4\|^## 3\.\|repo 內查無客戶回答" docs/vnext/DPE3_TERMS_AND_DPE6_CLOUD_CONFIG_EVIDENCE_2026-11-13.md
grep -n "^## 決策\|只接融資不需要回答 DG-COV\|附加條件 X" docs/vnext/DATA_WIRING_GATE_DECISION_SHEET_2026-11-12.md

# 4. BACKLOG 列
grep -n "DGLIC-PER-DATASET-MATRIX\|I1140-MARGIN-UNIT-MIX\|I1140-MARGIN-SOURCE-TEXT\|WORKFLOW-PAUSE-3-DATA\|I1144-LIC-THREE-QUESTIONS\|I1144-WIRING-GATE" docs/BACKLOG.md

# 5. DG-SCOPE：QA 請通讀命中處，自行確認無客戶回覆
grep -n "DG-SCOPE" docs/DECISIONS.md docs/BACKLOG.md

# 6. 程式註解：口徑／單位／sanity／直連
grep -n "MARGIN_DATASET\|TWD_PER_YI\|MARGIN_MONEY_ROW_NAME" shared/margin_schema.py
grep -n "MARGIN_BALANCE_SANITY" shared/signal_thresholds.py
grep -n "直連" scripts/update_macro_history.py
grep -n "MARGIN_SOURCE_TEXT\|0 production caller" src/services/margin_fact_service.py

# 7. L3 零引用（預期無輸出）
grep -rn "margin_fact_service" --include=*.py src app.py app_ui2.py shared scripts | grep -v "^src/services/margin_fact_service.py"

# 8. 既存消費面（C4）與顯名（C6）
grep -rn "get_chart_series\|load_v2_chart_series" --include=*.py src | grep -v "def "
grep -n "finmind_margin" scripts/export_stock_db.py
grep -n "force-push\|data 分支" .github/workflows/export_db.yml
grep -n "FinMind" src/ui/tabs/tab_macro_v2.py src/ui/views/page_today.py

# 9. 追蹤與忽略狀態（僅 git 中繼資料，不讀檔案內容）
git ls-files data_cache | grep finmind_margin
git check-ignore -v data_cache/finmind_margin.parquet ; echo "exit=$? (1＝未被忽略)"

# 10. 來源歸屬衝突（B7）
grep -n "融資餘額" DATASTATION.md

# 11. 既有文件分級（C2、C11）與 export_db（C4-export）
grep -n "^| H2 \|^### 4.1\|^### 3.3\|同為公開" docs/vnext/PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT_2026-11-11.md
grep -n "③a\|③c\|為選取欄位\|字面禁止對外再散布" docs/BACKLOG.md
grep -n "^### DEC-169｜\|^### DEC-184｜\|無任何一檔有「明示允許」" docs/DECISIONS.md
grep -c "export_db" docs/DECISIONS.md docs/BACKLOG.md          # 預期各 0（查無暫停記載；單組 grep）
grep -n "下游\|force-push" scripts/export_stock_db.py .github/workflows/export_db.yml | head

# 12. 二手線索（A12）與舊 tab_macro 即時路徑（C4）
grep -n "^| Q2 \|WebSearch 線索" docs/vnext/UI2_RUNTIME_PREGATE_EVIDENCE_SUPPLEMENT_2026-11-11.md
grep -n "禁止未經同意\|自動化" docs/vnext/DPE3_TERMS_AND_DPE6_CLOUD_CONFIG_EVIDENCE_2026-11-13.md
grep -n "唯讀 API 比對\|概念落差" docs/vnext/DPE3_TERMS_AND_DPE6_CLOUD_CONFIG_EVIDENCE_2026-11-13.md
grep -n "fetch_margin_balance" src/services/macro_fetch_orchestrator.py src/ui/tabs/tab_macro.py
grep -n "test_source_text_has_no_unverified_claims" tests/test_margin_fact_service.py
```

---

## 8. NOT VERIFIED 彙整

| # | 項 | 原因 |
|---|---|---|
| 1 | FinMind 官網即時條款是否與 2026-10-31 版相同 | 沙箱連不到；本文為二次記載 |
| 2 | 本專案 FinMind 方案等級；是否商業 | repo 內無證據；無客戶回覆 |
| 3 | FinMind 與來源機關的另行契約內容 | 僅 FinMind 自述 |
| 4 | 融資資料集的實際來源機關及其條款原文（含 TWSE『交易資訊使用管理辦法』） | repo 內零頁 |
| 5 | 融資資料集是否含上櫃、能否稱「全市場」 | 未驗；DEC-193 已移除該宣稱 |
| 6 | OGDL 對融資是否適用 | 僅 SPDX 轉錄本 |
| 7 | repo 現時可見性 | 兩份既有文件措辭不一致（C1）；本批無網路 |
| 8 | Cloud 公開網址／收費／部署 SHA；Cloud 是否實際渲染融資走勢卡與方向燈；畫面是否有顯名 | 無 Cloud 證據；未目視 |
| 9 | `export_db.yml` 現況與 `data` 分支下游 | 未重驗；本批只讀 workflow 檔頭註解 |
| 10 | 2026-11-14 後三支 workflow 與 #1124 的 GitHub 現況 | 本批無網路 |
| 11 | 歷史既有列是否已逐列校正（`I1140-MARGIN-UNIT-MIX`） | 本批刻意未讀 parquet |
| 12 | DG-SCOPE「無客戶回覆」 | 單組 grep；全稱句，須 QA 通讀 |
| 13 | §2.3 C4／C6 的 consumer 與顯名 grep | 單組 grep；間接路徑（registry、資料診斷頁）未查，**不得宣稱已窮舉** |
| 14 | `DATASTATION.md` 與實際取數的來源歸屬衝突（B7） | 未裁定 |
| 15 | 「cron 定期抓取」是否有條款專門表態（B3） | 既有文件只查過「唯讀 API 比對」；定期抓取本身未查 |
| 16 | 融資檔在 AUDIT H2／BACKLOG ③a③c 的既有分級是否被客戶／法務採納 | 既有文件自述非認定；無裁示記載 |
| 17 | `export_db` 是否啟用、`data` 分支現況與下游實際用法；DEC-185 後是否另有暫停 | DECISIONS／BACKLOG 0 命中屬單組 grep；未連網 |
| 18 | 既存路徑是否已觸發 I1140（§3.1 交叉註記） | INFERENCE，未驗實際取用 |
| 19 | 舊 `tab_macro` 即時路徑（`fetch_margin_balance`）進舊 UI 的實際畫面與顯名 | 清單未窮舉；未目視 |
| 20 | 本文全部出處轉述 | 單組作者；本版修正未經非作者再次 QA；git 歷史數字本機無法複驗 |
