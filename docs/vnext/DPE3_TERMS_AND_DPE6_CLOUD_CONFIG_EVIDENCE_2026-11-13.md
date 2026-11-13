# DPE-3 條款確認準備與 DPE-6 Cloud 設定證據 — 2026-11-13

> **性質**：證據文件（docs-only，新增單檔）。**不是決策來源**：決策只在 `docs/DECISIONS.md`（DEC-179）；本文件不新增第二份 SSOT，不改任何既有文件的語意。
> **基準**：本分支基底＝`df844b900520533f2e69d6edffe117478dc57547`（`git log` 實查）。文中 `file:line` 皆為 **2026-11-13、df844b9 時點**由寫入組以 `grep`／`sed` 逐一重核的行號快照，**會漂移**；引用時請重跑 `grep -n`。
> **單組聲明**：本文件為寫入組單組撰寫，**未經非作者獨立 QA**（`CLAUDE.md` §-2 規則 6）；**不是 QA PASS，不是授權，不是法律意見**。QA 結果由總管於 PR 補記。
> **客戶裁示出處**：DEC-179（DPE-3＝D、DPE-6＝B）。**方案代號不得混淆**：DPE-3＝D 不是 DPE-3 的 B，也不是 UI 決策單的 Q1＝A（對照表見 DEC-179「方案代號對照表」）。

## 0. 目的、範圍、禁止事項、證據方法

**目的**：為 DEC-179 的兩項客戶裁示準備「客戶或法務下一步要提供什麼」——(1) DPE-3＝D：外部對帳涉及哪些資料來源、各來源的使用條款證據到哪裡、還缺什麼；(2) DPE-6＝B：repo 內是否已有可信的 Streamlit Cloud 設定證據、還缺哪些設定值。

| 項 | 內容 |
|---|---|
| 本文件**做**了什麼 | 唯讀檢視 repo 內既有文件、程式碼、設定檔與 workflow；整理表格；列出缺口與最小回覆範本 |
| 本文件**沒有**做 | **未連網**；**未執行任何 fetcher／腳本**；**未抓取任何外部資料**；**未動 `data_cache`**；未登入任何第三方；未要求或顯示任何 Secrets／API Key／Token／密碼；未修改 Streamlit Cloud 設定 |
| 不宣稱 | **不宣稱 `DG-LIC` 已解除**；不宣稱任何來源的條款「已被確認允許」；不宣稱部署正在追蹤 main |
| 證據方法 | 四組獨立唯讀稽核——**DPE-3 兩組、DPE-6 兩組**——結論交叉一致處標「**兩組一致**」，僅一組得出處標「**單組**」；寫入組對本文件引用的每一個 `file:line` 另行重核（見上方基準說明）。四組稽核的原文本文件**不重述**，僅整理結論。**全部仍屬 AI 稽核，非法律意見** |
| 縮寫 | **GAPS**＝`DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md`；**SUPP**＝`UI2_RUNTIME_PREGATE_EVIDENCE_SUPPLEMENT_2026-11-11.md`；**AUDIT-PUB**＝`PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT_2026-11-11.md`；**PREGATE**＝`UI2_RUNTIME_PREGATE_RESEARCH_2026-11-11.md`；除另註外，這些文件都在 `docs/vnext/`；行號 `:N` 指該行 |
| 標籤 | **FACT**（可由所列 `file:line` 重現）／**INFERENCE**（推論，不得當事實）／**NOT VERIFIED**（未驗證）；性質欄：i＝客戶說、ii＝AI 推論或計畫、iii＝repo 可由程式／文件推得、iv＝實際 Cloud 設定紀錄 |

**稽核盲點（如實列出，詳見 §3）**：未讀 GitHub Issue #1107 原文；本地為淺層複製（50 個 commit，僅 2026-11-11 起）；`docs/archive/` 與 `STATE.md` 僅做關鍵字掃描；未檢查 GitHub 端 Deployments／Environments。

---

## 1. DPE-3 條款確認準備（DPE-3＝D）

### 1.1 外部對帳涉及的來源

對帳目標引自 `DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md`（以下簡稱 GAPS）G-01 的 (a)~(d)（GAPS:89）。Tier 欄依 `CLAUDE.md` §2.1 的 5-Tier 表；標 INFERENCE 者為寫入組對 Tier 歸類的推論（該表未逐端點列名）。

