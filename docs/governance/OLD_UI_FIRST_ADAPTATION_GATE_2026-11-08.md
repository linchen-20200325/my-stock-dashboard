# Old UI First — 新頁面設計與資料能力的前置參考治理規則

> 2026-11-08 客戶直接指示：**每次開始規劃新頁面時，先參考舊 UI 的頁面設計、功能與操作流程；涉及資料能力時，再查舊程式如何取數，最後依現行 New UI2 設計與資料架構改良，而非直接照搬**。本檔為此裁示的可稽核治理規則；不構成新產品功能、來源、公式、布局或正式投資訊號的施工授權。合併 main 後生效；如與上位 `CLAUDE.md`、`PROCESS.md` 或較新正式 Decision 衝突，依既有位階處理。

## 1. 新頁面／重大功能啟動的五步驟（必走，不重複已核准 Gate）

每當**開始規劃新 UI2 頁面或重大功能擴充**，先依序執行五步驟。這是「先設計、後施工」的前置流程，並非要求每次重新核准已通過的 Layout。現行五頁 📊市場／🎯標的／💼持股／👤我的／🗂資料、Dark-only、Mobile-first、頂部兩列導覽已核准，**直接沿用**；只有新布局、欄位增減、分頁動線或新商業語意才啟動相應 Wireframe／Decision Gate。既有純修 bug、無頁面／能力設計變更的最小修正，按原有治理 Gate 走，不強迫製造新線框。

1. **確認新頁面目標與已核准規格**：寫清楚使用者任務、頁面輸出與成功條件；區分已核准／待裁示／僅研究候選，查最新 main、Open/Draft PR 與有效契約，避免重做。新設計才送 Wireframe／Decision Gate，已核准項目不重審。
2. **盤點 Old UI／Legacy New UI 與共用資料層**：先檢視相應舊頁面設計、資訊架構、標題、欄位、圖表、互動、篩選、例外與缺值處理，以及舊 UI 是否有新 UI2 尚未承接的有效功能。若涉及資料，追到實際 caller → L3 service → L1 fetcher → source／fallback → schema／tests；檢查 API、Proxy／NAS、Token 引用、Retry、快取、計算、時間與證據資格。沒有舊對應功能時，明記「無對應」而非臆造。
3. **比較保留／改善／捨棄與至少三個方案**：對每項舊功能說明保留或改良的理由；就實作路徑比較「A 重用既有 canonical 能力／B 薄唯讀 adapter／C 新建或替換來源（需核准）」的正確性、風險、速度與 Token 成本，並推薦最省成本且合規的方案。不能只因舊版寫得不同就全部重寫。
4. **設計最適合 New UI2 的方案**：手機首屏可操作、資訊層級清楚、圖表優先但不堆卡片；資料層與 AI 推理層分離，沿用唯一正式計算與確定性行動權威。資料或登入尚未接線時誠實標示。不得照搬舊 UI 的 layout、Streamlit/session 邏輯或未驗證公式；若涉及新 Layout、Schema、來源、排名、Risk Cap、PIT 或 OneBrain runtime，停在相應客戶 Gate。
5. **獲授權後施工 → 非作者獨立 QA → 最新 head 原生 CI → 合併 → 驗收**：Claude Code 依既有分工分批實作，驗證舊／新行為差異、資料資格、手機與桌機、實際互動及回歸；QA／CI 過後才依既有 merge 規範合併，更新 GitHub 正式紀錄。未通過 Gate 不得推進正式環境，不將 CI 綠等同真實資料或部署驗收。

## 2. 舊設計及取數能力如何現行化（禁止機械複製）

每批至少留下「舊頁面／功能 → 新 UI2 目標 → 保留／改善／捨棄理由」對照。研究舊版時確認：

- **設計與互動**：舊版資訊分組、圖表、使用者操作順序與重要例外；依已核准五頁契約重新組織，避免功能流失，不恢復 Drawer／rail／JS_V4。
- **來源與網路**：API endpoint、dataset、參數、合法權限／憑證引用（不讀出秘密）、quota、Proxy／NAS／Session、HTTP／JSON status 判讀、Retry、timeout、冷卻、快取及 fallback；不得為了 DRY 破壞舊版曾有效的不同路由／錯誤處理。
- **語意與資格**：欄位、單位、月季歸屬、公告／觀測／抓取時間、provenance、as_of、freshness、PIT、missing、schema；**程式存在 ≠ 今天實測成功，曾抓到資料 ≠ 能直接作正式投資證據**。
- **新架構接線**：經驗證的 L1／L3 canonical service 優先；必要時使用薄唯讀 adapter → UI2 Evidence／VM／Decision Digest，不讓新 UI2 import `app.py` 或舊 render；AI 不自行取數或寫回。

