# New UI2｜過期規格停用索引、資料缺口與治理記憶收斂（2026-11-06）

> **狀態：獨立唯讀稽核＋待審草案；不是 main 的新 Active Contract。** 使用者要求清理不適用規格／記憶，查明真正取不到的資料、提出替代方案並更新可持續交接。當次 GitHub main `343f0e0e4072362c45bff1ccc25b61014d15c691`，Open Draft #1022/#1027/#1029/#1030/#1031/#1032；資料稽核 #1023/#1025。正式更改既有文件、程式或資料來源前必須以最新 main/PR head/diff/CI 重新驗證。本檔不覆蓋它們，共用治理檔由協調 Gate 收斂。
>
> **方法**：核對 `PROJECT_RULES.md`、`NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`、`NEWUI2_MOBILE_DRAWER_NAV_CONTRACT_2026-11-04.md`、#1030 Draft、`DATA_HEALTH_AUDIT_2026-10-23.md`、`MARKET_TREND_RESEARCH_BASELINE_2026-11-03.md`、`NEWUI2_REAL_FEED_MAPPING_2026-11-03.md`、`src/services/ui2/real_feed.py`、`data_registry_scanner.py`。**只驗 repo 的存在、資料流與舊稽核證據；未能登入 production、取得使用者憑證或對每個 API 做現場請求；不能宣稱列出的所有來源今日都壞了。** 2026-10-23 舊稽核狀態須重查，尤其 FinMind API 403、Yahoo/TWSE/TAIFEX 未實連，不能當 2026-11-06 實測結果。

## A. 正式適用性對照（先標 SUPERSEDED，勿刪歷史）

| 既有條文／文件 | 對 New UI2 最新方向的處理 | 保留不動 |
|---|---|---|
| `PROJECT_RULES.md` §30「四頁永久上限」、`NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md` §2 四頁 | **產品呈現要求 SUPERSEDED pending formal SSOT**：五頁「📊市場／🎯標的／💼持股／👤我的／🗂資料」；不得以四頁舊文字阻擋新線框 | 歷史客戶裁示、Data State、Missing、證據與投資風控 |
| Active Contract §2.5 桌機左 rail／帳號與 Drawer Contract 2026-11-04 手機抽屜、底部四格 | **導航布局 SUPERSEDED pending formal SSOT**：桌手機均頂部五頁導覽；手機橫向可捲動；頂部 Active Sheet、右上帳號。不得移除 OAuth 安全流程 | 歷史文件；真實 Auth/Sheet 契約及 a11y 測試要等價替代 |
| Active Contract §3／👤我的「完整資料健康度」 | **位置 SUPERSEDED**：全量來源健康度移至🗂資料；👤我的留設定與入口；其他投資頁仍留必要資料日、缺值、來源 | 確定性健康診斷能力與完整 registry |
| #1022 早期四頁藍圖、#1029 早期 44px drawer 與左 rail 線框 | **舊版呈現句不當 Active 施工依據**，先完成 supersession 對照及新的 390/1440 五頁視覺 Gate | 兩模式標的、W-11 資料語意、首屏需求、圖表來源契約 |
| 「每頁一個完全獨立 OneBrain／每次吞全資料／從 UI Top-N 給 AI」 | **架構讀法 SUPERSEDED**：唯一資料層、Evidence Registry、UI VM / Digest 雙投影、一套協調六研究單元＋全域反證複核；按需 evidence pack、coverage Gate | AI 不連外取數、不寫入、Single Action Authority / Risk Cap |
| 「短中長＝固定 3/6/9 個月」、「歷史 PDF 估值數字＝最新行情」 | **不得沿用**：短/中/長研究時域待契約，歷史 PDF 只作研究假設與來源 | 原始研究材料與當時日期 |
| 任何「移除 UI 細節＝移除後端 evidence」、「沒有資料＝0／正常／安全」、「老師姓名作正式功能名」 | **禁止復活** | 完整證據、同義命名歷史及正式缺值語意 |

**清理策略（三案）**：①直接刪歷史（高風險，不採）；②讓每個舊文件都改全文（檔案衝突/Token 高，不採）；③**新增當前唯一 Active 契約＋逐條 supersession map，舊 DEC 原文保留、各舊文件僅加適用性註記、用測試替換舊布局守衛**（推薦）。等待 #1030/#1032 的同檔協調，不能兩組同時覆寫 `PROJECT_RULES` 等共有檔。

