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

## G. 2026-11-06 追加：第一版缺貨/財報跨期能力「已存在 ≠ 已可安全重用」核對

本節是本次使用者追問「不能取得的資料須篩選、產業缺貨、財報變化與舊版 UI 重用是否真正執行」的獨立讀碼證據；**尚未執行 production API、並未改正式公式或接 New UI2**。

| 模組及錨點 | 已有能力（FACT，GitHub main 讀碼） | 需要額外驗收或未完成 |
|---|---|---|
| `src/services/shortage_screener_service.py`＋`src/compute/screener/shortage_screener.py` | 先全市場月營收動能候選，再深掃至多 50 檔；合約負債、毛利率、存貨天數、月營收 YoY 四代理指標評分，金融業排除，部分缺季資料有降級 | **它評的是財報「疑似缺貨足跡」，不是已證實產業缺貨或大單**。需要官方公告/法說/訂單事實證據及供需反證，並標區分 inferred/verified；實時來源驗證尚無 |
| `shortage_screener.py::_score_revenue_yoy` / `score_shortage`，`shortage_screener_service::_score_and_diagnose` | C4 月營收缺失時回 `0.0`＋「資料不足」原因，其他 C1–C3 可照算且仍列 rankable（如果總分符合 tier） | **Data Gap Gate**：確認 UI/Digest 是否只顯示「疑似」、保留分項 missing 旗標、coverage 與降低可信度；絕不能讓 C4=0 被呈現為真實零成長。另審查主排名/閾值是否應 fail-closed；公式/語意改動需 High Gate |
| `src/compute/health/fin_trend_score.py` | 月營收 65%＋近季財報 35% 的既有跨期趨勢模型，完整分項 detail，可給 OneBrain 研究證據 | `compute_monthly_revenue_subscore` 缺資料/缺 YoY 回 `0.0`＋ reason；`compute_fin_trend_subscore` 季數不足回 `0.0`＋ reason；`compute_trend_score` 直接合權重且 `_label_from_score` 可能產「中性」。**不能在資料缺口下把總分零/中性當經驗證的營運平穩**。需 coverage gate / mandatory data / missing-neutral mutation tests |
| `src/compute/health/fin_health_diff.py` | 比較兩期體檢的改善/惡化、盈轉虧/虧轉盈，未知狀態 `_score` 回 None 跳過 | 需確認兩期財報期間一致、會計口徑、樣本完整度、無資料不得宣稱穩定；連結 `DH-FIN-HEALTH-CF` |
| `src/services/financial_health_engine.py` 及 L1 financial statements fetcher | 原有財報體檢模組、現金流/獲利/負債等指標 | 舊稽核 `DATA_HEALTH_AUDIT_2026-10-23.md` 曾指出累計/單季現金流與缺科目 0、現金流比率口徑問題；最新 API 回應未實測，**不可整包當核准的 OneBrain 證據** |
| `src/services/ui2/real_feed.py` | 現時 New UI2 Real 模式僅正式唯讀讀 TWII 快照與市場位階快照 | **缺貨、跨期財報、集保、ETF、完整籌碼尚未接 UI2 的 approved feed/Digest**；不能因 HTML 有卡片或 legacy code 存在就算已接線 |

**稽核結果**：目前真正完成的是「初步模組資產盤點＋舊來源風險整理＋本次三處具體風險讀碼」；**不是**每一筆來源的 live reachability 測試、全面阻擋有問題數據、完整產業缺貨驗證、財務變化跨期正確性驗證或 New UI2/OneBrain runtime 接線。

**建議三段式、每批最多三項**（均需依當下 GitHub Gate、Claude Code owner 與授權決定）：
1. 先建「Legacy Capability × Source Health × Decision Safety」矩陣，對每個欄位 trace `producer → canonical → deterministic calc → Evidence Registry → Digest/UI`，將 `GOOD / LIMITED / UNSAFE / NOT_VERIFIED / NOT_WIRED` 分軸標記，不用單一綠燈掩蓋來源/公式/接線差異。
2. 先以測試固定缺貨 C4 missing→rankable 的情境，以及財報趨勢缺兩腿→neutral 的情境，開 High effort Risk/Data QA Gate；提出保留合法部分證據、禁止越級推論/正式動作的降級契約。**不要未裁示就改原分數公式或權重**。
3. 通過資料/財務可追溯與源端驗證後，逐批薄 L3 feed 接 UI2，完整 Evidence 給 OneBrain；🗂資料頁明確列出「來源不存在」「來源失敗」「資料不可信」「未接線」「已過期」，並保留原因與修復路徑。