既有路徑可先查 `app.py`、`src/ui/tabs/`、`src/ui/views/`、`src/ui_v2/`、`src/data/`、`src/services/`、`shared/` 及 tests，但不是全量清單。未驗證資料需明示 NOT VERIFIED，不得用 0、中性、安全或已驗證補洞。

## 3. 已發現的具體舊能力（實碼入口，非當日可用性證明）

| 需求 | 先檢查 | 現行化注意事項 |
|---|---|---|
| 月營收 | `src/ui/tabs/tab_stock.py`、`src/compute/health/fin_trend_score.py`、`src/data/stock/monthly_revenue_fetcher.py`、`src/data/core/finmind_client.py` | FinMind 及 TWSE/TPEx OpenAPI fallback 已存在；OpenAPI 只給最新月份快照，不可當完整多月歷史。收入單位、月份鍵與 PIT 必重驗 |
| 其他 FinMind 資料 | `src/data/core/finmind_client.py` 的保留例外／舊 caller | 部分呼叫依賴 Proxy Session、重試與不同 status 規則，不能機械改用 plain requests |
| 季財報／缺貨 | `src/data/stock/quarterly_financials_fetcher.py`、`src/services/shortage_screener_service.py` | 缺會計科目保留 None，不能當 0；公告日、資料資格與 PIT 另驗 |
| New UI2 真資料橋接 | `src/services/ui2/real_feed.py`、`src/services/ui2/real_canonical.py` | 既有 feed 讀取範圍有限；舊 UI 已有 ≠ 新五頁正式接線 |

## 4. 最小三方案比較與核准門檻

| 方案 | 正確性／風險 | 速度與 Token | 適用 |
|---|---|---|---|
| A. 重用已有 L1/L3 資料能力 | 通常最低（仍須驗證） | 通常最快最省 | 預設優先 |
| B. 保持舊來源行為，增加最小唯讀 adapter 對齊 UI2 canonical 契約 | 中低（需比對資料及例外 parity） | 中 | 舊能力有效、介面不合 |
| C. 重新設計 fetcher／新增 API／更換來源 | 風險與成本最高 | 較慢、Token 高 | A/B 證明不足、且通過 Decision Gate |

交付前留下五步驟完成證據與最小 Evidence Matrix：頁面任務／已核准設計契約／Wireframe 或 Decision Gate（如適用）／三方案比較／`main SHA`／舊頁面設計與功能對照（保留／改善／捨棄）／舊路徑及 symbol／正式 source／實測與否／欄位・單位・日期・PIT・freshness／ fallback 等價性／UI2 接線狀態／Evidence 覆蓋／A-B-C 決策／targeted tests／非作者 QA／最新 head 原生 CI。未實測者明示 **NOT VERIFIED**，不要憑程式存在推斷成功。

## 5. 硬性邊界

- 本規則增加「新頁面／重大功能啟動時先查已核准規格、舊設計與有效功能，再三方案比較、現行化設計、授權施工與驗收」的五步驟義務；**不**授權新來源、API 付費、實際部署、修改正式公式、權重、百分位、候選資格、Risk Cap、OneBrain runtime、PIT、歷史凍結資料或 UI layout。
- Missing ≠ 0、unavailable ≠ neutral、not evaluated ≠ safe；缺 token、無現時觀測、非等價 fallback、未驗公告時點等均不得冒充有效證據。
- 若 A/B/C 涉及客戶 Gate，停在研究與提案；資料與 AI 推理分離，不得 AI 自行抓取或回寫正式資料。
- `#1038` PIT 阻塞仍 NO MERGE；`#1034` 舊治理 Draft 須逐項核銷。現有 `#1085` 交接 PR 不因本規則自動合併或視為最新。
- 與其他治理文件的引用索引、DEC 編號／五檔同步依既有變更流程另做精確更新，避免同檔競爭；不可把本檔當第二套進度 SSOT。
