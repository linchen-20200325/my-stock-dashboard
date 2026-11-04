# New UI2 × OneBrain：完整 Evidence Coverage 驗證計畫（2026-11-04）

> **性質**：僅稽核計畫，**不是**第二套 Decision Digest schema、不是新增來源或投資規則、不是 OneBrain runtime 開工授權。既有最高原則請直接引用 PROJECT_RULES §30／NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md §8：「UI 簡化而完整 Decision Context 不減少」。客戶再次確認：以提供的四頁圖片為 UI 視覺主要參考；OneBrain 必須消費已核准且驗證的**完整資料與反證**，而非 Human UI 所呈現的 Top-N、卡片或文字。
>
> **同步狀態**：本批基準 main 801fe60e（#1012 已合併）；#1013 是尚待合併的視覺基準／頁數彈性文件 PR。本文件不動 #1013，也不改 P6／導航/程式。此表的「應驗」不是已通過的 coverage；repo 目前已明確記錄市場位階完整說明、指標明細、個股 lookup 基本面與估值等 Digest 缺欄／未驗。

## 1. 維持單一資料與雙投影架構

Sources → Validation / Normalization → Canonical Facts → Deterministic Rules → Risk Cap / System Action → Complete Evidence → [A: Human UI; B: Headless Decision Digest / OneBrain]。

- **UI**：採客戶參考圖的卡片、緊湊結論與圖表層級。可移除可見明細、合併重複大/小圖，但不得刪除上游 facts、缺值、provenance、正式判定、反證。
- **OneBrain**：以完整、機器可讀、可追溯的 Digest 接收已核准資料；禁止靠畫面渲染、Session UI、FAKE 情境、Top-N、截圖或 browser DOM 代替正式輸入。
- **資料未接**：Digest 必須能表達缺少／過期／來源不可用／未評估及 Capability 未接線（兩軸分離），不補 0、不補今日日期，不將 not evaluated 解釋成 safe。
- **投資建議**：OneBrain 可依正式事實與反證做風險、機會、情境與可能的下一步分析；**不得自己取代 System Action Authority**，不得推翻 Risk Cap。資料不足時降級為「無法判定／待補資料」，不能強行建議加碼、減碼或安全。
- **Token／成本**：完整是**語意與覆蓋完整，不等於每次把全部 raw 時序、表格、原始 HTML/JSON 巨量貼進模型**。應使用正式 evidence 的完整結構、必要統計、可追溯引用與按需讀取；任何摘要壓縮都要有反向 coverage／lossless-for-decision 驗收。

## 2. 每域必建 Coverage Matrix（待獨立讀碼回填）

| 域 | 要逐項核對的正式 evidence 類別 | 已知風險／限制 | 狀態 |
|---|---|---|---|
| 台股大盤／市場 Regime | 最新／歷史價格、資料日、位階、來源分支、完整 WHY、缺廣度原因、反證 | L0 完整位階說明在 VM；Digest 是否涵蓋未證，且可能缺欄 | 待稽核 |
| 核心總經／國際 | VIX、利率 2Y/10Y、利差、DXY、PMI／景氣、國際指數、資料新鮮度、口徑 | VIX／TWII 有兩路徑待選；利差 tenor 未定；PMI 不可混 ISM/台灣/NDC | 待稽核 |
| 市場廣度／產業 | 漲跌家數／廣度、產業強弱、法人資金流、來源期間、可靠性 | PORT／來源及 session readiness 多處未接 | 待稽核 |
| 個股基本面 | 營收、EPS（財報年度／TTM／預估 basis）、六維狀態、跨季序列、資料缺漏 | Lookup 的基本面與估值是否進 Digest 未證；跨季作為使用者功能仍 Pending | 待稽核 |
| 估值／價格／籌碼 | P/E、負 EPS 與口徑、估值對照、股價序列、法人／融資數據、限制與反證 | 不新增合理價或目標價；不從 VM 卡片補成 canonical | 待稽核 |
| 選股／雙軌候選 | A 成長／B 價值正式條件、排序、全部候選與淘汰證據、Data Gap | Top10 只是 UI；OneBrain 不能把 Top10 當全候選池 | 待稽核 |
| 持股／Portfolio | 每檔部位、成本／價格／市值、幣別、Sheet 日期、現金與分母、績效與產業曝險 | OAuth Gate；曝險分母缺欄，不能假裝已確認 | 待稽核 |
| Risk Cap／System Action | 唯一正式結果、限制原因、RuleIDs、來源、未評估／不可判定及 opposing evidence | 正式上限與動作 Aggregator 仍有 Gate；不能由 OneBrain重算 | 待稽核 |
| 事件／資料健康 | 已核准事件、來源、as_of／freshness、缺值／proxy、source health 及反證 | retrieved_at、source health 等可能無 canonical；不新增假欄 | 待稽核 |