## H. 2026-11-06 Claude 工程複驗勘誤與資料新鮮度阻塞（較本檔 B1/B2 舊稽核優先）

> **來源分級**：本節含 (1) 本次 ChatGPT 親自核對的 GitHub workflow 事實及 (2) Claude Code 回報的重現/靜態掃描；Claude 工程測試報告尚未由 ChatGPT 在相同環境獨立重跑。**不能把單組回報升格成獨立 QA PASS**。本檔以前引用 2026-10-23 audit 的缺口，不得推論 2026-11-06 main 仍有同一 bug。

### H.1 Cron write failure — 當前需要優先恢復的 production freshness

- **直接查到的 GitHub FACT**：2026-11-05 UTC、台灣時間 2026-11-06 的三個失敗 workflow：「Update Macro History (Daily)」、「Update Sector Flow (Daily)」、「總經燈號每日落地 (Weekdays)」，其 Jobs 都在 `Commit and Push Changes` 失敗；先前 fetch / capture 段未顯示失敗。當時 main `343f0e0e`。
- **workflow 原碼 FACT**：`.github/workflows/update_macro_history.yml`、`update_sector_flow.yml`、`update_macro_forward_test.yml` 的 commit 步驟均執行 `git push`、直接推送 checkout 的 main。
- **Claude 回報的日誌 FACT（待 ChatGPT 獨立取得該份 log）**：`GH006 Required status check "ui2-browser-gate" is expected`；因 branch protection 無法直接寫 main。Branch protection 規則「何時/由誰更改」未驗；未取得 Admin API 權限，不推定責任。
- **影響**：資料產生不等於已保存到 main。Claude 回報 `data_cache/twii_ohlcv.parquet` main 最後觀測 11-04；此項文件/內容日期仍需按實檔及 snapshot 再核。即使其他 workflow 綠也不得把新資料當已更新。日後每個資料產品必須揭露 last_observation_date / last_successful_published / freshness / status；不能用 runner 執行時間代替觀測日。

### H.2 先前 audit 過期或須修正的四項

| 本檔先前說法（歷史） | 最新複驗報告（Claude Code） | 處理 |
|---|---|---|
| 出口標籤錯把金額當訂單，仍未修 | 目前已修 | **改標歷史已修 / 需查 commit 和實際 UI 文字；不重開重複修復** |
| TWII MA200 根數不足時回落現價，仍未修 | 目前已修 | **改標歷史已修 / 需看缺樣本負測試；不據舊稽核下修生產程式** |
| 外資總經備援 fillna(0) 仍未修 | 目前已修 | **改標歷史已修 / 另查個股 data_loader 的 fillna(0) 是否仍存在** |
| ETF 回測已完全無讀者 | 仍有 1 個殘留讀取點（Claude 程式掃描） | **更正：功能頁退役但殘留讀者；查 live/dynamic import 後才可刪；不得宣稱完全零引用** |

以上為「舊稽核已過時」而非新資料來源已全部可用；**任何更正若無 GitHub 變更歷史/實測證據仍標待複核**。

### H.3 財務及缺貨模型新重現清單（Claude 提供）

