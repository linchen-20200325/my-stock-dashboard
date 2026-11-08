# Old UI First — 新頁面設計與資料能力的前置參考治理規則

> 2026-11-08 客戶直接指示：**每次開始規劃新頁面時，先參考舊 UI 的頁面設計、功能與操作流程；涉及資料能力時，再查舊程式如何取數，最後依現行 New UI2 設計與資料架構改良，而非直接照搬**。本檔為此裁示的可稽核治理規則；不構成新產品功能、來源、公式、布局或正式投資訊號的施工授權。合併 main 後生效；如與上位 `CLAUDE.md`、`PROCESS.md` 或較新正式 Decision 衝突，依既有位階處理。

## 1. 必查前置 Gate（不可跳過）

**每次啟動新頁面規劃或設計之前**，先檢視 Old UI／Legacy New UI 的相應頁面：資訊架構、標題與分組、卡片和圖表、欄位／指標、操作動線、篩選及互動、重要提示與缺值狀態；列出哪些有效能力應保留、哪些應改良、哪些不宜沿用。涉及資料欄位、真實接線、API 缺值、連線失敗或權限問題時，再定位真正的 data caller、fetcher、service、fallback、測試與來源紀錄。先查現行 main 及 Open/Draft PR，避免重做或踩到並行修改。不得以「新 UI 尚未接線」推論外部無資料，也不得以「舊 UI 曾抓得到」推論今天還抓得到、可合法當 PIT 證據。

路徑範圍（依當時 repo 真實性調整，不是硬編碼的全部清單）：`app.py`、`src/ui/tabs/`、`src/ui/views/`、`src/ui_v2/`、`src/data/`、`src/services/`、`shared/`、相關 tests 和已合併資料契約。**舊 UI 是設計與資料能力的優先參考，不是新版的版型規格。保留現行已核准的五頁、Dark-only、Mobile-first、頂部兩列導覽；不復活 Drawer／rail／JS_V4，不令 New UI2 import 舊 render 或 `app.py`。**

## 2. 先學原理，再現行化；禁止直接複製

先完成「舊頁面設計／功能 → 新 UI2 目標 → 保留／改善／捨棄及理由」對照；如涉及真資料，再按「舊畫面 → caller → L3 service → L1 fetcher → 外部 source → fallback → schema／證據」畫最短呼叫鏈；確認：
- 頁面設計：舊版如何安排主要資訊與次要資訊、操作順序、使用情境、資訊密度與視覺層級；以現行五頁視覺契約與手機首屏可操作性為改良基準。版型、欄位、分頁動線若有變更，仍須先送 Wireframe／Decision Gate。
- 資料源：API endpoint、dataset、參數／stock_id、授權及憑證引用位置（不輸出值）、限額、合法性與當前是否可用。
- 網路行為：HTTP vs JSON status 判斷、Proxy／NAS、Session／Retry、timeout、錯誤分類、冷卻與快取、降級來源是否同等口徑。
- 資料語意：原始欄位／單位、月／季歸屬、發布日與觀測日、as_of／captured_at／fetched_at、provenance、freshness、PIT、missing／schema 與可重現性。
- 舊 UI 原本的資料如何進入計算與呈現，以及 New UI2 的 canonical Evidence、VM、Decision Digest 是否已接線。

**建議實作方式**：最大限度重用通過資格驗證的現有 L1/L3 canonical 能力；必要時做薄唯讀 adapter 轉成 UI2 現行契約；確定不可用、且有正式授權及證據時才新增／替換來源。禁止直接把舊 UI 的 Streamlit/session、舊 layout、未驗證 cache、字串、互動、計算／Ranking 邏輯移入 UI2；不得為程式碼 DRY 而丟失現有 Proxy／Retry 或悄改 HTTP status 判定。

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

交付前留下最小 Evidence Matrix：`main SHA`／舊頁面設計與功能對照（保留／改善／捨棄）／舊路徑及 symbol／正式 source／實測與否／欄位・單位・日期・PIT・freshness／ fallback 等價性／UI2 接線狀態／Evidence 覆蓋／A-B-C 決策／targeted tests／非作者 QA／最新 head 原生 CI。未實測者明示 **NOT VERIFIED**，不要憑程式存在推斷成功。

## 5. 硬性邊界

- 本規則增加「新頁面先參考舊設計與有效功能；取數時再參考舊作法、分析差異並以新架構合規重用」的義務；**不**授權新來源、API 付費、實際部署、修改正式公式、權重、百分位、候選資格、Risk Cap、OneBrain runtime、PIT、歷史凍結資料或 UI layout。
- Missing ≠ 0、unavailable ≠ neutral、not evaluated ≠ safe；缺 token、無現時觀測、非等價 fallback、未驗公告時點等均不得冒充有效證據。
- 若 A/B/C 涉及客戶 Gate，停在研究與提案；資料與 AI 推理分離，不得 AI 自行抓取或回寫正式資料。
- `#1038` PIT 阻塞仍 NO MERGE；`#1034` 舊治理 Draft 須逐項核銷。現有 `#1085` 交接 PR 不因本規則自動合併或視為最新。
- 與其他治理文件的引用索引、DEC 編號／五檔同步依既有變更流程另做精確更新，避免同檔競爭；不可把本檔當第二套進度 SSOT。