## B. 資料真相分類：不能把「不能抓」與「未接」混為一談

- **N0 Source absent / 尚未核准**：repo/既有正式資料管線找不到可驗證來源或 contract，**不是**證明外界沒有來源。
- **N1 Source exists but not wired**：repo 有 fetcher、儲存或舊 UI 消費者，但 New UI2 尚無正式接線；不應找新 API。
- **N2 Source limited / broken semantics**：有來源，但舊稽核指出填零、代理、單位、口徑、日期或歷史不足；需修復與重驗。
- **N3 External availability unverified**：尚未在授權 production 或現時端到端抓取驗收；「無法實際取得」目前**無法成立**，標 `NOT VERIFIED`。
- **N4 Deprecated/retired**：功能已刪且零寫入者，應從活躍健康監測移除，而非永久顯示缺資料。

### B1. 來源缺口／未接線盤點（截至 2026-11-06 的 repo 證據，非實時 API 成功率）

| 項目 | 分類 | 可驗證事實與限制 | 下一步建議 |
|---|---|---|---|
| 台股大盤 forward EPS／EPS×PE 正式估值 | **N0** | `MARKET_TREND_RESEARCH_BASELINE` §4/5：repo 無正式大盤 forward EPS；PE、期別、情境倍數仍 Pending；個股 EPS 不可直接代用 | **優先研究**合法可持續的指數 EPS／加總成分 EPS 資料；來源、定義、覆蓋率與編制一致性 Gate；未核准僅研究框架與 Sheet 假設，不產正式指數預測 |
| 缺貨與大型訂單的可驗證前瞻資料 | **N0/N3（逐筆）** | 已有 `shortage_screener_service`，但「訂單」「缺貨」敘事不等於已驗證合約／業績；沒有逐筆來源不得當正式事實 | Sheet 獨立研究事件表：官方公告/法說與第三方預測分級，來源 URL、日期、數量、單位、有效期、反證、確認態；缺資料標 unverified |
| Sahm Rule Required veto | **N0（舊 audit）** | `DATA_HEALTH_AUDIT` §3.1：無來源，舊記錄為紅線永不觸發 | 查美國官方失業率序列＋同一口徑的規則推導來源；事實源與規則仍各自 Gate；未驗證不得標未觸發或解除風險 |
| 美國 2Y、10Y-2Y／10Y-3M、真實利率/TIPS | **N0/N1 交叉驗證** | 舊 audit 說無 2Y 等完整 production fetch；但 repo 另有 10Y-3M 舊 logit 計算或 10Y source，不能直接說「全無」 | 先重用已驗證的 US10Y，再調查 FRED/US Treasury 2Y/3M/TIPS 的實際欄位、發布延遲與授權；正式來源審核後方可接線 |
| 美國／全球 OECD CLI、美國 ISM PMI | **N0/N1** | 舊 audit：美國/全球 CLI 缺；ISM 有 fetcher 但無 production caller，FRED NAPM 停更 | OECD／Conference Board 等資料授權/頻率研究；ISM 優先研究是否有可合法取得的現行來源，避免復活 NAPM 停更序列 |
| 借券（SBL） | **N0** | 舊 audit §3.3 指 repo 無來源 | 先查 TWSE／TPEx 官方資料可得粒度及用途，再決定是否值得接 |
| AI/CSP CAPEX、OCF/FCF 與訂單關聯 | **N0/N1（分欄）** | PDF 提供歷史研究視角，不等於 canonical CSP 財報來源；個股財報路徑存在，但非完整 CSP 全球覆蓋 | 優先用公司財報/IR 官方公告，分清 capex guidance、實現值、OCF/FCF 和台廠供應鏈的假設，研究表不寫回客觀真相 |
| 真實台股市場廣度 ADL | **N2/N1** | 舊 audit：`fetch_adl` 為 ^TWII 代理，MI_INDEX 真實漲跌家數曾由舊 UI/cron 取得，存在兩套路徑 | 不再讓 proxy 冒充官方 ADL；優先驗 TWSE MI_INDEX producer→canonical→Digest，時間對齊後另 Gate 決定重算與正式得分 |
| 集保大戶/散戶、個股/ETF 成分穿透 | **N1/N2** | 集保已有 fetcher（第三方爬蟲且失敗快取）；ETF 成分有爬蟲但不保證完整；散戶**人數**不等於持股**比例** | 優先查 TDCC 官方可下載原始表與更新頻率；ETF 先查發行商官網成分權重/日期與完整度；無權重只顯示直接曝險 |
| 投信/自營、外資及融資 | **N1/N2** | 有 TWSE/FinMind 等路徑；舊 audit 指備援 fillna(0)、融資缺日期與失準固定門檻 | 先修 missing/日期、取消假零計算，再接 New UI2；不要因 UI 沒值誤判沒有 API |
| 大盤／個股歷史、外資期貨、VIX、國際指數 | **N1/N2/N3** | 既有 Yahoo、TAIFEX、FRED 等路徑；舊 audit 指盤中未收盤值、MA 根數不足、時間戳/口徑與頻率問題 | 並列 source/as_of/fetched_at；驗收盤後日期與最新 trading session；資料不夠不畫 MA200 或歷史曲線 |
| 輸出如「台灣出口訂單」的標籤 | **N2** | 舊 audit 指其值是**海關出口金額** YoY，不是接單金額 | 先修標籤；若真的要外銷訂單，再研究 MOEA 訂單統計資料源 |
| 健康度歷史與 ETF 回測 | **N1 / N4** | 健康度歷史追蹤清單空、排程停用；ETF 回測頁已刪、`etf_backtest_data` 只有舊讀者無寫者（依現有 repo 稽核） | 健康度歷史依是否需要決定啟用；**ETF 回測活躍健康監測列直接標退役、不顯永久缺漏**；歷史與原始文件保留 |