| 優先級 | Claude 回報的可重現案例 | 待確認的正確性契約 |
|---|---|---|
| P0 | `compute_trend_score([], [])` 得 `0.0 / ➖ 中性` | coverage 不足 ≠ 中性；正式輸出需 `⬜ 無法判定` 或明確 degraded，不得當交易權威 |
| P0 | 缺貨 8 季但所有數值 None ⇒ 0 分、tier「不明顯」仍排入 | 必須辨識 `NOT_EVALUATED`，不可當「缺貨證據不足因此真的不缺貨」 |
| P0 待來源口徑 | 現金流由累計轉單季尚未完成 | FinMind 實際回傳口徑未現場驗證，先做 source period/unit/quarter reconcile + mutation；未驗不改公式 |
| P1 | 月營收 `[20,30,NaN]` 仍選 M-1 為末月 | 不能將較早的月份冒充最新月；日曆月份連續性必須被驗證 |
| P1 | 缺合約負債/存貨部分腿記 0 分 | 「未取得」與「真實低增長」需分開，評分資格先根據 coverage 降級 |
| P1 | 月/季缺腿仍以 0 加權得到 0.233「中性」 | 應 fail-closed 或明確 partial，不可補成中性 |
| P1 | `fin_health_diff` Warning/N/A/無共同欄位可能被判 stable | 不同型指標及缺欄必須有適用性門檻，`stable` 須有充分可比資料 |
| P1 | 月營收時間序列有洞，M-2/M-1/M 不是連續月份 | 依 observation_date 連續性對齊，不以列表位置作真實月份 |
| P2 | `fin_health_diff._score` 前綴匹配 | 目前無已證實誤判，列研究，不主張改程式 |

Claude 回報此批相關測試 **322 passed**；這只表示既有測試通過，不否認上列案例存在，更不能取代缺值、期間與語意的負測試；不得直接以其報告修改正式 Risk Cap/公式/權重。

### H.4 Evidence Registry / Digest 實作現況（依 Claude 逐項掃描，待正式獨立 QA）
- `Evidence Registry` 尚無 production 實作；`RULE_ID_ALLOWLIST` 只是 rule whitelist，不是證據儲存體。
- Decision Digest schema/builder/validator 已有基礎，但沒有 production caller；UI2 只顯示「尚未開放」。**不存在的 evidence 不能宣稱已被截斷**。
- Builder 存在 `MAX_ACTIONS=3` 候選截斷、無省略計數/原因；這與完整必需證據的要求潛在衝突。**重要區分：完整 evidence ledger 不等於全部 action candidates 應直接下單**。須依 separate ledger/candidate list、cap/omission/coverage contract 與 safety gate 設計，不可簡單放大 MAX_ACTIONS 導致改動唯一動作權威。

## I. 三方案與設計草案：保留 main 保護的 Cron 恢復 Gate

**客戶向 ChatGPT 交付 Claude 回報；本節記錄 ChatGPT 建議路線，尚不是 production workflow 改動授權。**

| 選項 | 安全與正確性 | 實施與成本 | 結論 |
|---|---|---|---|
| A 暫時取消 required `ui2-browser-gate` | 會降低所有 PR/寫入驗收 | 快但有保護回退 | 不採 |
| **B 每個 cron 寫入獨立資料分支→ PR→既有必要檢查→經授權 merge** | **不破壞 main 保護；可留下每次資料發布證據** | 中等，初期多 CI、需確認 Actions token/PR/自動合併 | **推薦** |
| C 指定 bot/特權 token 繞過 branch protection | 寫入快，放大權限且跳過必要檢查 | 低～中，但需要權限管理 | 不採 |

**B 的可施工草案，尚待權限及端到端 Gate：**

1. 三個 workflow 分開產出 deterministic、具日期的單一資料分支（例 `data-sync/<workflow>/<observation-date>`，以合法名稱及 collision policy 驗證），發 PR 到 main；用 per-workflow `concurrency` 避免相互覆蓋。checkout、更新、重試須處理 main 被別的 PR 推進、existing PR/head、Git conflicts；禁止 force push 與私憑證出 log。
2. **GITHUB_TOKEN PR 觸發限制**：GitHub 官方文件表示其觸發的 PR 檢查有可能需要授權者手動核准；不可假設「建 PR 即自動跑必需 CI」。先製作 read-only PoC 比較 GitHub App 安裝 token、細粒度 PAT 與是否可由既有受保護 branch 的 workflow 分發/批准；任何新 token/權限或付費應先經客戶裁示，**不能重用現有 OAuth/Sheets secrets**。
3. **合併 Gate**：真實 PR `ui2-browser-gate` 等 required check 全部 success、head SHA 未漂移、來源觀測日與 schema/單位/資料 coverage 完整、不可用時 fail-closed；對可安全按規則合併的 data-only PR 才考慮自動合併（權限另核准），禁止默默把 needed checkout approval 假設為自動完成。
4. **恢復/補洞**：先判定 2026-11-05 三種資料實際觀測日與提交缺漏；重跑取得**真實**來源值，記錄 `as_of`／`fetched_at`，禁止拿 11-06 的值回填成 11-05。資料 cache 無新增應區分休市／fetch 無資料／出錯；驗收必須證明 main 新 commit 已讀得到。
5. **成功定義**：三個每日排程至少各有一次無 bypass 經 CI 驗證的真實資料發布，main 讀回數據且下游 view health/freshness 可對帳；不得只拿 workflow run success 代表發布成功。改動 workflows/credentials/CI gate 屬獨立工程 PR；Draft/試運轉期間不停止舊資料監控，遇任何新權限、保護規則變更先停。