| # | 來源 | 對應資料集／對帳目標 | repo 取得方式（file:line） | §2.1 Tier |
|---|---|---|---|---|
| 1 | Yahoo Finance `^TWII` | `data_cache/twii_ohlcv.parquet`；對帳目標 **(a)**：#1124 台股 11-10 開高低收與成交量（含被補寫的 4,766,000）（GAPS:89） | `scripts/update_macro_history.py:207`（chart API URL）；`:136-143` 經 `proxy_helper.fetch_url`（NAS／Squid 鏈），`:144-147` 缺 helper 時直連；`:36` 檔頭註記 | **T2**（FACT：§2.1 T2 列示 Yahoo Finance query1） |
| 2 | FinMind | `finmind_inst.parquet`；目標 **(b)**：外資 11-11 −7.66 億（前一日 −341.17 億、再前日 −900.56 億，量級偏小）與 11-10（GAPS:89）。dataset `TaiwanStockTotalInstitutionalInvestors` | `scripts/update_macro_history.py:326`；`_finmind_get` 直連（不走 proxy）`:153-165` | **T2** |
| 3 | FinMind | `finmind_margin.parquet`；目標 **(c)**：融資 11-10、11-11（GAPS:89）。dataset `TaiwanStockTotalMarginPurchaseShortSale` | `shared/margin_schema.py:54`（`MARGIN_DATASET`）；`scripts/update_macro_history.py:409`；`:376` 函式說明 | **T2** |
| 4 | TWSE rwd（T86／MI_INDEX）與 TPEX（insti／afterTrading／otc） | `sector_flow/daily_net.parquet`；目標 **(d)**：板塊 11-10、11-11 全體淨額合計（−77.03、+259.02 億）與業別數（46、45）——#1125（GAPS:89） | `scripts/update_sector_flow.py:15`（來源說明）、`:140-142`（`_SOURCE_TWSE`／`_SOURCE_TPEX`） | TWSE／TPEX 官方 API 屬 **T1**（FACT：§2.1 列 TWSE／TPEX OpenAPI）；**rwd／網頁 JSON 是否同屬 T1＝INFERENCE** |
| 5 | TWSE／TPEX openapi（業別母體） | `sector_flow/industry_raw.json`、`ticker_sector.json`（與目標 (d) 的業別數相關，**關聯為 INFERENCE**） | `src/data/stock/market_close_fetcher.py:265-266`（`t187ap03_L`／`mopsfin_t187ap03_O`） | **T1**（INFERENCE） |
| 6 | 權威交易日曆（G-07） | 11-10、11-11（及 11-12）是否為交易日（GAPS:131-136）；GAPS 未指名來源 | repo 現有 `src/data/stock/twse_holiday_fetcher.py:8`（TWSE openapi `holidaySchedule`）；該檔檔頭自陳寫成時**沒有拿到真實回應比對過**（`:21-23`） | **T1**（INFERENCE） |
| 7 | #1126 forward-test 帳本 | **不先列對帳**（欄位為凍結帳本、PIT 疑點優先，GAPS:89） | — | — |

**補充（單組，據派工訊息）**：#1124 另含 data.gov.tw PMI 與央行 EF15M01，**不在 G-01 對帳目標內**（GAPS:279 只寫 #1124 為「外資、融資、PMI 備份與 `metadata.json` 5 檔整包」）。

### 1.2 現有條款證據（各來源）