以上均是**檢查項目而非「目前有」的宣告**。任何域不存在正式 contract 的欄位＝Gap，不得冒充已接線。每個 evidence 項的追溯至少填：domain／fact_id／canonical service+field／source／as_of／quality state／rule or formula reference／digest builder path／coverage yes/no／reason／test evidence。

## 3. OneBrain Coverage Gate：測試要求

1. **雙向 lineage**：從 canonical 的每個應納入 fact 追到 builder、serialized Digest 與 OneBrain consumer；再從 Digest 每個值逆查唯一 canonical 來源、資料日與轉換；禁止暗中第二條計算。
2. **非 UI 依賴**：隱藏／移除 Human UI 的 L2/L3、調整圖卡或新增頁面，不得減少 Digest 的已核准 evidence；headless builder 不 import New UI2 presentation。
3. **完整而非大 blob**：對每一域列 required／available／missing／blocked counts，並附不可壓縮的 rule / counter-evidence / provenance / freshness 欄。能分段傳模型，但不得以 UI top-N 作唯一資料。
4. **狀態矩陣**：OK、Missing、Stale、Unavailable、Not Evaluated 與 Capability 未接線，逐一驗證 AI 分析降級與禁止的動作；未接線不冒充 Data State。
5. **強制留反證**：負面事件、基本面惡化、估值過高／資料不一致、集中度風險等若正式 evidence 存在，摘要／傳輸不得只挑利多。
6. **沒有 runtime 就不能標 PASS**：目前缺欄仍屬 open；builder static import/AST 檢查只證明沒有明顯直接相依，不能代替實際 payload diff 和動態匯入檢查。
7. **回歸與 mutation**：刪去 builder 的一項 required evidence、改資料日、把 missing 補成 0、只給 UI slice，須使 coverage tests 紅；移動 UI 卡片不得使 tests 紅（獨立投影）。

## 4. 三方案比較：先審再修

| 方案 | 速度／成本 | correctness | 建議 |
|---|---|---|---|
| A 讓 OneBrain 直接讀四頁 UI VM 或畫面 | 初期快 | 會漏被隱藏／非 Top-N 的 facts、rule trace，違背 §30 | 禁止 |
| **B 稽核既有 headless builder → 完成 Coverage Matrix → 只補缺漏的正式 Digest pipeline** | 最小必要修改，便於測試 | 可保持單一 authority、缺值/provenance、精準 Gate | **選定研究方向** |
| C 重寫所有資料層與 Digest | 大量工作／回歸風險 | 無證據必要 | 不採 |

**實作分界**：本文件只做設計與核查規格。若稽核發現 Digest schema 缺欄、跨模組 Data Contract、公式、Risk Cap、System Action 或新來源，需另案 Decision Gate，建議 Opus High。未授權不得寫入正式 OneBrain runtime、部署或新增 AI API 消耗。

## 5. 與 UI 模板收斂／自由比較圖的協作

- 外觀主模板以使用者提供四面板圖為準；可擴頁但需功能責任與線框核准。#1013 合併前以該 PR 作設計候選，不能宣稱已落 main。
- 市場自由比較圖為 Human UI 的互動 projection：標的/期間的選擇不得限制 OneBrain 可見的正式市場／反證資料，也不能用選取的兩三條曲線取代完整市場 Context。
- 大小圖去重只改 presentation，所有正式 series／歷史資料與 metadata 繼續保留於 canonical／Evidence；圖未接真序列時只可顯示尚未提供。
- P6 Data Health、DEC-134 drawer、P7 auth shell 與本 Coverage Gate 分批，避免同改主 layout 或 auth。

## 6. 近期可安全派發的下一步（不在本 PR 施工）

1. 先完成 #1013 文件驗收／合併，並核對與 #1012 決策順序。
2. 獨立 read-only 掃 builder、canonical、Digest consumer 的實際進出欄（至少市場位階 WHY、16 指標、個股 lookup 基本面/估值），形成可追蹤的 Coverage Matrix，不提前補 schema。
3. 報告 Ready／Blocked／Need Decision 與具體三項最優先缺口；需 schema/新來源/投資公式才另送 Opus High Gate。

**驗收聲明**：本 PR 的 PASS 只代表此計畫文件已 QA；**不代表 OneBrain 已取得完整資料，也不代表 AI 建議功能已上線**。