## J. PR #1035 獨立阻擋複驗（2026-11-06；GitHub + 官方文件）

> **GitHub FACT（本次驗證）**：main `343f0e0e`；PR #1035 Draft、head `dd3a1611add735f0d1a22186b8d7e9e6edeb6559`、6 files、PR Check success；真實資料 PR、main readback/發布仍 **NOT VERIFIED**。本節的結論取代 §I 對 `workflow_dispatch` 可能滿足 required check 的開放式假設。

### Critical — dispatch workflow check **不能**滿足 PR required checks

- #1035 `scripts/publish_data_pr.py` 以 `GITHUB_TOKEN` 建立/更新 PR 後執行 `gh workflow run pr-check.yml --ref auto/data-<job>`。
- GitHub 官方「Troubleshooting required status checks」明確說：`workflow_dispatch` 產生的 GitHub Actions jobs **不會算入 PR 的 required status checks**，即使在 head SHA 上全綠；要用 `pull_request` 或 `push` 等具資格的 event。官方：https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks
- GitHub 官方 GITHUB_TOKEN 規則：用 `GITHUB_TOKEN` 建立/更新 PR 可觸發 `pull_request` checks，但會進入**需要 write 權限者 approve workflows** 的狀態；此批准流程不可用 `workflow_dispatch` 的綠燈代替。官方：https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow
- **結論（BLOCKER）**：PR #1035 在原設計下不應 Ready/merge，也不應要求使用者先開 PR 建立權限，直到該錯誤路徑移除且安全資料語意 Gate 通過。

### Data safety blockers — #1035 helper 的實際程式邏輯

| 問題 | main/PR 程式證據 | 最低修復 Gate |
|---|---|---|
| **跨日 metadata 與 rows 不一致** | helper 檔頭承認分支未合併跨日時 `metadata.json.row_count` 可能仍是最後一次腳本產生的值，與 union 後 parquet 不一致 | 不能以「下一輪 main 自癒」當做正式資料正確性；需一致性驗收／fail-closed 或不產生可發佈的不一致資料 |
| **失敗／缺值被舊值回填** | `union_parquet_by_date()` 對相同 `date[+sector]` 的新列 `NaN/None`，從分支舊列回填有效值；若無明確 `carried_forward` provenance，可能把最新觀測缺失偷換成舊值 | 保持最新 missing status；需明示繼承策略/舊資料日時效/來源追溯並經正式資格 Gate；未授權時建議 fail-closed，不得 silent fill |
| **同樣時間戳不代表數值一致** | `is_substantive()` 忽略標記為 volatile 的時間欄，這只適用於 `updated_at` 等確定無業務語意的 metadata | 以實際 snapshot/觀測日/缺口狀態負測試；unknown keys/period 必須視為實質，絕不過濾真實資料錯誤 |
| **PR 防護與人工工作仍未驗證** | `GITHUB_TOKEN` PR 可能需 workflow approval；Repo `allow_auto_merge` 停用，日更需要人工審核/合併 | 先明示人工/低頻方案可接受範圍，不能把設計稱作全自動恢復 |

### 三條安全可行方案（供工程比較；不得自行啟用權限）
1. **A. GITHUB_TOKEN PR + 人工批准 pull_request checks + 人工合併**：不新增憑證，保護不變，但每日人工操作、須先確認 Actions PR permission；適合單次試運轉 Gate。
2. **B. 最小權限 GitHub App token 建 PR → 原生 pull_request checks → 經核准 auto-merge**：可降低長期操作成本，但新增憑證、權限與自動合併治理，屬另一個客戶 Decision Gate。
3. **C. cron 只推資料分支，人工用自己的已核准身分建立 PR**：不需 Actions 建 PR 權限，不新增 credential，但人工操作最高；適合 PR 建立權限受限時的緊急恢復。