| 來源 | repo 內現有證據 | 等級 | 出處 | 尚未決／缺口 |
|---|---|---|---|---|
| **FinMind** | 官方 GitHub Pages 原始檔的條款逐字摘錄；**條款版本日期 2026-10-31**，記錄於 2026-11-11 | **PARTIALLY VERIFIED** | `UI2_RUNTIME_PREGATE_EVIDENCE_SUPPLEMENT_2026-11-11.md` §11.2 Q1~Q13（`:452-470`）；`PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT_2026-11-11.md` §2.1 | 官網即時頁是否相同＝NOT VERIFIED；方案等級／是否商業／是否有另行契約＝NOT VERIFIED。條款內容針對**再散布、對外公開、商業**（Q4、Q5、Q8、Q9、Q10）；**未見針對「唯讀 API 比對」的專門條文**（**單組掃描，INFERENCE**）。Q5 明說對外公開須向**原資料來源機關**取得授權（非 FinMind 所能授予）。FinMind 條款約束的是「使用者與 FinMind」，**不能替代**TWSE／TPEX 條款（SUPP §11.3.2 末段） |
| **TWSE** | **無官方原文**。僅 WebSearch 摘要稱網站條款禁止未經同意以自動化程式下載（**INFERENCE，不得據以下結論**）；FinMind Q2 轉述須遵守『交易資訊使用管理辦法』（**二手線索**） | NOT VERIFIED | SUPP `:491`、`:478-489`（逐資料集表）；AUDIT-PUB `:69`；`DATA_WIRING_GATE_DECISION_SHEET_2026-11-12.md:403` | 『交易資訊使用管理辦法』**全文未取得**（決策單 `:466`）；TWSE 網站條款、openapi 是否自有聲明、openapi 是否掛 data.gov.tw 適用 OGDL＝未知 |
| **TPEX** | **無官方原文**。僅搜尋摘要稱另有獨立網站條款含類似自動化下載禁止（**INFERENCE**） | NOT VERIFIED | SUPP `:491`；AUDIT-PUB `:70` | 網頁 JSON 與 openapi 授權是否一致未知；不得把 TWSE 條款套 TPEX |
| **Yahoo Finance** | **無 Yahoo 官方文字**。僅第三方 yfinance README 稱「personal use only」（**非 Yahoo 文字，INFERENCE**）；本專案走**未公開文件**的 chart 端點 | NOT VERIFIED | AUDIT-PUB `:74`、`:163` | Yahoo 條款頁網域 **repo 內未列**，需另補 |
| **MOPS** | **無原文**；搜尋**找不到** MOPS 自身條款 | NOT VERIFIED | AUDIT-PUB `:71`；SUPP `:486`（MOPS 列） | MOPS 條款獨立於 TWSE 主站，未查 |
| **央行 CBC（EF15M01）** | **無原文**；搜尋摘要稱宣告採 OGDL v1＋註明出處，摘要自承另一版本宣告未提（INFERENCE） | NOT VERIFIED | AUDIT-PUB `:73` | EF15M01 是否在該宣告範圍未知 |
| **data.gov.tw（PMI 6100）** | 僅 SPDX 的 **OGDL-Taiwan-1.0 轉錄本**，**不是** data.gov.tw 原頁（Q13） | PARTIALLY VERIFIED（轉錄本）；適用本專案 NOT VERIFIED | SUPP `:470` | 需看**該資料集頁**的授權欄與顯名文字 |
| **FRED** | `DG-LIC` 對照表**未登錄**（SUPP §11 範圍 grep「FRED」0 命中；AUDIT-PUB 0 命中；單組 grep） | NOT VERIFIED（無證據亦無登錄） | 寫入組 `grep` 2026-11-13 | 非 #1124～#1126 對帳目標，僅為完整性列示 |
| **TAIFEX** | 僅一句「TAIFEX 條款不適用本專案」，**無推導依據**，**不可引用** | NOT VERIFIED | SUPP `:491` 末句 | — |
| **repo 內任何條款／授權聲明** | **無**：程式碼、設定、workflow 內皆無條款或授權聲明；**根目錄無 README／LICENSE**（寫入組 `ls` 實查）；未找到授權函、契約或方案憑證（單組 grep） | — | AUDIT-PUB:18；決策單 `:399-400` | 不證明 repo 外不存在 |

### 1.3 `DG-LIC` 現況