### B2. 比「多抓資料」更緊急的 correctness blockers（舊稽核，須現時復驗）

| 問題 | 潛在後果 | 優先修復方向 |
|---|---|---|
| 個股法人、外資備援／月營收缺值 `fillna(0)` 或 0 分 | 虛構無買賣、無成長、誤評分 | 先 fail-closed、保留 missing，再 targeted tests；**不要**直接改投資分數，需 High Gate |
| 財報現金流累計/單季混算、缺科目 0 | 財務健檢與改善判斷錯誤 | 先欄位口徑與日期 parity，修分母、期間、缺值；不偷改正式門檻 |
| ^TWII MA200 不足根數回落現價、BIAS240/PCR 代理值入 Risk Cap | 假年線、代理資料影響正式判斷 | 取消假值與 proxy 計分，Risk Cap/公式更改需 High+全 QA |
| VIX 未收盤值當盤後、期貨與 MA5 不同資料日 | 同日比較不成立，風控紅線失準 | 以 exchange timezone／交易日/資料日對齊，必要時 unavailable |
| Registry session `data_registry` 與 New UI2 Real Feed 混用 | 將某一 session 未更新誤視為外部來源全面故障 | 為🗂資料頁建立來源健康 vs capability/wiring vs evidence coverage 的三軸檢查，且標 observation_date vs fetched_at |
| AI 超 Token 只吃 Top-N | 漏掉負面證據，誤判完整 | required manifest/coverage、批次唯讀回查、partial，不能 silent truncate |

## C. 三路線與排序

| 路線 | 正確性 | 速度/Token | 建議 |
|---|---|---|---|
| 1 修復/承接現有官方或已核准 adapters | 最容易保留出處/合規，先處理缺值/時間口徑 | 最快/最省 | **首選** |
| 2 在同源下做薄 L3 adapter 與歷史批次資料校驗 | 可以解決只有舊 UI 有的 producer 或 headless Digest | 中等 | **第二** |
| 3 引入新官方 API、付費授權或人工研究 Evidence Sheet | 涉及授權、維護與資料成本；正式 Gate 必要 | 最慢 | **只有 N0 且必要時** |

MCP 只能改善「工具怎麼訪問」，**不能創造來源不存在的真實資料**。對正式評分與風控必要的 N0，優先調查一手來源；無官方/可驗證來源即保持資料未備、Research-only，不偷偷用代理值。

## D. 可持續記憶（GitHub durable memory）與刪除邊界