**建議先採 A 作受控端到端 PoC**，把 `workflow_dispatch` 視為可診斷的跑測試但**不能**視為 required gate；保留真正 `pull_request` 事件與人工 approval，正式資料 PR head、required checks、合併後 main 讀回全鏈驗證後，再議長期全自動。不要取消 `ui2-browser-gate`，不要 bypass branch protection。

## K. PR #1035 後續獨立設計／程式驗收（2026-11-06；head `04e0d440`）

> **先前 §J 的合併阻擋已被工程變更針對處理**，不能永久將舊 head `dd3a1611` 當作當前 #1035 的狀態。本節是新的**靜態程式與 GitHub CI 查核**，不取代第一次真實 Actions Data-PR 端到端發布。GitHub main 查核時為 `343f0e0e`。

- **變更與 CI FACT**：#1035 仍 Draft、6 files，head `04e0d440f517b5e88d16b8caef059585991555a3`；GitHub workflow run `42213815447` 成功，Fast checks、Slow tests、ui2-browser 1.56.0／1.59.2 與 `ui2-browser-gate` 五 jobs success。**查核 repo PR diff 不等於本人本地重跑 37552 測試；Claude 獨立 QA 三輪屬其回報，仍待第一次實際發布 Gate。**
- **原錯誤已修**：`scripts/publish_data_pr.py` 不再 dispatch `pr-check.yml`，guard 阻擋 `gh workflow`／`gh pr merge`／`gh api ...dispatches`；三 cron 無 `actions:write`，但仍需 `pull-requests:write` 和 repo Actions 設定允許建立 PR。GitHub 官方：GITHUB_TOKEN 建 PR 時 `pull_request:opened/synchronize/reopened` 會產生**需人工批准的 workflow run**，正是預定 PoC 的路線，**不能假定一定需 Close→Reopen**。官方：https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow；required checks 只認合格事件，詳：https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks
- **資料程式補強**：`union_parquet_by_date` 逐 `date[+sector]` 對照，舊有值而新缺失/衝突會 `PublishError`、凍結帳本同 date 差異中止；metadata `row_count`、`last_updated`、`n_days`（可重算者）於 commit 前重算＋驗證；失敗回復主工作樹，未經確認不 push。新數值與歷史共同 key **若來源追溯修正會 fail-closed**，此為明確保守取捨，可能需要人工處理，不等同永久資料業務公式已正確。
- **驗收界限／未驗**：Repo Actions「Allow GitHub Actions to create and approve pull requests」是否啟用無管理權限核實；真實 GITHUB_TOKEN PR 建立、approval-required 原生 CI 與 required head SHA、人工合併後 main/parquet readback、下一次 cron 的 branch 存續／conflict、GitHub runner 真實失敗回復皆 **NOT VERIFIED**。#1035 變更上線只代表批准受控 PoC，不能說三 cron 已修復。
- **建議放行條件**：目前可**考慮將 #1035 轉 Ready 進入人工審查與合併 Gate**（仍需使用者授權），條件為 ① head 未再變、② repo PR checks 與必要獨立 QA 有證據、③ user 在 repo Settings 適度開啟 Actions 建 PR 權限（不得額外新 Secret/Bypass）、④ 現場先做 `dry_run=true`，再僅對 `macro-history` 一條非 dry-run，人工批准原生 `pull_request` workflow 後按實際 head/merge ref 確認 required Gate，再人工合併資料 PR 並驗證 main/parquet。任何失敗停在資料 PR；後續另二 cron 不得直接宣稱已通。
- **風險接受範圍**：資料 PR 每日需人工批准／合併，必要時 fail-closed 會維持紅燈；這是先保留 GitHub 保護的臨時方案，非「完全自動化」目標。其餘四個尚直接 push main 的 workflows 留獨立 BACKLOG，不能在本批擴大修改。§J 設計阻擋為**已修程式、未過真實發布 Gate**的歷史狀態。