| 項 | 內容 |
|---|---|
| 狀態 | **HOLD，未解除** |
| 定義出處 | `UI2_RUNTIME_PREGATE_RESEARCH_2026-11-11.md` §6（`:196`）與 §3（`:101`）；commit `d601b5f`（#1147，DEC-166，`git log` 實查） |
| 解除條件（引自 `DATA_WIRING_GATE_DECISION_SHEET_2026-11-12.md` 決策 4「方案 A」，`:416-423`） | 客戶擇一提供：(a) 貼上證交所『交易資訊使用管理辦法』與證交所／櫃買中心網站條款原文；(b) 放行沙箱可連的官方網域；(c) 提供已合法配置 NAS 中繼的執行環境並明確授權唯讀 GET（DEC-168）；(d) 交法務出書面意見。AI 彙整成逐資料集對照矩陣。該決策單稱此為「解除 DG-LIC 的唯一路徑」（`:421`） |
| `I1144-LIC-THREE-QUESTIONS` | 是否商業／是否公開對外／公開 repo 保留個股級來源列是否可接受（BACKLOG:2314；決策單 `:407-412`）。**repo 內查無客戶回答**（寫入組 `grep` 2026-11-13，命中皆為定義或引用） |

**⚠️ 概念落差（必讀）**：`DG-LIC` 原始問題是「**呈現／再散布**」（資料整理後放網站、存公開儲存庫，PREGATE §6 `:196`）；DPE-3 問的是「**唯讀對帳（自動化存取）**」。GAPS:90 把後者歸入 `DG-LIC` 範圍，是 **GAPS 的歸類，不是 DEC 的原定義**。即使唯讀對帳的條款被確認允許，`DG-LIC` 其餘部分（呈現／再散布）**也不因此解除**；DPE-3＝D 與 `DG-LIC` 方案 A 做法相近，但**不是同一個客戶裁示**。

### 1.4 分類：哪些已核實、哪些完全沒有、哪些過期或僅推論

| 類別 | 來源 | 需要誰 |
|---|---|---|
| **(a) 已有正式核實**（僅此一項，且只到 PARTIALLY） | FinMind 條款文字（2026-10-31 版，官方 GitHub Pages 原始檔） | 官網即時版與方案等級：**可由客戶貼原文／告知方案解決** |
| **(b) 完全無證據** | TWSE（含『交易資訊使用管理辦法』）、TPEX、Yahoo Finance、MOPS、央行 EF15M01、FRED（LIC 表未登錄）、TAIFEX（僅一句無依據的「不適用」）、其餘 T3 站台（CIER／NDC／StockFeel／Goodinfo／HiStock 等，§2.1） | 與本次對帳目標直接相關者（TWSE、TPEX、Yahoo、央行）：**可由客戶貼原文解決，或需法務確認**；其餘：暫不需要（非對帳目標） |
| **(c) 過期或僅推論** | TWSE／TPEX「禁止自動化下載」（WebSearch 摘要＝INFERENCE）；data.gov.tw 的 OGDL 轉錄本（非原頁）；Yahoo 的第三方 yfinance README（非 Yahoo 文字）；FinMind 即時版（版本日期 2026-10-31，之後是否改版 NOT VERIFIED） | **需客戶或法務確認**，不得據以下結論 |

### 1.5 若後續只查兩個最大疑點（INFERENCE；兩組 DPE-3 稽核各自獨立得出相近結論）

| 疑點 | 為何最大 | 條款證據現況 |
|---|---|---|
| **一：Yahoo `^TWII`**（#1124 台股 11-10 OHLC 與成交量） | 這是 GAPS:89 目標 (a)；本專案走未公開文件的 chart 端點，且經 NAS／Squid 鏈（`update_macro_history.py:207`、`:136-143`） | 來源 Yahoo **零條款原文**（§1.2） |
| **二：外資 11-11 −7.66 億**（#1124，目標 (b)） | 數值量級明顯偏小（前一日 −341.17 億）；一端是 FinMind，要驗就需要**另一端獨立真值** | 一端 FinMind：條款已有，但只約束使用者與 FinMind（SUPP §11.3.2 末段）；另一端的獨立真值**最可能是 TWSE**（INFERENCE；SUPP 逐資料集表列有 TWSE T86／BFI82U 等），其條款原文為**零** |

**補充事實（不下結論）**：repo 的 NAS 中繼設計用途之一是**繞過資料中心 IP 被官方來源 403**（SUPP:261，`用途定位` 列）；部分 fetcher 使用瀏覽器樣式 User-Agent（`src/data/stock/market_close_fetcher.py:40`、`scripts/update_macro_history.py:147`、`src/data/proxy/proxy_helper.py:214`）。這些做法**是否牴觸任何來源條款，未被任何文件比對（NOT VERIFIED）**，本文件不下結論。