1. GitHub 五檔職責固定：`PROJECT_RULES` 方法與停手；`DECISIONS` 客戶裁示及 supersession；`BACKLOG` 未完成事項；`PROJECT_STATE` **目前有效**的專案知識；`HANDOFF` 當下接手點。不要另建記憶權威，也不直接覆寫聊天記錄。
2. 歷史 DEC、舊框架與線框**不得物理刪除**；以 `SUPERSEDED / HISTORICAL` 和一個最新 Active Contract 明確取代，避免 Claude 讀取過時條文；專案記憶摘要只引用有效最新版本。
3. 待 #1030/#1032 和本草案協調通過 Gate，才以**獨立最小 patch**更新五治理檔／原規格，保留原始決策來源，附驗收／回歸證據及 supersession map。
4. **客戶澄清（2026-11-06）**：「記憶」特指 GitHub 內保存的 ChatGPT 與客戶討論、裁示、設計及跨對話交接的**專案長期知識**，**不指 ChatGPT 帳戶的 Memory**。治理範圍是 repo 中 `docs/PROJECT_STATE.md`、`docs/HANDOFF.md`、`docs/DECISIONS.md`、`docs/BACKLOG.md`、`PROJECT_RULES.md` 及各主題 handoff/歷史討論引用（例如 `docs/vnext/ONEBRAIN_HANDOFF_STATE_2026-10-31.md`）；保留歷史決策，將不再適用的設計與舊狀態標為 SUPERSEDED，從當前有效摘要/接手點移除或更正，避免新 ChatGPT/Claude 誤認舊版為最新。**不應對使用者要求操作 ChatGPT Memory 設定**。
5. 交接與換對話規則依 #1032 避免重複：可預見上下文丟失風險時主動提供完整新對話提示；重大決策在有授權/連線時及時 GitHub checkpoint；不可承諾平台斷線後自動存檔。

## E. 下一批 Gate / 驗收條件

- **D1 規格收斂**：比對 main + #1022/#1027/#1029/#1030/#1031/#1032，形成唯一生效 SSOT 與正式 supersession map；獨立 QA 確認歷史不可誤施工。只有安全 docs-only 內容可先審。
- **D2 資料來源 live probe（唯讀）**：對每類來源記錄 `source_id`, producer, URL/endpoint (no secrets), requested range, HTTP/API outcome, error category, actual observation_date, fetched_at, field coverage, freshness, downstream consumer, fallback success and evidence, provider terms。**單次 403/timeout 不等於永久 unavailable**；無網路標 NOT_TESTED；credential/環境差異分開。
- **D3 風控及財務 correctness**：先 High-effort targeted evidence+parity+mutation，改任何 Risk Cap、計分公式、source/schema、auth 前必須獨立正式 Gate，不偷改。
- **D4 體驗與完整性**：🗂資料頁分「來源健康」「接線狀態」「證據覆蓋率」；📊🎯💼 頁只有關鍵異常、日期與來源；UI 精簡但 Digest 不刪事實。
- 新需求不能悄悄夾入 Claude 的 UI 主線工作；共檔衝突一律先停。

**本檔尚未完成：** production live probe、獨立第二組 QA、CI、新規則正式 main 合併。不得把上一個 2026-10-23 audit 的 🔴 視為 2026-11-06 API 現在不可用。


## F. 2026-11-06 客戶對「GitHub 對話記憶」的澄清與更新作業

- 本次「清理記憶」的對象是已存入 GitHub 的 **ChatGPT ↔ 客戶討論成果**，不是更動模型、平台帳號記憶或刪掉聊天。
- **保存歷史（Evidence）與有效記憶（Active）分離**：DEC 原文、歷史 handoff、舊藍圖/討論摘要保留，以 supersession 引用鏈標記；`docs/PROJECT_STATE.md` 只保留當前有效產品方向／限制／來源；`docs/HANDOFF.md` 只保留可接續工作；避免逐字對話堆積、雙重 SSOT、以舊 PR 當完成。
- 本次清理的具體錯誤示例：若 PROJECT_STATE／HANDOFF 仍稱「正式只有四頁」「手機抽屜、桌機 rail」「資料健康度在我的頁」「六個互不相連 AI」「固定 3/6/9 個月」「大盤 EPS×PE 已可出正式價位」，應更新為最新客戶方向或研究中/未核准狀態，並標出取代 DEC/PR。凡描述「已施工／已合併／已修資料」必有 GitHub main/diff/CI 證據，否則降為 Draft/Proposal。
- **不要把本 Draft 當成清理完成**：這份獨立檔案先提交具體取代清單。現有 #1030/#1032 也涉及 PROJECT_RULES/HANDOFF/DECISIONS；只有在 owner 協調、獨立 QA、CI 完成後，才可於正式治理文件落實，不得在其他 PR 仍同檔修改時直接覆蓋。
- 下次對話啟動：先查 main/PR/CI 與正式五檔，再看 supersession map、可追溯的新設計與缺料清單；禁止從歷史逐字聊天恢復已被較新客戶決策取代的規格。