### 1.6 若後續要確認條款或對帳，需要哪些授權（僅描述，**不授權任何一項**）

| 階段 | 對應 | 最低成本做法 | 需要的授權 | 本批是否授權 |
|---|---|---|---|---|
| **階段一：條款確認**（不碰任何資料） | DPE-3＝**D** | 客戶**貼條款原文**，或**交法務書面意見**——**不需任何網路授權、登入或 API key** | 無 | 這是 DEC-179 已裁示的方向，但**實際取證仍待客戶／法務** |
| 階段一替代 | 同上 | 客戶放行沙箱**唯讀 GET 公開條款頁**的網域（**此為 AI 提出的選項，不是客戶裁示**）：`www.twse.com.tw`、`openapi.twse.com.tw`、`www.tpex.org.tw`、`data.gov.tw`、FinMind 條款頁網域（`finmindtrade.com`、`finmind.github.io`，SUPP:447）；**Yahoo 條款頁網域 repo 內未列，需另補** | 網域放行（客戶側環境設定；僅條款頁、僅 GET） | **否**（需客戶另行明示） |
| 階段一替代 | 同上 | 客戶提供**已合法配置 NAS 中繼**的環境並授權唯讀 GET（DEC-168）。**NAS Key 與實際配置 NOT VERIFIED**：SUPP §9.3（`:264-277`）記錄當時沙箱的 NAS 相關變數皆為 False，現況未重測 | 環境與授權 | **否** |
| **階段二：唯讀對帳**（**條款確認後才可能**） | DPE-3 的 **B**（小範圍） | 客戶提供**可連外環境**並**書面授權**「只讀、不存檔、不寫 repo、不新增排程」（GAPS:262） | 書面授權＋可連外環境。是否需 `FINMIND_TOKEN`／NAS 取決於客戶提供的環境；登入需求 NOT VERIFIED | **否——DEC-179 明文不授權；條款確認後是否選 B 須客戶另行裁示** |

### 1.7 狀態與最小回覆範本

**狀態：BLOCKED／NOT VERIFIED，等待客戶或法務。** AI 不得自行取得條款原文（沙箱對官方站台一律被拒，SUPP:447；NAS 未配置）。

客戶可擇一回覆（皆**不需**貼任何 Secrets）：

```
【DPE-3 條款確認，三選一】
(1) 條款原文：來源〈TWSE／TPEX／Yahoo／央行／其他〉，貼上〈條款或管理辦法原文〉
(2) 法務意見：〈貼書面意見或摘要；注明日期與出具者〉
(3) 放行網域（僅條款頁、僅唯讀 GET）：同意放行 www.twse.com.tw、openapi.twse.com.tw、
    www.tpex.org.tw、data.gov.tw、finmindtrade.com、finmind.github.io；Yahoo 條款頁網域：〈客戶補〉
另請順帶回答（可回「交法務」）：本專案是否商業使用〈是／否／交法務〉；FinMind 方案等級〈…〉
```

---

## 2. DPE-6 Cloud 設定確認（DPE-6＝B）

### 2.1 DPE-6 與 G-13 原文

- **G-13**（GAPS:71、`:177-181`）：「Streamlit Cloud 追蹤哪個分支、何時重新部署」。現有證據＝「**repo 內沒有部署設定證據**」（GAPS:179）；既有事故紀錄把「部署的不是 main 最新提交」列為候選假說；為何重要＝即使資料 PR 合併進 main，**若部署端不追 main 或不自動重新部署，台股卡仍不會前進**；誰能補＝客戶貼 App 設定頁的 Repository／Branch／Main file path 與重新部署行為（**不要貼任何 secrets**，GAPS:181）。
- **DPE-6 方案 B**（GAPS:300-310，B 列 `:305`）：「客戶貼出 App 設定頁的 Repository、Branch、Main file path 與部署觸發方式（**不要貼 secrets**）」；效果＝立即排除「部署不追 main」假說、零施工。**客戶選的是 B；不含 C（日後比對 Cloud 畫面資料日）與 D。**

### 2.2 repo 內證據表

| # | 內容 | 來源（file:line） | 日期 | 性質 | 能證明什麼／不能證明什麼 |
|---|---|---|---|---|---|
| 1 | G-13／DPE-6 自陳「repo 內沒有部署設定證據」 | GAPS:71、`:179` | 2026-11-12 | ii（AI 稽核結論） | 這是本次稽核的**起點結論**，不是 Cloud 紀錄 |
| 2 | 各處 NOT VERIFIED 登記：Cloud 追蹤分支／入口檔／是否在線 | BACKLOG:2411；`PRODUCTION_HEALTH_FIVE_AXIS_SNAPSHOT_2026-11-13.md:150`、`:200`；HANDOFF:606、`:715` | 2026-11-12～13 | ii | 全部自陳**未驗證** |
| 3 | 2026-09-08 雲端日誌片段：`/mount/src/my-stock-dashboard/packages.txt` | `tests/test_deploy_no_apt_packages.py:1-14`（docstring 稱「使用者取得的雲端日誌」） | 2026-09-08 | i（客戶取得的日誌片段，經 docstring 轉述） | 只佐證**曾存在名為 `my-stock-dashboard` 的 mount 目錄**；**無分支、無入口檔、無 owner** |
| 4 | 2026-10-27 D2 事故：Cloud 啟動 `ImportError`；候選假說「**部署 commit 非 main**」**未證實**，根因未確認 | BACKLOG:833；DECISIONS:942；PROJECT_STATE:723 | 2026-10-27 | ii | 假說，**不是**設定紀錄；反而顯示「部署版本是否為 main」當時就是未決問題 |
| 5 | 2026-11-10 客戶 Cloud **手機截圖**回饋（「這圖放在 OneBrain 這邊滿奇怪的」） | DECISIONS:7969（該條自陳 repo 內無客戶逐字裁示、NOT VERIFIED by repo） | 2026-11-10 | i（客戶說；經轉述） | 截圖**不在 repo**，且是畫面不是設定頁；只佐證客戶曾在 Cloud 看到某版畫面 |
| 6 | 2026-11-02 New UI2 Preview app **計畫**：「同 repo、main、Main file＝`app_ui2.py`」；`NUI2-PREVIEW-APP-MANUAL` 為 blocked，待 `app_ui2.py` 實際可部署才以 Manual Action Gate 通知客戶 | BACKLOG:1187（「同 repo、main、Main file＝`app_ui2.py`」出自此處）；DECISIONS:5980（僅支撐「獨立預覽 app＋入口 `app_ui2.py`」，G1＝A 的描述，**不含**「同 repo、main」） | 2026-11-02 | ii（計畫） | **僅為計畫**，未見客戶已建立第二個 Cloud app 的紀錄；Gate 未發 |
| 7a | 2026-08-14 實機驗證報告：驗證對象為 `my-stock-dashboard-…streamlit.app`，頁面標題 `台股AI戰情室 v3.0` | `docs/audit-2026-08/LIVE_VERIFY_AND_DECLUTTER.md:3-4`；現行 `app.py:127` 的 `page_title` 亦為同字串 | 2026-08-14 | iii／ii | 佐證**當時**有一個在線 Cloud app 且畫面標題與 `app.py` 吻合（Main file 為 `app.py`＝**INFERENCE**）；**三個月前，無分支資訊** |
| 7b | 2026-08-15 交接：「要在 Streamlit Cloud 看：Settings → Branch **暫時指向該分支**」「看不到新東西先 Reboot app」；寫入組 `grep` `改回\|指回\|Branch` 於該檔、`STATE.md`、`docs/audit-2026-08/` **未見將 Branch 改回 main 的記錄**（單組 grep） | `HANDOFF_2026-08-15.md:32-33` | 2026-08-15 | ii（舊文件教學） | **旁證 Branch 曾被建議手動改過**；是否改回、現在是什麼＝**未知** |
| 8 | **App 網址（寫入組補充，非派工訊息所列）**：repo 內多處記錄子網域前綴 `my-stock-dashboard-…streamlit.app` | `STATE.md:663`（2026-08-11 實機驗收）、`tests/test_t3_watchlist_message.py:28`、`docs/push_watchlist_signals.md:73`、`HANDOFF_2026-08-15.md:51`、`LIVE_VERIFY_AND_DECLUTTER.md:3` | 2026-08 | iii | 佐證**至少曾有**一個 Cloud app；**不含** owner、Branch、Main file；網址為公開位址，非憑證。**單組補充**，現在是否仍有效＝NOT VERIFIED |
| 9 | `.devcontainer` 的 `streamlit run app.py` | `.devcontainer/devcontainer.json:22` | — | iii | 這是 **Codespaces** 開發環境，**不是 Cloud** |
| 10 | `.github/workflows` 無 deploy／webhook 步驟 | 寫入組 `grep -rln "deploy\|webhook\|streamlit.app\|share.streamlit" .github/workflows` 0 命中（2026-11-13）；`pr-check.yml:5-7` 只針對 `main` 的 PR／push 跑測試 | 2026-11-13 | iii | 僅 **GitHub 端**；**不能推論 Cloud 端**如何觸發部署 |
| 11 | `.streamlit/config.toml` 無部署資訊 | `.streamlit/config.toml`（僅 `[theme]`／`[server]`／`[browser]`／`[logger]`） | — | iii | 無 Repository／Branch／Main file／觸發方式 |
| 12 | repo 根有 `app.py` 與 `app_ui2.py` | `app_ui2.py:1-5`（docstring：「這是 **Preview 入口**，不是 production default：`app.py` 不引用本檔」） | — | iii | `app.py` 為 production 預設入口＝**INFERENCE**（寫入組 `grep` 未在 `app.py` 找到「唯一入口」自稱）；Cloud 設的是一個還是兩個 app、各指哪個檔＝**NOT VERIFIED** |

**結論（FACT）**：以上 #1～#12（含 7a／7b）中**沒有任何一項是性質 iv（實際 Cloud 設定紀錄）**——沒有一份是 Streamlit Cloud 設定頁的內容、截圖文字或客戶貼出的設定值。**兩組稽核一致。**

### 2.3 四欄位現況

| 欄位 | 現況 | 最強的間接線索 | 為何不足 |
|---|---|---|---|
| **Repository** | **NOT VERIFIED** | mount 目錄名 `my-stock-dashboard`（#3）；網址前綴 `my-stock-dashboard-…`（#8）；本 repo 為 `linchen-20200325/my-stock-dashboard` | **名稱吻合不能排除 fork 或同名 repo**；mount 目錄只含 repo 名，不含 owner；網址是 App 名，不是 Repository 欄 |
| **Branch** | **NOT VERIFIED** | Preview 計畫「main」（#6，計畫）；D2 事故假說「部署 commit 非 main」（#4，未證實） | 兩者都不是設定紀錄；**反有 2026-08-15 建議手動改 Branch 的旁證且無改回記錄**（#7b），所以「Branch＝main」不可推定 |
| **Main file path** | **NOT VERIFIED** | 2026-08-14 畫面標題與 `app.py:127` 一致（#7a，INFERENCE）；`app_ui2.py` 自稱 Preview 入口（#12） | 三個月前的單次畫面；**`app.py`／`app_ui2.py` 是一個還是兩個 Cloud app 不明** |
| **部署觸發方式**（自動追 push／手動 Reboot／不確定） | **NOT VERIFIED** | 2026-08-15 交接稱「Cloud 從睡眠喚醒不保證跑最新 commit」「看不到新東西先 Reboot」（#7b，客戶自己記過） | 這是**症狀描述**，不是設定；`.github/workflows` 無 deploy 步驟只說明 GitHub 端不推送部署（#10） |

**明文：目前不得宣稱部署正在追蹤 main。** 在客戶貼出實際設定值（性質 iv）之前，一律標 NOT VERIFIED。

### 2.4 稽核盲點（兩組 DPE-6 稽核如實列出）

| 盲點 | 影響 |
|---|---|
| **未讀 GitHub Issue #1107 原文** | 該 Issue 可能含客戶貼過的部署路徑；本表「repo 內無 iv 證據」的範圍是**已 checkout 的檔案**，不含 Issue／PR 留言 |
| 本地為**淺層複製**（50 個 commit，僅 2026-11-11 起，`git log` 實查） | 更早的 commit 歷史（如 2026-08 的部署相關討論）未完整檢視 |
| `docs/archive/` 與 `STATE.md` **只做關鍵字掃描** | 可能漏掉未含關鍵字的部署紀錄 |
| 未檢查 GitHub 端 **Deployments／Environments** | 若 GitHub 有 Cloud 回寫的 deployment 紀錄，本表未涵蓋 |

### 2.5 客戶最小必要資訊（**排除 Secrets**）

對**每個** Cloud app 提供下列欄位；若有 New UI2 Preview 第二個 app 另填一份，沒有就寫「沒有」。

> **請勿開啟或貼上 Secrets 分頁、API Key、Token、密碼；截圖只截含下列欄位的部分。**

```
【DPE-6 Streamlit Cloud 設定，每個 app 一份】
App 網址（子網域即可）：
Repository（owner/repo）：
Branch：
Main file path：
部署觸發：〈自動追 push／手動 Reboot／不確定〉
目前部署的 commit 或畫面版本字串（看得到才填，看不到免填）：
App 擁有者所屬 GitHub 帳號／workspace（用來排除 fork）：
查看日期：
目前狀態：〈Running／Sleeping／Error〉
New UI2 Preview 第二個 app：〈有，另填一份／沒有〉
```

AI 收到後僅登錄為證據（標明日期與來源類別＝客戶說），**不得**據以修改 Cloud 設定、部署分支、正式入口或環境變數；是否據以處置資料 PR 需 DPE-4／DPE-5 另行裁示。

---

## 3. NOT VERIFIED 與限制總表

| 項 | 狀態 |
|---|---|
| TWSE（含『交易資訊使用管理辦法』）、TPEX、Yahoo、MOPS、央行 EF15M01、FRED、TAIFEX 的條款原文 | **NOT VERIFIED**（repo 內零頁或僅二手線索） |
| FinMind 官網即時頁是否與 2026-10-31 版相同；方案等級；是否另有契約；本專案是否商業 | **NOT VERIFIED** |
| FinMind 條款是否有針對「唯讀 API 比對」的專門條文 | **單組掃描，INFERENCE**（未見） |
| 各 Tier 歸類中標 INFERENCE 者（rwd 網頁 JSON、業別母體、交易日曆） | INFERENCE |
| NAS 中繼的 Key 與實際配置 | **NOT VERIFIED**（SUPP §9.3 為當時沙箱紀錄，現況未重測） |
| Streamlit Cloud 的 Repository／Branch／Main file path／部署觸發方式 | **NOT VERIFIED**；repo 內無性質 iv 證據 |
| Cloud 上是一個或兩個 app；`app.py`／`app_ui2.py` 各指向何者 | **NOT VERIFIED** |
| GitHub Issue #1107 原文；GitHub Deployments／Environments | **未檢視** |
| 四組稽核的原文 | 本文件僅整理結論，寫入組未逐字重讀 |
| 派工訊息所述「main push CI run 43413653601」等 GitHub 端事實 | **總管轉述，寫入組未連網重取** |
| 本文件整體 | 單組撰寫，**未經非作者獨立 QA**；行號為時點快照 |

## 4. 本文件不構成授權（逐條）

1. 不授權任何外部對帳（DPE-3 的 B／C 皆**未選**；DPE-3＝D 只是條款確認前置決定）。
2. 不授權連網、登入第三方、抓取或儲存外部資料、新增 API／MCP／cron／Secrets、變更原始資料或 `data_cache`。
3. **不解除 `DG-LIC`**（亦不解除 `DG-SCOPE`／`DG-COV`／`DG-PIT`、`I1144-*`、G-F2～G-F6、外資 L3、`REORG3C-Q5-GATE`、D6）。
4. 不授權 DPE-6 的 C／D（日後比對 Cloud 畫面資料日）；不授權 AI 修改 Streamlit Cloud 設定、部署分支、正式入口或環境變數。
5. 不授權合併／關閉／rebase #1124～#1126，不處置 #1164，不清理 #1119。
6. 不授權 UI 施工（🗂 Q1～Q7 仍待客戶裁示）、不授權施工 `DEC178-QB3-*` 六項 P3 候選、不授權修改 `SHOWN_FOLDS`／UI 契約／測試 allowlist／`.claude/settings*`。
7. 不授權修改投資公式、Risk Cap、System Action、OneBrain 正式接線、Old UI。
8. 不得被引用為「條款已確認」「Cloud 追蹤 main」「已 QA PASS」。
