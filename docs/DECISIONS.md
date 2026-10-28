# DECISIONS — 裁示與正式決策紀錄（my-stock-dashboard）

> **位階**：本檔受 `PROJECT_RULES.md` 第 0 節約束。`CLAUDE.md`（資料完整性憲法，自稱最高準則）與 `PROCESS.md` **凌駕本檔**；本檔**不修改、不重新解釋**兩者任何一條。本檔條目與兩者牴觸時，以 `CLAUDE.md` 為準，並把牴觸登記到 `docs/BACKLOG.md` 第 4 節。
> **建立**：2026-10-16，Project AI Constitution v1.0 治理批（客戶 MSG 10 裁示，見 DEC-016）。
> ⚠️ **provenance 揭露（`CLAUDE.md` §-2 規則 6）**：本檔所有 DEC 條目由**單一撰寫組**依兩份獨立證據清單（文件／客戶裁示角度、git history 角度）合併、去重、交叉核對後撰寫，**待第二組獨立 evidence audit**。行號與 SHA 為撰寫組 2026-10-16 實測（`git show <sha>:<path> | sed -n`）；稽核通過後本註保留作 provenance。
> **登記不構成動工授權**（`CLAUDE.md` §-1）：一條裁示被記在這裡，不代表其所涉工作可以開工。

## 0. 怎麼讀

### 0.1 來源類別（每條必標）

| 類別 | 意思 | 可信度註 |
|---|---|---|
| **A** | repo 正式文件（`CLAUDE.md`、`PROCESS.md`、`docs/BACKLOG.md` Decision Register、`docs/v2/spec/*`）於 main | 正式文件；BACKLOG 的 DR 列自註「總管轉述」 |
| **B** | main 上的 commit／PR 訊息 | 多為 AI 撰寫的 commit 訊息轉述客戶裁示 |
| **C** | `HANDOFF.md`（分支 `claude/stock-dashboard-handoff-g9dtm0` @ `1510f3f0`）內「逐字收錄」之客戶裁示 | 該檔每則自註為**總管轉交、逐字未經第二組比對**；不在 main |
| **D** | 客戶本 session 原文，**本檔首次入庫** | 標「客戶訊息 <UTC 時間>（本 session；本檔首次入庫）」；引文逐字自客戶訊息 |

- 一條可同時有多類來源；**以最強者為主、其餘為佐證**。
- 路徑寫法：`path@sha8:行`。`H` ＝ `HANDOFF.md@1510f3f0`；`M` ＝ main `f0a6c474`（#863；其後 main 只有 cron 資料 commit，不碰 md，`git diff --name-only f0a6c474 origin/main` 實測僅 `data_cache/**`）。
- 本 session 的 MSG 4、MSG 8 是 AI 壓縮摘要，**不是客戶原文，本檔不引用**；MSG 9 的**前提**（股票 repo 有遺失的 Constitution 修改）已被 MSG 10 更正，該前提**不作 Decision 來源**；但 MSG 9 第 8 點的**禁止事項**（修改產品功能、修改投資公式或資料語意、刪 branch、force push、為了對齊報告而改寫 Git history 等）是客戶原文，**仍為有效來源**（`PROJECT_RULES.md` 第 10 節引用之）。

### 0.2 欄位

**ID**（`DEC-NNN`，永不重用）｜**內容**｜**範圍**｜**日期**（客戶裁示日）｜**決策者**（客戶／user ＝同一人，依原文用語；或「AI 總管內部」）｜**狀態**（生效／部分取代／被 DEC-xxx 取代）｜**來源**（類別＋位置＋≤3 行逐字）｜**取代鏈**。

### 0.3 不升格原則

- 證據不足、題意不明、只有方向沒有規則者 **不升格**，列在第 6 節並指向 `docs/BACKLOG.md` 第 4 節的 `CV1-*` 項。
- AI 的技術選擇不升格為客戶裁示（第 7 節列為 Fact）。
- 被取代的條目**不刪**，標狀態並寫取代鏈。

---

## 1. 治理（governance）

### DEC-001｜AI 總管只監督：一律派工、必須複驗、全稱句須第二組驗
- **內容**：每次任務由總管派對應 AI 執行；總管不自己寫實作；subagent 回報 ≠ 完成；調查／稽核多組獨立；總管自己的全稱句也要第二組驗或明說未驗。
- **範圍**：治理｜**日期**：2026-08-25｜**決策者**：user｜**狀態**：生效（`CLAUDE.md` §-2，凌駕全檔）
- **來源**：A `CLAUDE.md@f0a6c474:14`「2026-08-25 user 指派：**「每一次任務 AI 總管都要安排對應的 AI 去執行，AI 總管是負責監督的人」**」；規則 1～6 見同檔 §-2。B `7273cad3`、`4be897ec`（直推，無 PR#）。
- **取代鏈**：無。

### DEC-002｜沒實際 bug／沒具體需求 → 不要動
- **內容**：提議新工作前先驗是否在用、是否真 bug、ROI；user 沒指派 → 停手等指令。
- **範圍**：治理｜**日期**：2026-06-24｜**決策者**：user｜**狀態**：生效
- **來源**：A `CLAUDE.md@f0a6c474:1020`「2026-06-24 user 明確要求:**「沒實際 bug / 沒具體需求 → 不要動」**」；`:1041`「user 沒明確指派時 → **停手等指令**,不主動找事。」
- **取代鏈**：無。自主巡航（DEC-006／007）只在已授權範圍內，不是本條例外。

### DEC-003｜虛擬軟體公司運行規範 v3：內部自決區 vs 請示場景；UI 草稿先行
- **內容**：請示場景 ① UI/UX 線框草稿審批（版面、欄位增減、分頁動線異動前先提文字線框）② 商業需求衝突與不可逆操作；請示須附總管推薦方案與原因；其餘技術細節內部自決、不拋選擇題。
- **範圍**：治理／UI｜**日期**：2026-08-27｜**決策者**：user｜**狀態**：生效（v1 封存、v3 現行）
- **來源**：A `CLAUDE.md@f0a6c474:546-548`「2. 唯一允許向客戶展示與請示的情境 / * ① UI/UX 介面草稿審批（草稿先行原則）：任何版面佈局（Layout）、欄位增減或分頁動線異動前，必須先提「文字線框草稿（Wireframe）」供客戶拍板」。B `c794d2f0`（v1）、`56a36020`（v3）。C 2026-10-14 Q-z32＝A 重申：`H:1399`「依既有規則，涉及新畫面先提供文字線框給客戶確認，再實作。」
- **取代鏈**：請示範圍其後被 DEC-008、DEC-009 **擴充**（不是取代）。

### DEC-004｜merge PR 為常設授權
- **內容**：merge 這個動作本身已拍板，不必每次問客戶；其他不可逆操作仍須請示。
- **範圍**：治理｜**日期**：`PROCESS.md` 既有；2026-08-27 再裁維持｜**決策者**：user｜**狀態**：生效
- **來源**：A `PROCESS.md@f0a6c474:47`「- **PR 規範**：請直接 merge PR + 存檔 (STATE.md) 與同步 ARCHITECTURE.md、SPEC.md。」；`CLAUDE.md@f0a6c474:318`「2026-08-27 user 再次裁示**維持**）—— 故 merge 屬**已拍板**」。
- **取代鏈**：同句「存檔 (STATE.md)」與登記本的衝突從未裁示 → `CV1-DR-04`。

### DEC-005｜寫入端序列化、一次一檔；同一報錯連續重試 2 次未果即停機（跨 subagent 累計）
- **範圍**：治理｜**日期**：`PROCESS.md` 既有｜**決策者**：user｜**狀態**：生效
- **來源**：A `PROCESS.md@f0a6c474:31`「**並行處理（限唯讀）**…**寫入（改 code）仍嚴格序列化」；`:57`「針對同一個報錯，若連續重試 2 次未果，**立即停機**。」；`:61`「計數跟著錯誤走，不跟著 agent 走」。
- ⚠️ **決策者分層**：序列化與「重試 2 次停機」為 user 既有條文；`:61`「跨 subagent 累計」一款是 AI 編修組依 `CLAUDE.md` §-2 派工制補的連帶缺口（**AI 總管內部**，非客戶裁示）。
- **取代鏈**：無。

### DEC-006｜有限自主巡航＋防程式碼膨脹 Gate（Minimum Necessary Change 的 repo 來源）
- **內容**：每批 ≤3 項；不得創造新需求；必須停止 8 項（layout change／irreversible／touch L3 data layer／need new source／spec gap requiring invented wording／需要客戶裁示／同檔回修達上限／GitHub-CI 真錯誤）；能改既有函式就不新增、能重用就不新增相似元件。
- **範圍**：治理｜**日期**：2026-10-08｜**決策者**：客戶｜**狀態**：生效（停止條件與 DEC-008／DEC-009 併讀，取嚴）
- **來源**：C `H:133`「【運作模式切換｜有限自主巡航＋防程式碼膨脹】」；`H:150-151`「防膨脹 Gate：/ - 能改既有函式就不新增函式。」。D 客戶訊息 2026-10-16T08:00Z（本 session；本檔首次入庫）「依 Minimum Necessary Change 原則施工」。
- **取代鏈**：回報格式部分被 DEC-007 後續版本取代；其餘不變。

### DEC-007｜靜默自主巡航（回報模式）
- **內容**：沒有需要客戶決定的事時不輸出過程訊息，但持續執行已授權工作；只在「完整有意義階段完成」或「真正需要客戶裁示」時回報；不報「已派工／PR 已開／等 CI／沒有新資訊」等中間狀態；每批最多約 3 個高度相關安全項目。
- **範圍**：治理｜**日期**：2026-10-10、10-13 收斂；2026-10-15 重申｜**決策者**：客戶｜**狀態**：生效
- **來源**：D 客戶訊息 2026-10-15T13:40Z（本 session；本檔首次入庫）§24「每批原則：/ 最多約 3 個高度相關安全項目。」；客戶訊息 2026-10-15T13:53Z（本 session；本檔首次入庫）「只有以下兩種情況才回報：/ A. 這個完整 correctness 階段已完成… / B. 出現真正需要客戶裁示的問題。」。C `H:248`「只有 3 種情況可以主動回報」（2026-10-10）；`H:1036` 起〈恢復自主巡航〉（2026-10-13）。
- **取代鏈**：2026-09-26～10-09 歷代回報格式已逐層被取代（`H` 自註為編修組判讀，單組）；不逐條升格。

### DEC-008｜資料品質、資料來源與公式正確性治理規則（2026-10-10 長期授權）
- **內容**：可客觀證明的公式 bug 可最小修正＋regression；多種合理算法、門檻、權重、策略、訊號定義、模型假設 → 送裁示；缺資料依 Level 1（程式錯，可修）→ Level 2（核准備援）→ Level 3（研究新源）；**允許**研究／PoC 新 API／MCP，但**第一次接入正式投資資料鏈前**須驗 16 項；禁止假補值（填 0、昨值冒充今值、靜默沿用 cache、fallback 偽裝主源等）。
- **範圍**：治理＋資料語意｜**日期**：2026-10-10｜**決策者**：客戶｜**狀態**：**部分從嚴**（§五「可以直接進行的情況」由 DEC-009 從嚴，見取代鏈）
- **來源**：C `H:410`「客戶 2026-10-10〈資料品質、資料來源與公式正確性治理規則〉（逐字收錄…後續所有階段持續適用」；`H:505`「允許 agent 主動搜尋、研究、建立 PoC、測試與比較新的 API/MCP 資料源。」；`H:507`「但第一次接入正式投資資料鏈前，必須驗證：」。
- **取代鏈**：本條 §五 允許「同口徑高可信免費源」不問客戶最小整合；DEC-009（2026-10-15）把「新／替換資料來源、新 API / MCP」一律列入必須停下 → **暫行取嚴**（任何新／替換 production source 接入一律走 Decision Gate）；兩者關係未經客戶明示 → `CV1-DR-08`。研究／PoC 的許可**不受影響**。

### DEC-009｜必須停下裁示的事項（Decision Gate 清單）
- **內容**：新／修改投資公式；新資料語意；新／替換資料來源；新 API／MCP；正式 scoring／weight；Context → Core／hard Veto；正式加減碼比例；substantive AI behavior；重大 UI flow；irreversible operation；production switch；old UI deletion；branch deletion；credentials／account access；genuinely multiple reasonable directions；無法安全自行解決的 blocker。已裁示過的不重問；確認 bug 且只有一個安全修法可自行修。
- **範圍**：治理｜**日期**：2026-10-15｜**決策者**：客戶｜**狀態**：生效
- **來源**：D 客戶訊息 2026-10-15T13:40Z（本 session；本檔首次入庫）§25「必須停下裁示的事項 / 包括：/ - 新／修改投資公式」；同節「確認 bug 且只有一個安全修法：/ 未來施工階段可自行修。」。
- **取代鏈**：擴充 DEC-003、DEC-006、DEC-008；與 DEC-008 §五的寬嚴差異見 `CV1-DR-08`。

### DEC-010｜QA 分級（A／B／C）與回修上限
- **內容**：A 級（程式邏輯、安全、合規）、B 級（新頁新元件）、C 級（文件、交接本）自驗不派稽核；跨級取最高；同檔回修超過 2 輪停手問客戶。
- **範圍**：治理｜**日期**：2026-10-06｜**決策者**：客戶｜**狀態**：生效，但**本批（治理文件）被 DEC-016 覆寫**為須派獨立 evidence audit
- **來源**：C `H:58`「（客戶 2026-10-06 頒布，立即生效；逐字收錄）」；`H:63`「■ A 級（程式邏輯、安全、合規）」；`H:84`「■ 回修上限」。
- **取代鏈**：C 級「自驗」是否全面被取代未裁示 → `CV1-DR-02`。

### DEC-011｜formal Backlog 與 HANDOFF 分離（DR-2026-10-15-4）
- **內容**：`docs/BACKLOG.md` 為未完成事項的持久化來源；HANDOFF 只留 current state／active work／next step／major blocker & decision＋指向 Backlog；不得遺失 AUD-C3～C16；不大幅重構文件系統。
- **範圍**：治理｜**日期**：2026-10-15｜**決策者**：客戶｜**狀態**：生效
- **來源**：A `docs/BACKLOG.md@f0a6c474:56`「**DR-2026-10-15-4** | 2026-10-15 | 未完成事項放哪？ | **formal Backlog 與 HANDOFF 分離**」。B `ed186e04`（#856）。D 客戶訊息 2026-10-15T19:42Z（本 session；本檔首次入庫）「HANDOFF 只保留：/ - current state …」。
- **取代鏈**：**取代** 2026-10-09〈HANDOFF 維護：A〉C `H:2499`「- HANDOFF 維持單一 SSOT。」（原文在 handoff 分支，未改）。舊待辦遷移未完成 → BACKLOG `BL-MIGRATE-1`。

### DEC-012｜分支刪除不得自主執行
- **內容**：遠端分支刪除須客戶核准清單；`auto/recalibrate-20261001` 先保存唯一季度校準報告、不刪；不恢復已刪除的舊 audit branch。
- **範圍**：治理（不可逆）｜**日期**：2026-10-09；2026-10-15 重申｜**決策者**：客戶｜**狀態**：生效
- **來源**：C `H:2515` 段「…唯一例外：分支刪除不得自主執行。」；`H:2554`「"auto/recalibrate-20261001" 本輪不得刪除。」。D 客戶訊息 2026-10-15T13:40Z（本 session；本檔首次入庫）「不要恢復已刪除的舊 audit branch。/ 不要自行刪除 branch。」
- **取代鏈**：2026-10-09 核准刪除的三條舊分支已由客戶於 GitHub 網頁手動刪除（`H:2538`）。handoff 分支是否可刪 → `CV1-DR-05`（本批 ⛔ 不刪）。

### DEC-013｜已裁示事項不重問；待裁示題內容未變不重送
- **範圍**：治理｜**日期**：2026-10-09；2026-10-15 重申｜**決策者**：客戶｜**狀態**：生效
- **來源**：C `H:187`「只要問題內容沒有變化，不要重複發送；等待客戶回答即可。」。D 客戶訊息 2026-10-15T13:40Z（本 session；本檔首次入庫）§19「已裁示事項：/ 不要無故重問。」

### DEC-014｜Model／Mode／Effort 自主管理
- **內容**：每個完整階段開始前自判模型／模式／Effort；只在有明顯品質或額度效益時，於安全停點只回固定格式；客戶回「改好了」後直接繼續、不重摘要不重問不重做；等 CI／workflow／稽核時不得要求切換；模式切換不算客戶裁示題。
- **範圍**：治理｜**日期**：2026-10-16｜**決策者**：客戶｜**狀態**：生效
- **來源**：D 客戶訊息 2026-10-16T02:32Z（本 session；本檔首次入庫）「另外，從現在開始正式啟用「模式／Effort 自主管理」：」；「等待 CI／workflow／稽核時不得要求切模式」；「模式切換不算「客戶裁示問題」。」（格式全文見 `PROJECT_RULES.md` 第 9 節）
- **取代鏈**：無。

### DEC-015｜Audit 不得順手施工；不得預先決定 Batch 1
- **內容**：Audit 發現一律「記錄 → 分類 → 證據 → 建議」，不順手修（production-critical 例外：立即停下回報）；Audit 完成停一次回報；Batch 1 須經客戶確認方向後才開始。
- **範圍**：治理｜**日期**：2026-10-15；2026-10-16 重申｜**決策者**：客戶｜**狀態**：生效（該 Audit 已完成；「Batch 1 須客戶核准」仍有效）
- **來源**：D 客戶訊息 2026-10-15T13:40Z（本 session；本檔首次入庫）§21「Audit 不得順手施工 / 這是硬限制。」、§22「不得預先決定 Batch 1」。客戶訊息 2026-10-16T13:54Z（本 session；本檔首次入庫）「不要自行開始下一個功能 Batch。」

### DEC-016｜Project AI Constitution v1.0 建置規則（本批）
- **內容**：以最新 origin/main 為 base 建治理 branch；基金 repo 只作結構與治理機制參考，禁止複製基金專屬規格、文件位階、Decision；DECISIONS 不預設條目數、每條可追溯、證據不足不升格；BACKLOG 既有未完成項不得遺失、合併、擅自關閉；HANDOFF 只放現況＋指向；只做治理文件；完成後派獨立第二組 evidence audit，PASS 後 PR → CI → merge → main verification。
- **範圍**：治理｜**日期**：2026-10-16｜**決策者**：客戶｜**狀態**：生效（本批）
- **來源**：D 客戶訊息 2026-10-16T13:54Z（本 session；本檔首次入庫）「請正式為 "my-stock-dashboard" 建立 Project AI Constitution v1.0」；「"docs/DECISIONS.md" 不預設一定要有 DEC-001～DEC-018。」；「證據不足的歷史討論不得升格為 Decision」。
- **取代鏈**：本批覆寫 DEC-010 C 級自驗。

### DEC-073｜Minimum Sufficient Model／Effort Gate：每階段必判模型／能力等級＋Effort；不足時強制停手（Silent Autonomous Cruise 正式例外）（客戶 2026-10-23）
> 2026-10-23 追加（第 8 節「收到當輪追加」；ID 照序取下一個未用號，撰寫組寫入前 `git grep -n "DEC-073"` 實測 0 命中、最大為 DEC-072）。BACKLOG 登記：DR-2026-10-23-2。規則本文落點：`PROJECT_RULES.md` 第 9 節（9.0 新增、9.1／9.2 修訂）、第 3 節（正式例外註）、第 15 節（Context Loss Check／Handoff）。
- **內容**（客戶原文；經總管轉交，撰寫組未見原件，依總管轉交文字逐字收錄）：

```
專案 AI 不得再依固定模型或固定 Effort 工作。
每一個「下一完整工作階段／Batch」開始前，必須根據實際工作內容自行判斷：
- 所需模型／能力等級
- Minimum Sufficient Effort：Low / Medium / High
原則：
Low
GitHub 狀態確認、交接同步、機械性文件修正、低風險且規格完全明確的小修改。
Medium
一般 UI/UX、單模組 bug fix、一般測試／wiring、跨模組唯讀稽核，以及需要推理但不改變核心投資語意的工作。
High
只有必要時：
- 核心投資語意／判斷公式
- 跨模組且高複雜度的核心修改
- L3／資料層重大變更
- 新資料來源
- 不可逆操作
- 大規模刪除／合併
- 需要重新定義權重、門檻、評分或投資結論
強制 Model / Effort Gate
若「目前模型／Effort」低於下一工作所需：
1. 立即停手。
2. 不得硬做。
3. 不得自行假設模型或 Effort 已切換。
4. 不得自行降低問題複雜度以繞過 Gate。
5. 必須向客戶回報：
   - 建議模型／能力等級
   - 建議 Effort
   - 為什麼目前設定不足
   - 切換後準備執行的工作
6. 等客戶確認已切換後才能繼續。
這是 "Silent Autonomous Cruise" 的正式例外：
即使其他工作應靜默自主執行，遇到 Model / Effort 不足仍必須停下通知客戶。
反過來，如果現有能力高於工作所需，不需要為了形式要求客戶降級；遵守 Minimum Sufficient Effort 即可。
此規則必須寫入正式治理 SSOT（以 "PROJECT_RULES.md" 為主），並納入 Context Loss Check／交接規則，確保新 Claude 對話也會自動讀到，不再依賴客戶每次提醒。
```

- **範圍**：治理｜**日期**：2026-10-23｜**決策者**：客戶｜**狀態**：生效（規則已落盤 `PROJECT_RULES.md`）
- **來源**：D 客戶訊息 2026-10-23（本 session；本檔首次入庫；經總管轉交；確切 UTC 時戳未記錄，只保留日期）。
- **與其他 DEC 的關係**（append-only；撰寫組讀法，單組，⚠️ 待第二組 evidence audit；舊 DEC 條文一字不改）：
  - **DEC-014**（Model／Mode／Effort 自主管理）：**強化**。(a) 新增「**模型／能力等級**」為每個下一完整階段／Batch 開始前的**必判項**（DEC-014 原為「自判模型／模式／Effort、只在有明顯效益時中斷」，屬裁量式）；不足時由「有明顯效益才中斷」改為**強制停手**。DEC-014「客戶回『改好了』後直接繼續、不重摘要不重問不重做」與「等 CI／workflow／稽核時不得要求切模式」**續有效**。
  - **DEC-059**（Minimum Sufficient Effort、雙向主動提醒）：**部分修訂**。(b) DEC-059「高於所需也應主動提醒『可以降低 Effort』」被本條「反過來，如果現有能力高於工作所需，不需要為了形式要求客戶降級」**修訂**：降級提醒由「應主動提醒」改為「**不需要**為了形式要求降級」；`PROJECT_RULES.md` 9.2 對應句以刪除線保留、兩邊理由並陳。(d) 9.1 分級表依本條客戶新清單修訂，差異：**「跨模組唯讀稽核」明列 Medium**（舊表無此項）；High 新增「**新資料來源**」「**不可逆操作**」「**大規模刪除／合併**」「**L3／資料層重大變更**」「**需要重新定義權重、門檻、評分或投資結論**」；舊表的 High 細項（Risk Cap、選股核心邏輯、Thesis、PIT／look-ahead 等）未被本條明示撤銷，撰寫組讀為仍屬「核心投資語意／判斷公式」之例示、續有效（**撰寫組讀法**）。「Minimum Sufficient Effort」原則本身同向不變。
  - **DEC-061**（強制內部 Effort Check、High → Medium／Low 主動降級提醒）：**部分修訂**。內部 Check 的階段邊界（新批次前、裁示後動工前、merge＋main verification 後進收尾同步、收尾後）**續有效**，Check 題目擴為「模型／能力等級＋Effort」；DEC-061 的「High → Medium／Low 同樣必須主動提醒」與 (b) 同受本條修訂 —— 改為**不需要**為形式要求降級（DEC-061 原條文不刪）。
  - **第 3 節 Silent Autonomous Cruise（DEC-007／DEC-059）**：(c) 本條自稱為其「**正式例外**」—— 能力不足時停手通知客戶，不受靜默巡航「只在完整階段完成或需要裁示時打斷」的限制；DEC-059 第三種可打斷情況（需要切換 Effort）由本條**具體化並轉為強制**（且只限「不足」方向）。
  - **DEC-067／DEC-068**（Handoff Save Check、Context Loss Check）：**擴充**。依客戶原文「納入 Context Loss Check／交接規則」，`PROJECT_RULES.md` 第 15 節新增：新對話啟動與每個下一完整階段前須執行第 9 節 Gate，且 `docs/HANDOFF.md` 須記錄下一階段建議模型／Effort（落點與措辭為撰寫組依客戶原文所寫）。
  - ⚠️ Gate 不改變派工、獨立稽核、揭露義務（`CLAUDE.md` §-2）；Model／Effort 切換本身**不是**產品 Decision Gate（DEC-014 續有效）。

### DEC-084｜Minimum Sufficient Model × Effort 可直接執行規則＋雙向停手 Gate（客戶 2026-10-25）
> 2026-10-25 補登（ID 取下一個未用號；落盤前實測 `grep -n "DEC-084" docs/DECISIONS.md` 0 命中、最大為 DEC-083）。**本條為補登紀錄，不新增治理規則**：規則本文以 `PROJECT_RULES.md` 第 18 節與 `docs/governance/MODEL_EFFORT_POLICY_2026-10-25.md` 第 1 節為準，PR #928 合併於 main `361c7890`。
- **內容**（現行規則摘要，忠實記錄 main 已生效之裁示）：
  - 每個完整工作階段開始前，依 Minimum Sufficient Model × Effort 判斷；**Model 與 Effort 分開判斷**，不得因模型較強就拉高 Effort。
  - **Haiku**：GitHub 狀態、讀規則與 SSOT、治理／文件機械同步、改字、commit／PR 收尾等機械性低風險工作；**預設 Haiku + Low**。
  - **Sonnet**：一般 UI／UX、一般 coding、單模組 bug、tests、一般 wiring；**OAuth／Google Sheet／一般跨模組工作先以 Sonnet + Medium 評估**，不得因關鍵字（OAuth、Sheet、API、跨模組、architecture）直接升 Opus。
  - **Opus**：只用於真正高風險推理，如資安決策（scope／callback／credential／token）、新資料契約、多模組重大架構取捨、高風險 migration、投資核心語意、Risk Cap、PIT／look-ahead、不可逆操作；可逆且範圍受控者 Medium，影響重大者 High。
  - **Fable**：原則不作日常模型，只有 Opus 明顯不足的極端複雜工作才考慮；不得作為一般開發、OAuth、文件、GitHub、UI 或一般架構工作的預設。
  - **模型版本不得寫死**：治理文件只寫家族名，以客戶當下介面實際可選的最新對應版本為準。
  - **Effort** 一律採最低足夠值（Low → Medium → High 逐級，且需要時才往上）。
  - **雙向停手（Change Gate）**：只要任一建議配置（Model 或 Effort）與目前不同，無論升級或降級，都必須在 Safe Checkpoint 停手，告知客戶建議配置與原因，**等客戶手動切換並回覆「改好了」後才可繼續**；不得自行假設已切換。
  - **不得為省 token 把同一完整 Batch 人為切碎**；CI 等待、QA／audit 等待、commit、push、開 PR 不算新的完整工作階段；只有工作性質改變（如文件同步變實作、一般 wiring 變資安決策、局部 bug 變跨模組架構、一般資料處理變資料契約或投資核心語意）或原模型已證實不足時才重判。
  - **Silent Autonomous Cruise 續有效**；Model／Effort Change Gate 是其正式例外。
  - **正確性是底線**：省 token 不得造成錯誤投資語意、錯誤資料契約、資安風險、Missing 被當成 0／False／safe，或未驗證資訊被當成已確認。
- **範圍**：治理｜**日期**：2026-10-25｜**決策者**：客戶｜**狀態**：生效（`PROJECT_RULES.md` 第 18 節＋政策文件第 1 節已在 main `361c7890`；PR #928 squash 合併，main CI success）
- **來源**：客戶 2026-10-25 最新正式裁示（本 session；Model × Effort 治理 PR #928；客戶確認「維持模型家族名、不寫死版本號」並要求依 Rule 1～12 收斂）。
- **與其他 DEC 的關係**（append-only；舊 DEC 條文一字不改）：
  - **DEC-073**（Minimum Sufficient Model／Effort Gate）：**部分取代**。DEC-073 中「反過來，如果現有能力高於工作所需，不需要為了形式要求客戶降級」這一方向，由本條收斂為「**只要建議配置不同，升級或降級都必須停手**」。DEC-073 「不足時強制停手、每階段必判、不得假設已切換」等其餘規則**續有效**。`PROJECT_RULES.md` 第 18.4 節已記載此取代關係。
  - **DEC-059／DEC-061**（雙向主動提醒）：**加嚴**為「雙向停手＋等待客戶改好」。
  - **DEC-014**（Model／Mode／Effort 自主管理）：**續有效**。客戶回覆「改好了」後直接繼續，不重新摘要、不重問、不重做。
  - **DEC-007／Silent Autonomous Cruise**：**續有效**；Model／Effort 切換通知為正式例外。
  - **PROJECT_RULES.md 第 9.1 Effort 分級表、第 17 節 Minimum Sufficient Effort／Test Scope**：**不變**；本條只改「何時停、誰切換、切換後何時能繼續」。
  - ⚠️ 本條不改變派工、獨立稽核、揭露義務（`CLAUDE.md` §-2），不降低高風險工作（Risk Cap、投資語意、PIT、資料有效性）的 QA 要求。

### DEC-085｜Long-lived UI × Sustainable Logic（客戶 2026-10-26）
> 2026-10-26 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-085"` 0 命中、最大為 DEC-084）。**本條不新增任何功能需求、不改任何投資公式／門檻／權重／Risk Cap、不改資料來源、不授權任何 implementation**；它是永久治理規則，規則落點 `PROJECT_RULES.md` 第 19 節。
- **背景**：客戶要求新 UI 以「可長期使用、持續演進、不需反覆推倒重做」為目標，並給出 10 條核心治理原則。
- **內容**：見下方「來源」逐字原文（10 條）。濃縮可執行版見 `PROJECT_RULES.md` 第 19 節；若濃縮與原文有出入，以原文為準。
- **頁面責任（第 2 條）的讀法**：客戶列的六頁（📊 大盤／🎯 標的／⚡ 行動／🛡️ 持股／👤 我的／🩺 資料中心）是**責任方向**，**不等於現行程式 nav 命名**。讀碼事實：`shared/ia_nav.py` 現行頁名為 📊 大盤／🚦 今天／🔍 找標的／🔬 查一檔／💼 我的持股／📖 憑什麼／👤 我的，且 `docs/vnext/INTERACTION_COVERAGE_MATRIX_2026-10-25.md` §0.2 記載 ⚡ 行動、🩺 資料中心尚無 view。命名與導航落地屬後續 IA Decision Gate（本條不決定對映、不改 nav）。
- **範圍**：治理（永久規則）｜**日期**：2026-10-26｜**決策者**：客戶｜**狀態**：生效（`PROJECT_RULES.md` 第 19 節；待 PR 合併）
- **來源**：客戶 2026-10-26 指示（本 session；經總管轉交），**逐字收錄，未改寫**：

```
這個專案的新 UI 不只是短期改版，而要以「可以長期使用、持續演進、不需要反覆推倒重做」為目標。

核心治理原則如下。

1. UI 穩定、資料來源可替換

UI 不得直接綁死單一 API、資料供應商或單一資料抓取方式。

未來外部 API、MCP、資料來源或 provider 更換時：

- 優先由資料／adapter／service 層吸收變化。
- 不應因此迫使主要頁面資訊架構重新設計。
- UI 依賴的是穩定的 domain contract，不直接依賴 provider-specific schema。

2. 頁面責任長期穩定

目前主要產品資訊架構的責任方向：

- 📊 大盤：市場狀態、大盤、台股趨勢、國際趨勢與必要風險脈絡。
- 🎯 標的：尋找、篩選、探索值得進一步研究的標的。
- ⚡ 行動：把既有資料與規則轉成「目前需要注意／處理什麼」。
- 🛡️ 持股：持股、組合、觀察清單、風險與持續追蹤。
- 👤 我的：登入、Sheet 綁定、個人設定、目前使用中的組合／觀察清單。
- 🩺 資料中心：資料來源、資料健康、freshness、缺值與可用性。

未來可以優化畫面與元件，但不得因小功能增加就反覆改變主要頁面責任與導航定位。

重大 IA／頁面責任變更仍屬客戶 Decision Gate。

3. SSOT

同一份 domain state 或規則不得在不同頁面各自維護第二套實作。

尤其：

- Sheet binding
- portfolio
- watchlist
- authentication
- market state
- investment rule output
- data-health state

必須有清楚的 Single Source of Truth。

UI 只是消費既有狀態，不各頁自行重算或偷偷建立另一套來源。

4. 規則模組化、不可揉成黑盒

以下概念必須保持可獨立理解、測試與版本化：

- 市場位階
- 指標危險度
- Risk Cap
- 台股趨勢
- 國際趨勢
- 估值
- 個股／持股判讀
- 其他未來新增投資規則

不得只為 UI 簡化而把多個不同語意硬合併成單一不可追溯分數。

若需要 aggregate view，底層 constituent signals 與 provenance 仍必須保存。

5. AI 必須可替換

AI 是分析／解釋層，不得成為資料真相或核心 deterministic rule 的唯一來源。

未來更換：

- AI model
- AI provider
- prompt architecture
- inference implementation

不應迫使資料層、核心規則或 UI 資訊架構推倒重做。

AI 只能讀取既有、可追溯資料與規則輸出。

6. 向後相容與能力守恆

任何新 UI 改版都必須先做：

Old UI → New UI Interaction Coverage

舊 UI 是：

- 功能參考
- 邏輯參考
- 互動參考
- 資料來源參考

不是視覺模板。

新版可以：

- 合併
- 重新編排
- 收進次層
- 簡化前台

但不得無意識刪除既有重要能力。

任何舊功能必須標示：

- 已覆蓋
- 部分覆蓋
- 未覆蓋
- 明確不再需要／不應搬入

未完成替代前不得因新 UI 上線就直接刪舊 UI。

7. Data Contract 優先於 Provider Contract

長期演進時應優先建立穩定 domain schema／contract。

例如 UI 應依賴：
「價格、日期、freshness、source、status」

而不是依賴：
「Yahoo 回傳第幾欄」「MoneyDJ HTML selector」「某 API 特定 JSON 路徑」。

provider-specific parsing 應被限制在 adapter／ingestion layer。

8. Missing semantics 永久一致

長期 UI 與邏輯演進不得破壞既有資料語意：

- missing ≠ 0
- missing ≠ 中性
- missing ≠ 正常
- missing ≠ HOLD
- proxy／estimated ≠ real
- stale ≠ current
- error ≠ missing

UI 必須能表達這些不同狀態，不得只靠顏色。

9. Presentation 與 Decision Logic 分離

UI layout、component、copy 調整不得偷偷改變：

- threshold
- weights
- eligibility
- investment semantics
- Risk Cap
- trend definition
- valuation definition

UI change 與 investment-rule change 必須是不同類型的變更與不同 Gate。

10. 可演進，不追求永久凍結

「長久 UI」不是禁止未來改版。

允許：

- 更好的元件
- 更好的 responsive layout
- 更好的 accessibility
- 新資料呈現方式
- 新功能

但應遵循：
「stable responsibilities + replaceable internals」。

重大重構必須能說明為什麼現有 contract 已不足，而不能因開發方便就推倒重做。
```

- **與其他 DEC 的關係**（append-only；舊 DEC 條文一字不改；撰寫組讀 `docs/DECISIONS.md`、`shared/ia_nav.py`、`src/ui/views/` 後的判讀，單組）：
  - **DEC-017／DEC-018／DEC-019／DEC-020**（IA v2、雙軌入口、新 UI 唯一主線、舊 UI 刪除前置）：**同向、不取代**。第 6 點「未完成替代前不得刪舊 UI」與 DEC-019／020 的刪除前置一致；本條不放寬任何一項。另 DEC-017 為「五頁」，本條列六頁責任方向；五頁→六頁責任方向的落差由後續 IA Decision Gate 處理，本條不決定。
  - **DEC-022**（合規母法）：其狀態欄為「部分取代 → DEC-054」（全面禁止方向性 Action 部分已由 DEC-054 取代；其餘護欄的承接見 DEC-054「DEC-022 護欄承接表」）。**護欄承接依 DEC-054，本條不變**；第 9 點只加「UI 調整不得偷改投資語意」，不碰合規護欄。
  - **DEC-081**（互動控制完整性）／**DEC-082**（先草稿後施工 Stage A～D）／**DEC-083**（舊 UI Removal Gate 等）：**同向、不放寬**。第 6 點的 Old→New Interaction Coverage 與 DEC-081 的互動覆蓋、DEC-083 E 段的刪除閘門一致；第 2 點「重大 IA／頁面責任變更屬客戶 Decision Gate」與 DEC-082 流程相容。
  - **DEC-084**（Model×Effort）：**正交**，本條不涉及模型／Effort 規則。
  - **PROJECT_RULES 第 6 節（Safe Checkpoint）／第 13 節（Investment Domain Constitution）**：第 13 節為索引、不重新定義；第 8 點 Missing 語意、第 4 點規則模組化與其既有條目**同向**，衝突時取較嚴者。
  - ⚠️ 本條**不授權施工**：不開 P2、不刪舊 UI、不改 nav、不開任何 implementation；~~新 UI Stage B/C/D 仍須客戶 Gate（DEC-082）。~~
  - 📌 **更正註記（append-only；2026-10-26 有意識的更正，不是漏刪；決策者＝客戶，依客戶 2026-10-26 裁示；本註記為撰寫組／AI 判讀的更正，不是客戶原文，上方「來源」逐字區塊一字未動，也不是新 DEC）**：上方被劃掉的「新 UI Stage B/C/D 仍須客戶 Gate（DEC-082）」是 AI 誤讀 DEC-082。正確語意：**Stage A＝唯讀盤點；Stage B＝可產出 wireframe／IA／互動草稿與方案（不須先過客戶 Gate）；Stage C＝正式客戶 Decision Gate（草稿完成後停手等裁示）；Stage D＝只有 Stage C 客戶核准後才可施工**。本條「不授權施工」的其餘部分（不開 P2、不刪舊 UI、不改 nav、不開 implementation）不變。
  - ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：上述關係判讀由單一撰寫組產出，**沒有第二組驗過**。

### DEC-086｜Quota-safe Resume Checkpoint／中斷續接規則（客戶 2026-10-26）
> 2026-10-26 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-086"` 0 命中、最大為 DEC-085）。**本條不改任何產品 code／投資語意；規則落點 `PROJECT_RULES.md` 第 20 節。** 不新增功能需求、不改投資公式／門檻／權重／Risk Cap、不改資料來源、不授權任何 implementation。
- **背景**：客戶模型額度已接近上限，要求即使因額度、對話、連線、session、context 中斷，下一個全新 session 只讀 GitHub 就能接續，不依賴聊天記憶、不需客戶重新解釋。本規則立即生效。
- **內容**：見下方「來源」逐字原文（10 點＋本輪執行方式）。濃縮可執行版見 `PROJECT_RULES.md` 第 20 節；若濃縮與原文有出入，以原文為準。
- **範圍**：治理（永久規則）｜**日期**：2026-10-26｜**決策者**：客戶｜**狀態**：生效（`PROJECT_RULES.md` 第 20 節；待 PR 合併）
- **來源**：客戶 2026-10-26 指示（本 session；經總管轉交），**逐字收錄，未改寫**：

```
新增永久治理要求：Quota-safe Resume Checkpoint / 中斷續接規則。

目的：

即使 Claude 因模型額度、對話、連線、session、context 或其他中斷而停止，下一次恢復後只讀 GitHub 就能準確接續，不依賴聊天記憶，也不需要客戶重新解釋「做到哪裡」。

本規則應視為既有 DEC-067／DEC-068／DEC-079 的強化與具體化，不建立平行治理體系。

目前客戶模型額度已接近上限，因此本規則立即生效。

---

1. 不建立第二套狀態 SSOT

沿用既有 GitHub 長期記憶架構：

- "PROJECT_RULES.md"：正式永久規則
- "docs/DECISIONS.md"：正式裁示
- "docs/PROJECT_STATE.md"：durable project state／重要背景、限制、研究結論摘要
- "docs/BACKLOG.md"：真正尚未完成工作
- "docs/HANDOFF.md"：目前熱狀態與唯一接手點
- GitHub branch／PR／commit／CI：操作事實

不得另建平行的 "SESSION_STATE"、"RESUME_STATE"、第二份 handoff 或其他第二套狀態真相。

"docs/PROJECT_STATE.md" 已由 DEC-068 正式授權，必須保留，不得因本規則移除。

GitHub 操作事實永遠優先於 HANDOFF／聊天記憶。

---

2. Resume Checkpoint

"docs/HANDOFF.md" 應維持一個極短 Resume Checkpoint，讓新 session 可以直接接手。

至少包含：

- latest verified main SHA
- current working branch
- current PR（若有）
- current task / batch
- completed in this batch
- exact current stopping point
- next single action
- tests / CI 已完成
- tests / CI 尚未完成
- unresolved true Stop Gates
- 是否存在 uncommitted / unpushed work
- relevant evidence location
- recommended Model
- recommended Effort
- last checkpoint timestamp

要求：

- 只記目前狀態
- 不寫長篇流水帳
- 不複製完整 BACKLOG／DECISIONS
- 不把 inference 寫成 FACT
- 不把未完成工作寫成完成
- 必須能讓另一個完全沒有聊天 context 的 Claude 直接理解下一步

---

3. Checkpoint 觸發時機

除既有 Handoff Save Check／Context Loss Check 外，再加入以下安全節點。

一般狀態

在 meaningful safe checkpoint 更新：

- 一個實作小批完成
- commit 完成
- PR 建立
- 稽核／review 完成
- PR 合併
- Model／Effort 切換前
- 下一完整工作階段開始前
- 長工作即將跨 session／conversation

但避免為每個極小操作製造文件 commit。

優先跟著目前合法 feature branch／docs branch 一起保存。

---

4. 額度風險模式

約 80% 或其他明顯額度壓力

若客戶告知模型額度約達 80%，或 UI／系統顯示明顯接近限制：

- 每一個 meaningful safe checkpoint 都確認 Resume Checkpoint 是否足夠恢復
- 優先採小批次
- 避免開始過大的新工作
- 避免累積大量只存在本機、未保存的修改

約 90% 以上或即將歸零

- 每完成一個可驗證安全步驟就保存
- 優先 push 已安全完成的 commit／branch
- 不把大量未保存工作留在 local working tree
- 若新批次無法在合理 safe checkpoint 前保存，延後開始
- 優先完成 Handoff Save Check，而不是追求把整個下一階段做完

80%／90% 是操作門檻，不是產品邏輯；未來額度 UI 若改變，可依「明顯額度風險」等價判斷。

---

5. Git 保存原則

可以保存：

- 已完成且自驗通過的安全修改
- feature branch commit
- docs branch commit
- Draft PR
- HANDOFF Resume Checkpoint
- PROJECT_STATE durable facts

不得因 checkpoint：

- 直接把未驗證程式推進 main
- 繞過 CI／audit／review
- 降低 security gate
- 降低 investment semantics gate
- 寫入 secret／token／credential
- 把 checkpoint 當完成或驗收證據
- 改變 Auto-Ship 規則
- 改變 DEC-084 Model × Effort Gate

若工作尚未完成但需要保存：

- 留在 feature branch
- 若 repo 現行規則允許，使用清楚的 WIP／checkpoint commit
- PR 保持 Draft
- HANDOFF 明確標示「未完成／不可視為驗收」
- 最終仍走正常 review／CI／Auto-Ship

若 repo 既有規則禁止 WIP commit，必須遵守既有更嚴規則，只保存到合法的最小 safe unit。

---

6. Resume 流程

任何：

- 新 Claude session
- 額度恢復
- 對話中斷後重開
- context loss
- 換模型後重新接手

都不得先問客戶「做到哪裡」。

先自行：

1. 執行 GitHub Verification Gate
2. 讀 "PROJECT_RULES.md"
3. 讀 "docs/HANDOFF.md" Resume Checkpoint
4. 讀相關 "docs/PROJECT_STATE.md"
5. 讀相關 "docs/BACKLOG.md"
6. 讀相關 "docs/DECISIONS.md"
7. 查 current branch／PR／commit／CI
8. 比對 HANDOFF 與 GitHub 操作事實

若一致：

直接從 "next single action" 繼續。

若不一致：

- GitHub 操作事實優先
- 修正 HANDOFF
- 再繼續

只有真正 Stop Gate／客戶偏好／不可逆決策才詢問客戶。

---

7. 中斷後不得因失憶重做

恢復時不得因 session context 消失而：

- 重跑已有可信 CI 證據的完整批次
- 重問已有正式 DEC 的問題
- 重建已存在 PR
- 重寫已完成文件
- 重新研究已有可追溯 evidence 的結論
- 重做已合併且 main CI 已驗證的工作

必須先讀 GitHub 證據，再判斷是否真的需要重跑。

若 evidence 已失效、環境改變、main 已漂移或規格改變，才允許重驗，並說明原因。

---

8. Silent Autonomous Cruise

Resume Checkpoint 更新屬例行安全治理：

- 不需每次向客戶回報
- 不因此增加碎碎唸
- 不逐步回報 checkpoint
- 不把保存動作當作 customer gate

只有以下情況才回報：

- GitHub 與 HANDOFF 真正不一致
- 保存失敗
- branch／PR／CI 狀態異常
- 出現真正 Stop Gate
- Model × Effort 需要切換
- 整批工作完成

---

9. 與現有治理關係

本規則：

- 強化 DEC-067：Handoff Save Check
- 強化 DEC-068：GitHub＝跨 AI 長期專案記憶 SSOT／五檔分工／Context Loss Check
- 強化 DEC-079：額度／context 預判不足時提前落盤
- 不取代 DEC-084 Model × Effort
- 不取代 Silent Autonomous Cruise
- 不降低任何 Security／Investment／Data／CI／Audit Gate
- 不建立第二套 SSOT

若與既有治理文字有衝突，以較嚴者為準。

---

10. 驗收標準

本規則是否成功，只看一個核心結果：

「額度突然歸零時，換一個全新的 Claude session，只靠 GitHub，就必須知道做到哪裡、證據在哪、下一步做什麼，而且不需要客戶重新解釋。」

若新 session 無法做到這件事，表示 Resume Checkpoint 不合格，必須修正治理流程。

---

本輪執行方式

不要為本規則打亂目前已核准的 Stage A 工作邊界。

請在下一個合法 safe checkpoint：

1. 保存目前實際進度。
2. 更新 "docs/HANDOFF.md" 的極短 Resume Checkpoint。
3. 依既有五檔分工，把本規則正式落到正確治理文件。
4. 不建立新的狀態檔。
5. 不改產品 code。
6. 不進 Stage B。
7. 不改投資語意。
8. 不因治理落盤重做已完成 evidence。
9. 若需要新 DEC 編號，先確認最新未用編號後再使用。
10. 走正常 docs QA／獨立複驗／CI／Auto-Ship。

目前 Model × Effort：

- Model：Sonnet
- Effort：Medium

若仍是 Sonnet + Medium，不需切換，直接依 Silent Autonomous Cruise 執行。

完成後只在整批完成或真正 Gate 時回報。
```

- **與其他 DEC 的關係**（append-only；舊 DEC 條文一字不改；撰寫組判讀，單組）：
  - **DEC-067**（Handoff Save Check）：**強化**，不取代。
  - **DEC-068**（GitHub＝跨 AI 長期專案記憶 SSOT／五檔分工／Context Loss Check）：**強化**，不取代；不建立第二套 SSOT，`docs/PROJECT_STATE.md` 必須保留。
  - **DEC-079**（額度／context 預判不足時提前落盤）：**強化並具體化**（Resume Checkpoint 欄位、80%／90% 操作門檻）。
  - **DEC-084**（Model×Effort）：**不取代、不改**；Model／Effort Change Gate 續有效，checkpoint 不得繞過。
  - **Silent Autonomous Cruise**：**不取代**；Resume Checkpoint 更新屬例行安全治理，僅在原文第 8 點所列情況回報。
  - 不降低任何 Security／Investment／Data／CI／Audit Gate；不改 Auto-Ship；不建立第二套 SSOT（不得另建 `SESSION_STATE`／`RESUME_STATE`／第二份 handoff）。若與既有治理文字衝突，**取較嚴者**。
  - （撰寫組註記，非客戶原文）過渡：Resume Checkpoint 尚未落地於 `docs/HANDOFF.md` 前，以 HANDOFF 第 0 節現行短版為唯一接手點；缺 Checkpoint 不視為違規，但須在下一個 safe checkpoint 補上。
  - （撰寫組註記，非客戶原文）第 20 節為新增章節，因本規則含 15 欄清單與 8 步流程，無法併入第 11 節一條；DEC-079 要點「不另造重複章節」限於該條自身。
  - ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：上述關係判讀由單一撰寫組產出，**沒有第二組驗過**。

### DEC-087｜No Silent Stop／禁止無提示停手（客戶 2026-10-26）
> 2026-10-26 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-087"` 0 命中、最大為 DEC-086）。**本條不改任何產品 code／投資語意；規則落點 `PROJECT_RULES.md` 第 21 節。** 不新增功能需求、不改投資公式／門檻／權重／Risk Cap、不改資料來源、不授權任何 implementation。
- **背景**：Silent Autonomous Cruise 的「靜默」只代表減少中途碎片回報；客戶要求即使不回報進度，每次真正停手都必須讓客戶一眼看懂「要不要回」與「要回什麼」，禁止在客戶不知道是否需要回覆時停工。
- **內容**：見下方「來源」逐字原文（首行三種狀態、🟢／🟡／🔴 定義、禁止無提示停手、等待外部系統屬 🟢、客戶原文第 1～7 點）。濃縮可執行版見 `PROJECT_RULES.md` 第 21 節；若濃縮與原文有出入，以原文為準。
- **範圍**：治理（永久規則）｜**日期**：2026-10-26｜**決策者**：客戶｜**狀態**：生效（`PROJECT_RULES.md` 第 21 節；待 PR 合併）
- **與其他 DEC 的關係**（append-only；舊 DEC 條文一字不改；撰寫組判讀，單組）：
  - **DEC-067／DEC-068／DEC-079／DEC-086**（Handoff／GitHub SSOT／額度落盤／Resume Checkpoint）：**強化**，不取代；Resume Checkpoint 於 🟡／🔴 停手時同步記 waiting_for_customer 等欄（原文第 7 點）。不建立第二套狀態 SSOT。
  - **DEC-084**（Model×Effort）：**同向、不取代**；Model×Effort Gate 觸發即須標 🟡（原文第 4 點），本批 Haiku + Low 切換要求即為例。
  - **Silent Autonomous Cruise**（PROJECT_RULES 第 3 節）：**不取代**；原文第 6 點明定不增加碎碎唸、不逐步實況。
  - 不降低任何 Security／Investment／Data／CI／Audit Gate。若與既有文字衝突，取較嚴者。
  - ⚠️ 揭露（CLAUDE.md §-2 規則 6）：上述關係判讀由單一撰寫組產出，**沒有第二組驗過**。
- **來源**：客戶 2026-10-26 指示（本 session；經總管轉交），**逐字收錄，未改寫**：

```
新增永久治理要求：No Silent Stop / 禁止無提示停手規則。

目的：

Silent Autonomous Cruise 的「靜默」只代表減少中途碎片回報，不代表可以在客戶不知道是否需要回覆的情況下停止工作。

從現在起，任何 user-visible 回覆的第一行必須明確標示以下三種狀態之一：

- 🟢 不需要你回覆
- 🟡 需要你回覆
- 🔴 需要你裁示

1. 🟢 不需要你回覆

用於：

- Claude 會自行繼續
- 等 CI／audit／check_suite，但有自動喚醒機制
- 純進度資訊，不需要客戶動作
- 整批工作已完成

若工作尚未完成但會自行繼續，必須明確寫：

「🟢 不需要你回覆（我會自行繼續）」
或
「🟢 不需要你回覆（等待 CI；事件喚醒後自動繼續）」

不得讓客戶自行猜測是否需要回話。

2. 🟡 需要你回覆

只要後續工作因「需要客戶做一個明確動作」而停住，就必須使用此狀態。

例如：

- Model／Effort 需要切換
- 需要客戶提供檔案／憑證／實機結果
- 需要客戶完成外部操作
- 需要客戶回覆固定確認語

除了標示「需要你回覆」，還必須明確告訴客戶：

1. 為什麼停
2. 要做什麼
3. 做完後精確回覆什麼

例如：

「🟡 需要你回覆
請切換為 Sonnet + Medium，完成後只要回覆『改好了』。」

禁止只說「我先停在這裡」而不告知客戶需要回應。

3. 🔴 需要你裁示

只有真正 Customer Decision Gate 才使用。

必須：

- 精簡列出問題
- 提供選項
- 提供 AI 總管推薦
- 明確寫出客戶只需回覆什麼

技術細節如果 AI 總管能自行判斷，不得丟給客戶裁示。

4. 禁止無提示停手

任何情況下，只要 Claude 不會自行繼續，而且下一步依賴客戶，就禁止在沒有 🟡／🔴 標記的情況下結束回覆。

尤其禁止：

- 說「先停在這裡」但不說需要客戶回覆
- 說「等待你的指示」但不說要回覆什麼
- 只描述 Decision Gate，不標 🔴
- Model × Effort Gate 觸發後不標 🟡
- 因外部資料不足停止，卻沒說是否需要客戶介入

5. 等待外部系統不等於客戶 Gate

CI、GitHub Actions、audit agent、check_suite 等若可自動恢復：

- 標 🟢
- 不要求客戶回覆
- 事件完成後自行繼續

只有真的無法自行前進、必須客戶操作時，才標 🟡。

6. 與 Silent Autonomous Cruise 的關係

本規則不增加碎碎唸。

仍維持：

- 安全工作自主執行
- 不回報中途微小進度
- 不逐步実況
- 不要求客戶反覆確認

但每一次真正停手，都必須讓客戶一眼看懂：

「我要不要回？」
「如果要，我要回什麼？」

7. Resume Checkpoint

若 Claude 因 🟡／🔴 Gate 停手：

Resume Checkpoint 必須同步記錄：

- stop reason
- waiting_for_customer = true
- exact customer action
- exact resume condition
- next single action

這樣即使額度／session 同時中斷，新 session 也知道目前是在等客戶，而不是誤以為可以自行繼續。

請把這條規則正式落入既有治理體系；先確認下一個可用 DEC 編號。

docs-only，不改產品 code、不進 Stage B、不改投資語意。

完成正常 QA／CI／Auto-Ship 後更新 Resume Checkpoint。

本批建議：
Model：Haiku
Effort：Low

若目前不是 Haiku + Low，依 DEC-084 必須先明確回覆：
「🟡 需要你回覆：請切換 Haiku + Low，完成後回覆『改好了』。」

不得直接無提示停手。
```

### DEC-088｜Proactive Conversation Handoff／主動建議換新對話（客戶 2026-10-26）
> 2026-10-26 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-088"` 0 命中、最大為 DEC-087）。**本條不改任何產品 code／投資語意；規則落點 `PROJECT_RULES.md` 第 22 節。** 不新增功能需求、不改投資公式／門檻／權重／Risk Cap、不改資料來源、不授權任何 implementation。
- **背景**：長對話的 context／token／quota／session 狀態可能已不適合安全繼續下一完整工作階段；客戶要求此時 AI 先把現場落盤，再主動建議換新對話並附接手提示語，避免 checkpoint 後默默停住、也避免客戶需要重新解釋做到哪裡。
- **內容**：見下方「來源」逐字原文（觸發條件、四步順序、固定首句、接手提示語、禁止事項、context 健康時不得頻繁要求）。濃縮可執行版見 `PROJECT_RULES.md` 第 22 節；若濃縮與原文有出入，以原文為準。
- **範圍**：治理（永久規則）｜**日期**：2026-10-26｜**決策者**：客戶｜**狀態**：生效（`PROJECT_RULES.md` 第 22 節；待 PR 合併）
- **與其他 DEC 的關係**（append-only；舊 DEC 條文一字不改；以下為撰寫組讀法，非客戶原文；單組）：
  - **DEC-086**（Resume Checkpoint）：**強化**；原文要求換對話前先更新 HANDOFF／Resume Checkpoint，不建立第二套狀態 SSOT。
  - **DEC-087**（No Silent Stop）：**同向**；「建議換新對話」屬需要客戶回覆的停手，首行標 🟡（原文固定首句即為 🟡）。
  - **DEC-079／DEC-067／DEC-068**（額度落盤／Handoff／GitHub SSOT）：**強化**，不取代；新 session 仍以 GitHub Verification Gate 與 GitHub SSOT 為準。
  - **DEC-084**（Model×Effort）：**不取代**；兩者各自獨立觸發。
  - 不建立第二套狀態 SSOT；不降低任何 Security／Investment／Data／CI／Audit Gate。若與既有文字衝突，取較嚴者。
  - ⚠️ 揭露（CLAUDE.md §-2 規則 6）：上述關係判讀由單一撰寫組產出，**沒有第二組驗過**。
- **來源**：客戶 2026-10-26 指示（本 session；經總管轉交），**逐字收錄，未改寫**：

```
Proactive Conversation Handoff

當專案 AI 判斷目前 conversation 的 context／token／quota／session 狀態已不適合安全繼續下一完整工作階段時：

- 先完成最近合法 Safe Checkpoint
- 更新 HANDOFF／Resume Checkpoint
- 確認 branch／PR／CI／next single action 可由新 session 恢復
- 然後必須主動回覆：

「🟡 需要你回覆：建議換新對話。」

並簡短說明原因。

同時提供一段可直接貼到新 Claude Code 對話的接手提示語。

不得 checkpoint 後默默停住；不得要求客戶重新解釋做到哪裡。

新 session 仍以 GitHub Verification Gate 與 GitHub SSOT 為準，接手提示語只做入口。

若目前 context 仍健康，不得為形式頻繁要求換對話。
```

### DEC-089｜New UI Stage C 裁示：G1 C／G2 X／G3 B／G4 B／G5 B／G6 A／G7 B＋線框套件核准＋確認表全同意＋7 項補充執行條件（客戶 2026-10-26）
> 📌 **被 DEC-092 部分 supersede（2026-10-27；append-only，本條原文未改）**：G1＝C 六向導覽已被 D2.5 固定四主導航取代（DEC-092 Q6）；G3／G4 的 ⚡／🩺 佔位主頁設計不再作為最終設計；**DEC-089 其餘項與 HI-1～HI-6 未核准狀態不變**。
> 2026-10-26 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-089"` 0 命中、最大為 DEC-088）。**本條只落盤客戶的 Stage C 裁示，不改任何產品 code／測試／navigation，不進 Stage D 實作。**
- **背景**：DEC-082 規定新 UI 流程為 Stage A（事實盤點）→ Stage B（設計草稿）→ Stage C（正式客戶 Decision Gate）→ Stage D（施工）。Stage B 草稿 `docs/vnext/NEWUI_STAGE_B_DRAFT_2026-10-26.md` 已於 #938 合併並呈現為 Stage C；客戶於 2026-10-26 回覆本裁示。
- **內容**（撰寫組摘要，**非客戶原文**；以下「來源」fence 為準，若摘要與原文有出入，以原文為準）：
  - **G1＝C**（先固定六向導覽殼，內容分步補；現行頁成為各方向底下的葉；未建方向誠實顯示「⬜ 尚未建置」）；**G2＝X**（🎯 找＋查同頁兩區）；**G3＝B**（⚡ 建最小版本：彙總＋連回 🛡️）；**G4＝B**（🩺 唯讀＋篩選＋「重新檢查」鈕＋全站一行狀態）；**G5＝B**（高頻動線加可點跳轉＋預填識別）；**G6＝A**（🛡️ 補逐檔戰情表＋展開明細，欄位僅限已存在事實）；**G7＝B**（High 項目分批處理）。各選項的完整定義以 Stage B 草稿 B9.4 為準。
  - **線框套件（B3～B7）整體核准**；**「⚑／結構性自決項確認表」（24 項）全同意**（撰寫組讀法：D-1～D-41 的總管自決在此範圍內維持原提案；輕量確認 Q1～Q4 客戶未逐項回覆，**撰寫組不替客戶解讀，維持「未回覆＝維持現況／暫行」**）。
  - **7 項補充執行條件**見來源逐字原文：核准的是設計方向，不把 INFERENCE 升格為 FACT；Stage D 實作前／時須以最新 main 實證所有未複驗項，驗不到維持 missing／未確認；不新增或修改任何投資語意與資料來源；G7＝B 不等於 HI-1～HI-6 已核准施工；舊 UI 維持 Removal Gate；Stage D 前依 DEC-084 做 Model × Effort Check；維持 Silent Autonomous Cruise 與 Resume Checkpoint。
- **範圍**：產品／UI（New UI Stage C）｜**日期**：2026-10-26｜**決策者**：客戶｜**狀態**：生效（待 PR 合併）
- **核准範圍（撰寫組讀法，單組）**：
  - 核准的是**被選定的方案與線框的設計方向**；**不涵蓋** HI-1～HI-6（High Gate 待開清單；客戶原文第 4 點明示不視為已核准施工，需另走 High Gate）。
  - **G1＝C 時 Stage D 仍須先出「導覽殼」線框**：Stage B 草稿只有歸屬圖、沒有殼的畫面（草稿 B9.4 G1 條件）；依 `CLAUDE.md` §-1.5.D（v3）§03-2 ①，導覽列／分頁動線屬 UI 草稿審批情境，**殼線框經客戶核准後才可寫殼的 UI code**。本裁示的「線框套件核准」指 B3～B7，不含殼。
  - **不新增投資語意**：Risk Cap、threshold、weights、趨勢／估值定義、資料來源、Action 語彙一律不動（原文第 3 點）。
  - **舊 UI 全留**：Removal Gate（DEC-019／020／083 E）不變；新版 Old→New 對等驗收完成前不得刪除。
  - **Stage D 前置**：須先以最新 main 實證所有 INFERENCE／未複驗項（原文第 2 點），並依 DEC-084 重做 Model × Effort Check（原文第 6 點）。
- **與其他 DEC 的關係**（append-only；舊 DEC 條文一字不改；以下為撰寫組讀法，非客戶原文；單組）：
  - **DEC-082**（Stage A→B→C→D）：**履行**；本條是 Stage C 的客戶裁示，Stage D 的 gate 由此開啟，但受上列條件與 G1＝C 的殼線框 gate 約束。
  - **DEC-085**（Long-lived UI × Sustainable Logic）：**同向**；責任方向≠現行 nav 命名、SSOT、Coverage 四狀態、Missing 語意照舊。
  - **DEC-081／DEC-083**（📊 大盤／👤 我的 Stage C）：**不變**；已核准內容不因本條改動，舊 🚦 今天維持至 📊 驗收。
  - **DEC-084**（Model×Effort）：**呼叫**；Stage D 開始前必須重做一次。
  - **DEC-086／087／088**（Resume Checkpoint／No Silent Stop／主動換新對話）：**呼叫**；原文第 7 點要求維持；本條落盤後 `waiting_for_customer` 為 false，Stage D 的 D1 殼線框完成後才再需客戶核准。
  - **DEC-019／DEC-020**（New UI 唯一主線／舊 UI 刪除前置）：**不變**；Removal Gate 照舊。
  - 不降低任何 Security／Investment／Data／CI／Audit Gate。若與既有文字衝突，取較嚴者。
  - ⚠️ 揭露（CLAUDE.md §-2 規則 6）：「核准範圍」與上述關係判讀、對「全同意」涵蓋範圍的讀法，皆由單一撰寫組產出，**沒有第二組驗過**；摘要中的選項敘述轉述自 Stage B 草稿，亦非客戶原文。
- **來源**：客戶 2026-10-26 Stage C 裁示（本 session；經總管轉交），**逐字收錄，未改寫**：

```
G1 C｜G2 X｜G3 B｜G4 B｜G5 B｜G6 A｜G7 B｜線框套件 核准｜確認表 全同意

補充執行條件：

1. 本次核准的是 Stage C 的 IA／UX／線框設計方向，不代表把文件中的 INFERENCE 自動升格為 FACT。
2. Stage D 實作前／實作時，所有已標示未複驗的資料契約、欄位可用性、L3 彙總讀法、動態引用等，必須以最新 main 實證確認；驗不到就維持 missing／未確認，不得補猜。
3. 不因本次核准新增或修改投資語意、Risk Cap、threshold、weights、台股／國際趨勢定義、估值公式或資料來源。
4. G7 採 B：High 項目分批處理；不得因 Stage C 核准而視為 HI-1～HI-6 已核准施工。
5. 舊 UI 維持 Removal Gate，未完成新版對等驗收前不得刪除。
6. Stage D 開始前依 DEC-084 再做一次 Model × Effort Check；若目前配置已是最低足夠配置，可直接靜默繼續。
7. 維持 Silent Autonomous Cruise 與 Resume Checkpoint；若 context／quota 已不適合安全繼續，依既有治理主動通知我換新對話。
```


### DEC-090｜New UI D1 導覽殼線框裁示：形式採 (b)＋線框核准＋②～⑧ 全要＋⑨ 要（指路句補「側欄選『不使用』」步驟）＋P-1／P-2 同意（客戶 2026-10-26）
> 📌 **被 DEC-092 部分 supersede（2026-10-27；append-only，本條原文未改）**：形式 (b) 兩層側欄與 ⚡／🩺 佔位頁文案已被 D2.5 固定四主導航取代（DEC-092 Q6）；D2 殼僅作過渡版保留、D2 過渡版功能驗收通過；其餘（線框核准的歷史事實、舊 UI Removal Gate）不變。
> 2026-10-26 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-090"` 0 命中、最大為 DEC-089）。**本條只落盤客戶對 D1 線框的裁示，不改任何產品 code／測試／navigation，不改 CLAUDE.md／PROJECT_RULES.md。**
- **背景**：DEC-089（G1＝C）要求 Stage D 先出導覽殼線框並經客戶核准才可寫殼 UI code。D1 線框 `docs/vnext/NEWUI_D1_SHELL_WIREFRAME_2026-10-26.md` 已於 PR #942 合併 main `385463a6`，客戶於 2026-10-26 回覆本裁示。
- **內容**（撰寫組逐項對照線框 §1.4／§4 原文翻譯，**非客戶原文**；以下「來源」為準，若有出入以原文為準）：
  - **① 殼的形式＝(b)**（對應原文「D1 採 b」）：側欄兩層——最上層固定六個方向（📊 大盤／🎯 標的／⚡ 行動／🛡️ 持股／👤 我的／🩺 資料中心），選定方向後出現第二層該方向底下的頁；「不使用（用下方原功能）」仍為預設。線框 §2.2、§3 為準。
  - **線框核准**：核准 `docs/vnext/NEWUI_D1_SHELL_WIREFRAME_2026-10-26.md` 為殼實作依據（以 (b) 的畫面態為準）。
  - **② 要**：主畫面最上方「📍 位置列」。**③ 要**：選單尾端「⬜」標記與「⬜＝尚未建置」圖例。**④ 要**：第二層小標題「〈方向〉底下：」。**⑤ 要**：🚦 今天頁頂一行說明（線框 §3.7）。**⑥ 要**：預設落點與排序（進入方向先落在第一個已建的頁；已建在前、未建在後，線框 §2.2）。**⑦ 要**：指路句多帶方向名（例：「🩺 資料中心 › 📖 憑什麼 › 資料體檢」，線框 §3.1）。**⑧ 要**：兩份佔位頁文案（⚡ 行動、🩺 資料中心本體）採用，逐頁見 P-1、P-2。
  - **⑨ 要**：在指到舊版的說明句（線框 §1.2 第 7 點）加入「側欄選『不使用』」這一步。線框 §1.4 ⑨ 與註 1 定義為「只在 P-1、P-2 兩份文案各加一句」，故本條只授權在 P-1、P-2 及 §4 模板加此步驟；其餘固定字不改。
  - **P-1 同意**（⚡ 行動佔位頁文案，線框 §4 P-1；套用 ⑨）。**P-2 同意**（🩺 資料中心本體佔位頁文案，線框 §4 P-2；含「🔧 工具箱 › 🔎 資料診斷」兩層路徑延伸；套用 ⑨）。
- **範圍**：產品／UI（New UI Stage D／D1）｜**日期**：2026-10-26｜**決策者**：客戶｜**狀態**：生效（待 PR 合併）
- **授權範圍**：**D2（`NEWUI-STAGE-D2-SHELL-IMPL`）導覽殼實作的授權依據**。D2 開工前仍須 DEC-084 Model × Effort 重判、擴充 `tests/test_ia_v2_sidebar_nav.py`、獨立 QA、Old→New 對等驗收。
- **不授權**：任何投資語意（Risk Cap、threshold、weights、趨勢／估值定義）、資料來源變更；刪除任何舊 UI（Removal Gate 不變）；🎯 合頁（屬 D6）、⚡／🩺 內容（D7／D8）、可點跳轉（D9）、HI-1～HI-6；線框 §1.3「本文件不決定的事」仍不決定。
- **未確認／留待實作核對**（不替客戶解讀）：線框 §6 T12（P-1「去哪」指向 🛡️ 戰情室或 🚦 今天較貼切）為內部技術核對項，客戶已同意 P-1 現文；P-1 字面與頁內標題對齊屬實作時核對，不得改語意；⑨ 的加句確切位置（P-1、P-2 舊版句前或後）由 D2 依線框模板決定並於交付報告揭露。
- **與其他 DEC 的關係**（append-only，單組讀法）：DEC-089 **履行**（G1＝C 殼線框 gate 於此開啟）；DEC-082 **履行**；DEC-084 **呼叫**（D2 開工前重判）；DEC-019／020 **不變**。不降低任何 Security／Investment／Data／CI／Audit Gate；衝突取較嚴者。⚠️ 逐項對照由單一撰寫組產出，沒有第二組驗過。
- **來源**：客戶 2026-10-26 回覆（本 session；經總管轉交），**逐字收錄，未改寫**：

```
D1 採 b｜線框 核准｜②～⑧ 全部要｜⑨ 要｜P-1 同意｜P-2 同意
```


### DEC-091｜D2.5 Simple UI／One AI Brain：停止原 D3～D5，改執行 D2.5 指定版設計（4 頁主導航＋全站唯一 AI 投資總結＋產業趨勢主線）；本輪只規劃、停在 Customer Design Gate（客戶 2026-10-27）
> 📌 **被 DEC-092 更新（2026-10-27；append-only，本條原文未改）**：本條「待客戶 Design Gate 裁示」狀態已由 DEC-092 解除（設計方向核准，Q1～Q6 已裁示）；D2 殼處置、批次重排、策略分類／產業趨勢口徑見 DEC-092。
> 2026-10-27 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-091"` 0 命中、最大為 DEC-090）。**本條只落盤客戶的 D2.5 指示，不改任何產品 code／測試／navigation，不改 CLAUDE.md／PROJECT_RULES.md。** 來源類別＝**客戶口述指示**（D 類；經總管轉交的規格檔，下方「來源」逐字收錄）。
- **背景**：D2 導覽殼（六方向兩層側欄，DEC-090 核准）已合併 main（#944 `b111c1c6`），其後客戶回報 Streamlit Cloud 啟動 `ImportError`（`NEWUI-STAGE-D2-BOOT-INCIDENT`，根因未確認）。客戶於 2026-10-27 另行指示改走 D2.5。
- **內容**（撰寫組摘要，**非客戶原文**；以「來源」逐字文字為準，若有出入以原文為準）：
  - **(a) 停止與改道**：停止原 D3～D5 施工，改執行 **D2.5 — Simple UI / One AI Brain**；規格為「客戶指定版」，客戶已看過並核准一版視覺方向，本輪**不是自由設計**；僅允許針對 Streamlit 技術限制做最小調整，偏離主要 IA／資訊層級／頁面責任＝列為 Customer Gate，不得自行換方案。
  - **(b) 主導航固定 4 個**（桌面與手機）：📊 市場／🎯 標的／💼 持股／👤 我的。⚡行動→融入各頁首屏「需要處理」；🩺→小型「資料健康」狀態入口（點擊才展開）；📖→各重要判斷旁「查看依據」（點開才顯示）。三者不再作為一般使用者主導航。
  - **(c) 資訊三層**：Level 1 結論／需不需要行動；Level 2 圖表＋主要原因；Level 3「查看依據」展開後才看（原始數字、計算邏輯、資料來源、freshness、missing reason、門檻、工程診斷），**不得預設展開**。
  - **(d) One AI Brain**：全站唯一「🤖 AI 投資總結」，共用同一份 Decision Digest，**不是第五個主導航頁**；固定五段輸出（市場／產業／存股／資本利得／本期行動，資料不足時必須說不知道）；每個結論旁可「查看依據」（使用的資料、資料日期、規則／計算結果、missing、confidence／availability、AI 是否參與）。架構＝Data Layer → Rule/Calculation Layer → 各頁 Structured Result → Decision Digest → One AI Brain → Investment Summary；**禁止 Data → LLM → LLM 自己決定數字**；AI 不得自行抓資料、生數字、補 missing、設門檻、定義公式、發明股票或產業趨勢。
  - **(e) 持股頁**：先按**投資目的**分 🌱存股／📈資本利得；**ETF／個股不是分類規則**；正式分類必須來自客戶設定／既有可追溯設定，沒資料顯示「未分類」，**不得 AI 猜**。進階分析（235 燈、80/20、VaR、壓力測試等）降為 Level 3，保留不刪。
  - **(f) 產業趨勢**為**正式新增主線**（不是純 UI）：先盤點既有資料是否支援、不夠就列資料缺口；**不得用 LLM 常識宣告某產業已衰退或已崛起**。
  - **(g) EPS×PE 大盤合理區間**維持 **Research Framework**：EPS 資料來源／PE 情境／計算公式／更新頻率經正式 High Gate 核准前，不得把示意值當 production；Risk Cap 尚未核准時，「建議總持股水位」須誠實顯示「尚未核准／無法判定」，不可用示意數字。
  - **(h) 本輪只規劃**：產出 4 頁＋AI 總結展開的視覺 wireframe、Old→New Coverage、AI Brain architecture／Decision Digest、產業資料盤點與缺口、實作批次建議並落盤；**不改 product code**，完成後**停在 Customer Design Gate**，只把真正需要客戶決定的少量問題交回。
  - **(i) 落盤要求**：客戶要求「每次討論有正式結論後存到 GitHub」——設計規格寫入 `docs/vnext/`、正式裁示寫入本檔、待辦寫入 `docs/BACKLOG.md`、階段狀態寫入 `docs/PROJECT_STATE.md`、Resume Point 寫入 `docs/HANDOFF.md`（一次 docs PR）。
- **保護規則（沿用，客戶原文最末段）**：舊 UI 不刪；Risk Cap、threshold、weights、正式趨勢定義、估值公式、投資語意不得未經 Gate 修改；Missing semantics 不變（missing≠0、≠neutral）；尚未證實的推論維持 INFERENCE；現有 AI summary 只是技術基礎，不等於全站 AI 總管；HI-1～HI-6 未核准。
- **範圍**：產品／UI（New UI D2.5）｜**日期**：2026-10-27｜**決策者**：客戶｜**狀態**：生效（待 PR 合併）；設計文件本身**待客戶 Design Gate 裁示**。
- **⚠️ 與既有裁示的狀態（必讀，避免誤讀為撤銷）**：D2.5 設計規格文件（`docs/vnext/NEWUI_D25_A／B／C_*_2026-10-27.md`、`docs/vnext/d25_wireframes/`）**尚未被客戶核准**。在其核准前：**DEC-089 G1＝C 六向導覽、DEC-090 與已合併的 D2 殼、G3（⚡ 行動最小版）／G4（🩺 資料中心）的形態，既不視為被撤銷，也不視為仍是最終方案——狀態＝待客戶在 Customer Design Gate 裁示。** 本條不修改 DEC-089／DEC-090 任何一字（append-only）。
- **D2 Cloud 啟動事故仍 open**：`NEWUI-STAGE-D2-BOOT-INCIDENT`（Cloud 啟動 `app.py` `ImportError`，根因未確認；缺 Cloud 完整 traceback 或客戶 Reboot 結果）不因 D2.5 改道而結案；`tests/test_boot_import_smoke.py`（#945）只是守衛，不是根因結論。
- **授權範圍**：僅授權產出規劃文件（wireframe、Coverage、AI Brain／資料盤點）與本次 docs 落盤。**不授權**：任何 product UI code、nav 變更、刪舊 UI、投資語意／Risk Cap／threshold／weights／估值公式變更、新增資料來源、HI-1～HI-6、EPS×PE 當 production、AI Brain 實作。
- **與其他 DEC 的關係**（append-only，單組讀法）：DEC-089（Stage C，G1＝C 等）**待裁示，不撤銷**；DEC-090（D1 殼線框）及 D2 殼（#944）**待裁示，不撤銷**；DEC-081／083（📊 大盤／👤 我的）**不變**；DEC-082（先草稿後施工）／DEC-085（Long-lived UI）／DEC-084（Model×Effort）**呼叫**；DEC-019／020（舊 UI Removal Gate）**不變**；DEC-086／087／088（Resume Checkpoint／No Silent Stop／換對話）**呼叫**。不降低任何 Security／Investment／Data／CI／Audit Gate；衝突取較嚴者。
- **未確認／留待 Design Gate**（不替客戶解讀）：D2 殼（六向）如何處置（保留／改為 4 頁／其他）；原 D3～D11 批次是否沿用、重排或作廢；Risk Cap、EPS×PE、策略分類資料契約、產業趨勢資料的正式 Gate；具體問題清單見設計文件。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：上列摘要與「與既有裁示的狀態」判讀由單一撰寫組產出，**沒有第二組驗過**；摘要非客戶原文。
- **來源**：客戶 2026-10-27 D2.5 指示（本 session；經總管轉交的規格檔），**逐字收錄，未改寫**（首行標題為總管轉交檔的檔頭）：

```
# 客戶指定版 D2.5 規格（2026-10-27，逐項照辦；只允許針對 Streamlit 技術限制做最小調整；偏離主要 IA／資訊層級／頁面責任＝列為 Customer Gate，不得自行換方案）

停止原 D3～D5 施工。執行 D2.5 — Simple UI / One AI Brain。本批只做規劃、wireframe、coverage、資料盤點與正式文件落盤，不改 product code。客戶已看過並核准一版視覺方向，本輪不是自由設計。

## 一、整體視覺
深色投資儀表板：深色背景、卡片式、留白清楚、大數字少而重要、圖表優先、文字短、第一眼知道現在狀態、不把工程文件搬到使用者畫面、手機第一屏也看得懂。
禁止：大量三要素文字卡＋工程說明＋資料來源＋門檻＋診斷全部同層。
資訊層固定：
- Level 1：結論／需不需要行動
- Level 2：圖表＋主要原因
- Level 3：「查看依據」展開後才看：原始數字、計算邏輯、資料來源、freshness、missing reason、門檻、工程診斷。不得預設展開 Level 3。

## 二、主導航固定 4 個（桌面與手機）
1. 📊 市場 2. 🎯 標的 3. 💼 持股 4. 👤 我的
不再作為一般使用者主導航：⚡行動、🩺資料中心、📖憑什麼。改成能力：
- ⚡行動：融入各頁首屏「需要處理」
- 🩺資料健康：小型狀態入口，例如「資料 8/9 正常 · 1 項待更新」，點擊才展開
- 📖憑什麼：每個重要判斷旁放「查看依據」，點開才顯示

## 三、全站固定 One AI Brain
不要每頁各自建立不同 AI。設計成「🤖 AI 投資總結」，全站唯一投資決策總管，不是第五個主導航頁。桌面：頁面首屏右上／上方明顯區域，可展開。手機：首屏放一張 compact AI summary card。所有主頁共用同一份 Decision Digest。
AI 整合：市場→台股趨勢→國際趨勢→估值→產業趨勢→候選標的→我的持股→存股→資本利得→Risk Cap→最終行動。
AI 不得自行抓一套與資料層不同的資料；不得自己：生數字、補 missing、設門檻、定義公式、發明股票、發明產業趨勢。

## 四、📊 市場頁指定版
頁首「📊 市場」，副標「現在適不適合投資？未來風險正在增加還是下降？」
第一列只放 3～4 個核心狀態：
- 市場狀態：🟢偏多／🟡中性／🔴偏空／⬜無法判定
- 建議總持股水位：例如 60～70%；若正式 Risk Cap 尚未核准：誠實顯示「尚未核准／無法判定」，不可用示意數字
- 今日主要風險：只顯示最重要 1～3 項
- 更新：主 CTA「🚀 更新市場資料」
主要圖表：
- 圖A 🇹🇼台股趨勢：圖上方「看台股目前是在長期上升、整理還是轉弱；趨勢與短期波動分開判斷。」圖：加權指數、必要趨勢線、必要區間、資料日；不要塞十幾個燈在第一層。
- 圖B 🌍國際趨勢：圖上方「看海外市場、利率與美元是否正在幫助或壓抑台股風險偏好。」只挑真正有判斷價值的系列；詳細原始 series 收到「查看依據」。
- 圖C 💰大盤合理區間：保留蕭碧燕研究方向，大盤 EPS × PE 情境估值。圖上方「用企業獲利 EPS 搭配不同合理本益比情境，觀察目前指數位在便宜、合理或偏貴區域。」圖型優先考慮：EPS 情境、PE 情境、對應指數區間、現在指數位置。但仍是 Research Framework：EPS 資料來源／PE 情境／計算公式／更新頻率 正式 High Gate 核准前，不得把示意值當 production。
- 圖D ⚠️主要風險：不要把 16 燈全部鋪開；第一層只顯示最需要注意的 3～5 項、方向、是否惡化；完整 16 燈放「查看全部指標」。

## 五、🎯 標的頁指定版
「找標的」＋「查一檔」整合成同一主頁。頁首「目前市場裡有哪些值得研究的股票？」
- 第一區｜產業機會：產業強弱圖。上方「先找正在變強的產業，再從產業裡找公司；避免只看單一股票短線漲跌。」呈現：產業、基本面成長、相對強弱、法人／籌碼、估值、資料可信度。沒有正式資料的維度不得讓 AI 補。
- 第二區｜候選標的：簡潔表格／卡片：標的｜產業｜基本面｜估值｜籌碼｜狀態。優先基本面，再看價格與技術面。
- 第三區｜單一股票：點候選股或搜尋代碼後，同頁展開：EPS／營收、財報趨勢、估值、籌碼、風險、為什麼值得看、為什麼不能買／資料不足。不要再另外要求使用者去另一主頁「查一檔」。

## 六、💼 持股頁指定版
必須先按「投資目的」分：🌱存股／📈資本利得。ETF／個股不是分類規則（ETF 可以是資本利得，個股也可以是存股）。正式分類必須來自客戶設定／既有可追溯設定；沒資料顯示「未分類」，不得 AI 猜。
首屏最上面先放「🤖 AI 投資總結（持股摘要部分）」，只顯示：目前有沒有需要換股、有沒有需要減碼、有沒有產業曝險過高、是否建議降低總持股比、本期最重要 1～3 個行動。下面才放圖表。
- 🌱存股區：「我的長期資產現在健康嗎？」圖表優先：存股績效（總報酬、配息、現金流、長期績效走勢）；存股配置（ETF／個股、產業、核心部位、集中度）；存股健康（基本面是否惡化、配息品質、是否仍符合長期持有理由）。不要因短線價格波動就叫長期存股換股。
- 📈資本利得區：「哪些部位還有成長動能？哪些應該汰弱換強？」圖表優先：資本利得績效、產業曝險、成長動能、換股候選；最後直接列：續抱／注意／減碼／換股候選。
- 進階分析（Level 3，保留不刪功能、只降階）：235燈、80/20、VaR、壓力測試、燈牆、詳細門檻、原始 digest、資料工程診斷。

## 七、產業趨勢是正式新增主線
不是純 UI。客戶要 AI 幫忙回答：「產業世代是否正在改變？」「我的持股是不是還押在正在退潮的產業？」「下一個成長產業在哪裡？」
先盤點既有資料是否支援：產業營收、EPS／獲利成長、資本支出、產業相對強弱、法人配置、籌碼、估值、景氣循環、產業事件、技術世代變化。不夠就列資料缺口。不得用 LLM 常識直接宣告某產業已衰退或已崛起。

## 八、👤 我的頁指定版（極簡）
只放：1 Google 帳號 2 目前 Sheet 3 目前投資組合 4 觀察清單 5 投資策略分類（🌱存股／📈資本利得）6 必要設定。不放投資分析。

## 九、One AI Brain 指定輸出（固定分五段）
① 市場：台股趨勢、國際趨勢、總體風險、建議總持股水位
② 產業：變強產業、轉弱產業、結構性變化、資料不足時必須說不知道
③ 存股：是否繼續持有、基本面／現金流是否惡化、是否需要降低配置
④ 資本利得：哪些續抱／減碼／換股、候選產業／候選標的
⑤ 本期行動：只給最重要 1～3 項
每個結論旁必須能「查看依據」，展開內容至少：使用的資料、資料日期、規則／計算結果、missing、confidence／availability、AI 是否有參與。

## 十、AI 架構
Data Layer → Rule/Calculation Layer → 各頁 Structured Result → Decision Digest → One AI Brain → Investment Summary。禁止 Data → LLM → LLM 自己決定數字。AI 只整合、比較、解釋、排序與生成摘要。

## 十一、必須產出可讓客戶看懂的視覺 wireframe（不要只給文字規格）
1 📊市場—桌面＋手機首屏 2 🎯標的—桌面＋手機首屏 3 💼持股—桌面＋手機首屏 4 👤我的—桌面＋手機首屏 5 🤖AI投資總結展開狀態。風格：深色、卡片、圖表優先、少文字、第一屏可行動。若無法直接產圖，至少提供 HTML wireframe／Streamlit 靜態 mockup，但不得因此進 production implementation。

## 十二、Coverage
Old UI capability → New 4-page destination → 是否首層 → 是否進階層 → 是否仍未接線 → 是否被保留。簡化畫面 ≠ 刪除能力；任何既有重要投資判斷不得因為變 4 頁而消失。

## 十三、正式落盤（一次 docs PR）
設計規格寫入 docs/vnext/；正式裁示／方向寫入 docs/DECISIONS.md；待辦 docs/BACKLOG.md；階段狀態 docs/PROJECT_STATE.md；Resume Point docs/HANDOFF.md。

## 十四、停止條件
完成：指定版 4 頁 wireframe、AI Brain architecture、Decision Digest、產業資料盤點、Old→New Coverage、資料缺口、實作批次建議、GitHub 正式落盤。之後 STOP at Customer Design Gate，不得進 production UI code；只把真正需要客戶決定的少量問題交回。

## 保護規則（沿用）
舊 UI 不刪；Risk Cap、threshold、weights、正式趨勢定義、估值公式、投資語意不得未經 Gate 修改；Missing semantics 不變（missing≠0、≠neutral）；尚未證實的推論維持 INFERENCE；現有 AI summary 只是技術基礎，不等於全站 AI 總管；HI-1～HI-6 未核准。
```

### DEC-092｜D2.5 Customer Design Gate 裁示：Q1 策略分類（portfolio_id+symbol）／Q2 趨勢（均線僅參考、正式定義另列 High Gate）／Q3 風險桶／Q4 沿用既有建議動作／Q5 產業趨勢先研究／Q6 D2 殼過渡保留＋D2 驗收通過＋設計方向核准（客戶 2026-10-27）
> 2026-10-27 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-092"` 0 命中、最大為 DEC-091）。**本條只落盤客戶的 Design Gate 裁示，不改任何產品 code／測試／navigation，不改 CLAUDE.md／PROJECT_RULES.md。** 來源類別＝**客戶 Customer Design Gate 裁示**（回覆 DEC-091 之 D2.5 設計文件；客戶原文逐字收錄於下方）。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：

```
Customer Design Gate 裁示如下。不是「全照推薦」，請依以下內容正式落盤後再規劃實作批次。

Q1｜策略分類

修改推薦。

策略分類不得以 "symbol" 作為全站唯一鍵。

第一版採：

"portfolio_id + symbol -> strategy"

strategy：

- 🌱 存股
- 📈 資本利得
- 未分類

原因：同一代號在不同投資組合可能有不同投資目的。

若未來確認需要「同一投資組合、同一代號同時拆成兩種策略」，再另開 Gate 研究 lot／sub-position 級分類；本批不要過度設計。

分類屬客戶設定，存入既有 Google Sheet SSOT 路線可以接受。

但新增寫入能力必須遵守現有 writer／WIF／安全治理，不得因此放寬其他 Sheet 寫入權限。

---

Q2｜台股／國際趨勢

大致照推薦。

圖 A：
可先畫既有指數／均線作為「視覺參考線」，但明確標示：

「均線為參考，不等於正式台股趨勢判斷。」

圖 B：
可以沿用目前已有且可追溯的國際資料系列作展示。

在正式趨勢定義完成以前：

- 台股趨勢 = ⬜ 尚未定義
- 國際趨勢 = ⬜ 尚未定義

不得由 AI／均線／單一指標自行補成多空結論。

正式「台股趨勢」與「國際趨勢」定義另列 High Gate，之後需要包含：

- 判斷資料
- 時間尺度
- 規則／公式
- missing semantics
- 驗證／回測
- AI 可使用範圍

---

Q3｜市場第一層風險

照推薦，但加一條：

五個風險桶各取最需要注意的一項。

如果某一桶沒有足夠資料：
顯示 "⬜ 資料不足／無法判定"，不得硬選一個「最差」。

第一層最多 3–5 項；完整燈號與細節留在「查看全部指標／查看依據」。

---

Q4｜持股動作／本期行動

照推薦。

第一版沿用既有已正式存在的「建議動作」與既有優先序。

暫時不要新增「續抱／注意／減碼／換股」的新判斷語意或四態規則。

One AI Brain 可以：

- 整理
- 解釋
- 比較
- 排出本期最重要 1–3 項

但不得創造既有規則層沒有產出的買賣動作。

---

Q5｜產業趨勢

修改推薦。

「產業單季營收 YoY 中位數＋覆蓋率」可以作為 第一個候選維度／baseline research，但不得直接定義為正式「產業趨勢」。

我要判斷的是較長期的：

「產業是否正在變強／轉弱／發生世代結構變化？」

因此先開研究，不導入 production。

研究至少盤點：

1. 產業營收 YoY／成長廣度
2. EPS／獲利趨勢
3. 產業相對強弱
4. 法人配置／籌碼
5. 資本支出
6. 景氣／終端需求
7. 估值
8. 結構性技術／產業世代變化

先盤點 repo 已有可追溯資料，再提出：

- 可直接使用
- 需要轉換
- 缺資料
- 新來源候選

新外部來源目前只研究：
不得接入 production、不得新增 API／MCP，正式導入前另開 Customer Gate。

AI 在正式產業規則完成以前不得自行判定產業興衰。

---

Q6｜D2 與 Boot Incident

採：

1. D2 導覽殼作為過渡版保留，直到新的四頁架構完成替代。
2. 原 D2 的 ⚡／🩺 等佔位主頁設計已被 D2.5 四頁 IA supersede，不再作為最終設計。
3. D2 過渡版功能驗收視為通過。
4. Boot incident 記錄更新為：
   - 實機已恢復正常啟動／可瀏覽新版頁面
   - root cause 仍未確認
   - 不得寫成已證實為 stale module
   - boot smoke guard 保留
5. 舊 UI Removal Gate 仍然有效；新四頁未完成實機驗收以前不得刪除舊 UI。

---

設計方向核准

D2.5 以下大方向核准：

- 固定四主導航：
  - 📊 市場
  - 🎯 標的
  - 💼 持股
  - 👤 我的
- 🤖 One AI Brain 為全站共用，不是第五主頁
- 圖表優先
- 每張圖上方有白話說明
- Level 1 結論 → Level 2 圖表／原因 → Level 3 依據／原始資料
- 手機優先
- 💼 持股分 🌱存股／📈資本利得／未分類
- ETF／個股不得自動等同策略分類
- AI 不創造數字、門檻、missing、趨勢或標的
- EPS×PE 保留 Research Framework，正式公式仍需 High Gate

現有 wireframe 可作為後續 UI 的視覺基準，不要重新發明另一套 IA。

---

落盤要求

這次 Customer Gate 已產生正式結論。

請先更新並合併：

- "docs/DECISIONS.md"
- "docs/vnext/NEWUI_D25_PLAN_2026-10-27.md"
- 對應 D2.5 spec／AI Brain／產業研究文件
- "docs/BACKLOG.md"
- "docs/PROJECT_STATE.md"
- "docs/HANDOFF.md"

確保下一個新對話可以直接恢復，不依賴聊天記憶。

落盤完成後，再依 DEC-084 判斷下一個實作批次需要的最小 Model × Effort。

不要直接開始大批 product code。

先提出最合理的第一個實作批次；若該批不需要新的 Customer Gate，可依既有 Auto-Ship／Silent Autonomous Cruise 規則執行。
```

- **撰寫組摘要，非客戶原文**（以上方 fence 為準，若摘要與原文有出入，以原文為準）：
  - **Q1 策略分類（修改推薦）**：分類鍵＝**`portfolio_id + symbol -> strategy`**，strategy 三值＝🌱存股／📈資本利得／未分類；**否決**以 symbol 為全站唯一鍵（同一代號在不同投資組合可能有不同投資目的）。lot／sub-position 級分類**本批不做**，若未來確認需要再另開 Gate 研究。分類屬客戶設定，存入既有 Google Sheet SSOT 路線**可接受**；但**新增寫入能力必須遵守現有 writer／WIF／安全治理，不得因此放寬其他 Sheet 寫入權限**（仍屬 HI-5 寫入面，實作前仍須符合 writer 治理；本條不等於寫入授權）。
  - **Q2 台股／國際趨勢（大致照推薦）**：圖 A 可畫既有指數／均線作「視覺參考線」，並**必須標示**「均線為參考，不等於正式台股趨勢判斷。」；圖 B 可沿用目前已有且可追溯的國際資料系列展示。正式定義完成前，**台股趨勢＝⬜ 尚未定義、國際趨勢＝⬜ 尚未定義**，不得由 AI／均線／單一指標補成多空結論。正式定義**另列 High Gate**，須含：判斷資料、時間尺度、規則／公式、missing semantics、驗證／回測、AI 可使用範圍。
  - **Q3 市場第一層風險（照推薦＋一條）**：五個風險桶**各取最需要注意的一項**；某桶資料不足時顯示「⬜ 資料不足／無法判定」，**不得硬選最差**；第一層**最多 3–5 項**；完整燈號與細節留在「查看全部指標／查看依據」。
  - **Q4 持股動作／本期行動（照推薦）**：第一版**沿用既有已正式存在的「建議動作」與既有優先序**；暫不新增「續抱／注意／減碼／換股」四態或新判斷語意。One AI Brain 可整理／解釋／比較／排出本期最重要 1–3 項，但**不得創造既有規則層沒有產出的買賣動作**。
  - **Q5 產業趨勢（修改推薦）**：「產業單季營收 YoY 中位數＋覆蓋率」僅為**第一個候選維度／baseline research**，**不得定義為正式「產業趨勢」**。先開研究、不導入 production；至少盤點八項：(1) 產業營收 YoY／成長廣度 (2) EPS／獲利趨勢 (3) 產業相對強弱 (4) 法人配置／籌碼 (5) 資本支出 (6) 景氣／終端需求 (7) 估值 (8) 結構性技術／產業世代變化。**先盤 repo 既有可追溯資料**，再分「可直接使用／需要轉換／缺資料／新來源候選」。新外部來源**只研究**：不得接 production、不得新增 API／MCP，正式導入前另開 Customer Gate。AI 在正式產業規則完成前**不得自行判定產業興衰**。
  - **Q6 D2 與 Boot Incident**：(1) D2 導覽殼為**過渡版保留**，直到新四頁架構完成替代；(2) 原 D2 的 ⚡／🩺 佔位主頁設計已被 D2.5 四頁 IA **supersede**，不再是最終設計；(3) **D2 過渡版功能驗收視為通過**；(4) Boot incident 更新為：實機已恢復正常啟動／可瀏覽新版頁面、**root cause 仍未確認**、**不得寫成已證實為 stale module**、boot smoke guard 保留；(5) **舊 UI Removal Gate 仍有效**，新四頁未完成實機驗收前不得刪舊 UI。
  - **設計方向核准清單**：固定四主導航（📊 市場／🎯 標的／💼 持股／👤 我的）；🤖 One AI Brain 全站共用、**不是第五主頁**；圖表優先；每張圖上方有白話說明；Level 1 結論 → Level 2 圖表／原因 → Level 3 依據／原始資料；手機優先；💼 持股分 🌱存股／📈資本利得／未分類；ETF／個股不得自動等同策略分類；AI 不創造數字、門檻、missing、趨勢或標的；EPS×PE 保留 Research Framework，正式公式仍需 High Gate。**現有 wireframe 可作後續 UI 的視覺基準，不要重新發明另一套 IA。**
  - **落盤要求**：更新並合併 `docs/DECISIONS.md`、`docs/vnext/NEWUI_D25_PLAN_2026-10-27.md`、對應 D2.5 spec／AI Brain／產業研究文件、`docs/BACKLOG.md`、`docs/PROJECT_STATE.md`、`docs/HANDOFF.md`，確保新對話可不依賴聊天記憶恢復；落盤後依 DEC-084 判斷下一個實作批次的最小 Model × Effort；**不要直接開始大批 product code**，先提出最合理的第一個實作批次，若該批不需要新 Customer Gate，可依既有 Auto-Ship／Silent Autonomous Cruise 規則執行。
- **範圍**：產品／UI（New UI D2.5）＋資料契約（策略分類）＋研究（產業趨勢）｜**日期**：2026-10-27｜**決策者**：客戶｜**狀態**：生效（待 PR 合併）。
- **與 DEC-091 的關係（append-only；舊條文原文不改，只在 DEC-091／089／090 條目加註）**：DEC-091 的「待客戶 Design Gate 裁示」狀態**由本條解除**（D2.5 設計方向核准，並對 Q1～Q6 裁示）。DEC-089 G1＝C 六向導覽、DEC-090 形式 (b)（兩層側欄）及 ⚡／🩺 佔位頁文案**由本條 supersede**（Q6：殼僅作過渡版保留；最終 IA＝固定四主導航）——舊條文原地加註、不刪。**DEC-089 其餘項（G2～G7 中未被四頁 IA 取代者、7 項補充執行條件、確認表）與 HI-1～HI-6 未核准狀態不變**；DEC-091 的授權範圍限制（不授權 HI-1～HI-6、不授權 EPS×PE 當 production、不授權新增資料來源）**不因本條放寬**。
- **效力邊界（⛔ 不是實作授權）**：本條是**設計方向與資料口徑的裁示**，**不是**施工授權：(1) 不授權 Sheet 寫入面（HI-5；策略分類寫入須另符合 writer／WIF／安全治理並走既有 Gate）；(2) 不授權新增 API／MCP／新外部資料來源／接 production；(3) 不授權正式台股／國際趨勢結論、正式產業趨勢、EPS×PE、Risk Cap、四態規則（皆另列 High Gate／Customer Gate）；(4) 不授權刪舊 UI；(5) 實作批次須先過 DEC-084 Model×Effort 與 boot import smoke。保護規則（沿用 DEC-091）全部不變。
- **與其他 DEC 的關係**（append-only，單組讀法）：DEC-091 **解除其待裁示狀態**；DEC-089／DEC-090 **部分 supersede**（見上）；DEC-081／083（📊 大盤／👤 我的）**不變**；DEC-019／020（舊 UI Removal Gate）**不變**；DEC-082／084／085／086／087／088 **呼叫**。不降低任何 Security／Investment／Data／CI／Audit Gate；衝突取較嚴者。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：上列摘要與「與 DEC-091 的關係」判讀由單一撰寫組產出，**沒有第二組驗過**；摘要非客戶原文。

### DEC-093｜AB-0 Decision Digest 契約的內部設計選擇（形狀、拒收名單定位、INVALID、未帶鍵持股、AI 字樣語意、不做 from_dict）（AI 總管內部，2026-10-27）
> 2026-10-27 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-093"` 0 命中、最大為 DEC-092）。**本條不是客戶裁示**，只記錄 AB-0 實作時的技術選擇，供後續批次（AB-1／AB-2a／AB-4r）與獨立 QA 對照；不改 `CLAUDE.md`／`PROJECT_RULES.md`。
- **決策者**：**AI 總管內部（技術實作，依 `CLAUDE.md` §-1.5 v3 §03-1 內部自決）；非客戶裁示**。客戶 2026-10-27 只給了 AB-0 的邊界（純資料契約＋測試；不接 AI、不接 UI、不碰 `app.py`／`shared/ia_nav.py`；`portfolio_id + symbol -> strategy` 只定型別、不發明 `portfolio_id` 來源；missing／availability／AI 參與語意要明確可測；unavailable ≠ neutral、missing 不是 0；不新增投資判斷規則）；以下各點是在該邊界內的實作選擇。
- **內容**：
  1. **契約形狀＝AB-0 落地版**：`shared/decision_digest.py`（L0、stdlib-only、frozen dataclass；`SCHEMA_VERSION="decision_digest.v1"`）。與設計草案 C §4 的差異逐項列於 `docs/vnext/NEWUI_D25_C_AI_BRAIN_DATA_2026-10-27.md` §11（例：`sources[]`→每個 Fact 自帶 Provenance、頂層 availability→逐段推導、`candidates[]` 與 `ActionRef.kind` 未納入）。**後續讀端以程式碼與 §11 為準，不以 §4 草案為準**；補回欄位＝改契約，須升 `SCHEMA_VERSION` 並過獨立 QA。
  2. **拒收名單是盡力而為，不是權威**：缺值佔位字、AI 字樣、方向字樣三份名單只擋明顯情形，換拼法即可繞過；**權威防線**＝AB-1 的 `rule_id` 允許名單（＋逐字比對 `text` 是否等於規則層輸出）與 AB-2a grounding。不得把「通過 AB-0 驗證」讀成「內容已確認無 AI／無方向判斷」。
  3. **`INVALID` 不是 MISS 概念**：`DataStatus.INVALID`＝C §4.1 D11「上游有值但不是合法數值」；值丟棄為 None，**不附** `missing_reason`（不用 `contract_drift` 頂替）；給客戶的文案屬 UI 層。`MissingReason` 與 `shared/station_specs.MISS_*` 是**對映**（`MISS_CODE_TO_REASON`），字串值不同。
  4. **缺鍵持股計數、不捏造**：上游缺 `portfolio_id` 或 `symbol` 的列不建 `HoldingEntry`，只計入 `HoldingsSection.unkeyed_count`；>0 時 holdings 不得為 available。取代 C §4「該列策略一律未分類＋NO_INPUT」的寫法——補一個鍵等於捏造身分。
  5. **「ai」「llm」字樣語意**：`Provenance.source`／`RuleRef.rule_id`／`strategy_source` 依 `[:._/-]`／空白切 token 後，token 等於 `ai`／`llm`／`genai`／`gen_ai`，或以 `gemini`／`gpt`／`claude`／`openai` 等開頭，或含「模型」、或 `ai` 緊鄰中日韓字，即拒收（名單與比對細節以程式碼為準，本條不釘死）；目的＝AI 不得成為資料來源、規則或分類來源（DEC-092 設計方向「AI 不創造數字／門檻／missing／趨勢／標的」、Q4）。副作用：真實來源名稱若恰含此 token 也會被拒，屆時由 AB-1 允許名單處理，不在 AB-0 放寬。
  6. **不做 `from_dict`**：目前沒有消費者需要反序列化；日後若需要，必須同樣嚴格（同型別檢查、同不變量），另案實作並過獨立 QA。
- **範圍**：資料契約（New UI D2.5 AB-0）｜**日期**：2026-10-27｜**狀態**：生效（隨 AB-0 PR；**待 CI／merge**）
- **來源**：分支 `ccr-fa5b6ded-9rhvoj` commits `8f85bee9`、`2184d015`、`e005e98c`（`shared/decision_digest.py` 檔頭 docstring、`tests/test_decision_digest_contract.py`）；客戶邊界見 2026-10-27 AB-0 開工指示（經總管轉交，非本條逐字收錄）。
- **與其他 DEC 的關係**：本條**不重新解釋** DEC-091／DEC-092 任何一字；DEC-092 Q1（鍵＝`portfolio_id + symbol`）、Q2（趨勢＝尚未定義）、Q4（沿用既有建議動作與優先序、AI 不得創造動作）是本契約的**上位約束**，衝突時以 DEC-092 為準。DEC-084（Model×Effort）、DEC-003（內部自決區）**呼叫**。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本條由單一撰寫組依程式碼與執行組回報撰寫；契約已過兩輪獨立 QA 並修正，**最終獨立複驗見 PR**，本條不宣稱已通過；第 1 點引用的差異清單為單組比對，未經第二組逐項驗證。


### DEC-094｜AB-1 Decision Digest Builder／rule_id 允許名單的內部設計選擇（AI 總管內部，2026-10-27）
> 2026-10-27 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-094"` 僅命中 BACKLOG／HANDOFF／PROJECT_STATE／AB-1 規格的「預告將寫 DEC-094」，`docs/DECISIONS.md` 無此條、最大為 DEC-093）。**本條不是客戶裁示**，只記錄 AB-1 實作時的技術選擇，供後續批次（AB-2a／AB-4r）與獨立 QA 對照；不改 `CLAUDE.md`／`PROJECT_RULES.md`。
- **決策者**：**AI 總管內部（技術實作，依 `CLAUDE.md` §-1.5 v3 §03-1 內部自決）；非客戶裁示**。客戶 2026-10-27 給的邊界：在已合併 AB-0 契約上建純函式 Builder；不新增投資規則、不接 AI／UI、不碰 `app.py`／`shared/ia_nav.py`、不定義 `portfolio_id` 來源、不寫 Sheet。以下為該邊界內的實作選擇。
- **內容**：
  1. **落地檔案**：`shared/decision_digest_rules.py`（L0：`rule_id` 允許名單 `RULE_ID_ALLOWLIST`、Q4 優先序 `Q4_ACTION_PRIORITY`、`assert_strict`）、`src/services/decision_digest_builder.py`（L3 純函式 `build_decision_digest`，回傳前一律 `assert_strict`）；測試 `tests/test_decision_digest_rules.py`、`tests/test_decision_digest_builder.py`。**不改 AB-0**（`shared/decision_digest.py` 未動）；無新投資規則；不接 AI／UI。
  2. **`ACTION_RULE_VERSION = "action_branch.v1"` 是內部命名**：行動規則原本無版本常數，此標籤是實作者命名，**不是客戶核准的規則版本**；日後 `action_branch` 條件或優先序變更必須升版並過審。允許名單成員只收程式已存在的識別字（`risk_cap`→`RISK_CAP_RULESET_VERSION`；`cut`／`take_profit_force`／`take_profit_partial`／`pause_add`／`add` 的字串複本，測試 pin 住與 `dividend_station.ACTION_*` 相等）；`premium`／`cruise` 刻意不收。
  3. **`rule_wrong_location`（位置維度）＝超出規格 B.1 的實作者新增**：允許名單除了「id＋版本是否存在」也管「放在哪」（`risk_cap` 段只能引 `risk_cap`；持股事實與行動只能引行動分支碼；市場事實／定義狀態段維持 AB-0 的 rule 選填，有帶就必須在名單內）。**語意 QA 建議保留**；它只**收緊**（更多拒收），不放寬任何 AB-0 語意。
  4. **資料異常列整列不搬行動（fail-safe）**：帶非空 `_invalid_lights`／`_invalid_inputs` 的站內列，其行動整列不進 Digest。方向＝只減不增；AB-0 契約沒有對應的揭露欄位，故**不揭露**（客戶看不到「有一列因資料異常被略過」——此為已知限制，若要揭露屬改契約，須升 `SCHEMA_VERSION`＋獨立 QA）。
  5. **Fail loud**：`held`／`is_loaded` 非 `bool`／`None` → `TypeError`；輸入型別不對一律 `TypeError`；建議動作文字佔位字（如「—」類）降級為 `MISSING`，不當成可顯示的行動文字；可搬運的行動列 `建議動作` 非非空 str → `ValueError`；**重複持股列**、**同 ticker 重複行動列**皆 fail loud（不默默取其一）。
  6. **v1 不攜帶**：個股路徑換股動作（`assess_stock`，無分支碼、無 Q4 rank）與 `flag_take_profit`（衛星 ≥15%）——排位須客戶裁示（BACKLOG `AB1-STOCK-PATH-AND-TAKE-PROFIT-RANK`）。其餘沿 `docs/vnext/NEWUI_D25_AB1_BUILDER_SPEC_2026-10-27.md`：無日期事實＝`MISSING`＋`NO_INPUT`（builder 不發明日期）、`SourceStamp` 由呼叫端傳入、行動截斷至 `MAX_ACTIONS`(3)、Risk Cap 取 `macro_state['exposure_limit_pct']`（非 `AllocationDecision.cap_pct`）。
- **已知限制與不改項（誠實揭露）**：
  - **AB-0 尚無「actions AVAILABLE 且 0 筆」的產生路徑**：「沒有要做的事」與「判不出來」在 v1 無法區分，0 筆行動＝UNAVAILABLE＋`NO_INPUT`。
  - **production 在 AB-4r 前不可達**：`portfolio_id` 無來源（AB-4r 才定義），AB-1 產出的持股列都沒有鍵；無任何 production caller。
  - 上游 L4 缺口（cap 與 `final_hi` 交叉、health 範圍、舊 `snapshot_ts` 不推 STALE）屬規格明言／上游責任，本批不補（L4 等已知不改項）。
  - `snapshot_ts` 格式為 `macro_state_locker._TIMESTAMP_FMT` 的**複本**（L3 之間不互相 import）→ BACKLOG `AB1-SNAPSHOT-TS-FORMAT-SSOT`；百分比定義域 0..100 為 builder 內字面值 → `AB1-PERCENT-DOMAIN-CONSTANT`；`建議動作` 逐字攜帶而該文字可能含 "AI" 字樣，與 AB-0「AI 不得出口」精神的關係未判斷 → `AB1-ACTION-TEXT-AI-WORDING`（AB-4 前須判斷）。
- **範圍**：資料搬運層（New UI D2.5 AB-1）｜**日期**：2026-10-27｜**狀態**：生效（~~隨 PR #951；**待 CI／merge，尚未合併**~~ 已隨 PR #951 合併，squash main `6a4c0628`，CI 綠（run 1775）（2026-10-27 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；決策內容未改）
- **來源**：分支 `ccr-fa5b6ded-9rhvoj` commits `3784a25`、`07cd93c`（`shared/decision_digest_rules.py`、`src/services/decision_digest_builder.py` 檔頭 docstring、兩個測試檔）；規格 `docs/vnext/NEWUI_D25_AB1_BUILDER_SPEC_2026-10-27.md`；客戶邊界見 2026-10-27 AB-1 指示（經總管轉交，非逐字收錄）。
- **與其他 DEC 的關係**：不重新解釋 DEC-091／DEC-092／DEC-093；DEC-092 Q3／Q4（行動沿用既有建議動作與優先序、不得創造動作）、Q1（鍵＝`portfolio_id + symbol`）為上位約束，衝突以 DEC-092 為準。DEC-084（Model×Effort）、DEC-003（內部自決區）呼叫。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本條由單一撰寫組依 diff／commit 與實作者回報撰寫。**突變 98/98 killed 為實作者自列**；兩組獨立 QA（對抗式＋語意）已跑並已回修（`07cd93c`），但**QA 回修後未重跑突變**；沙箱為 Python 3.13，**CI 的 Python 3.11 尚未實跑**；本條第 3 點「語意 QA 建議保留」為總管轉述，未逐字附 QA 報告。本條不宣稱 PR 已通過 CI 或已合併。

### DEC-095｜AB-2a Grounding／Validator 與規則式摘要的內部設計選擇（句型白名單取代黑名單、降級四態、INVALID 整份不保留、Risk Cap 保守顯示）（AI 總管內部，2026-10-27）
> 2026-10-27 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-095"` 0 命中、`docs/DECISIONS.md` 最大為 DEC-094）。**本條不是客戶裁示**，只記錄 AB-2a 實作時的技術選擇，供後續批次（AB-2b／AB-4r／AB-5／AB-6）與獨立 QA 對照；不改 `CLAUDE.md`／`PROJECT_RULES.md`。
- **決策者**：**AI 總管內部（技術實作，依 `CLAUDE.md` §-1.5 v3 §03-1 內部自決）；非客戶裁示**。邊界來自 `docs/vnext/NEWUI_D25_PLAN_2026-10-27.md` §5 序 4：G1～G6 規則式驗證、無 AI 版規則式摘要、統一「AI 不可用」型別；不新增 AI 傳輸、不呼叫 LLM、不接 UI、不改 AB-0／AB-1（`shared/decision_digest.py` 與 AB-1 兩檔未動，`git diff origin/main --stat` 僅新增檔與本規格）。
- **內容**：
  1. **落地與降級四態**：L0 `shared/decision_digest_terms.py`（具名常數／模板）、`decision_digest_validator.py`（`assess_digest`、四態 `SummaryState`）、`decision_digest_grounding.py`（`SummaryDraft`／`Lit`／`Ref`、`SHAPES`、`check_summary`），L3 `src/services/decision_digest_summary.py`（`build_rule_summary`）。四態：INVALID（contract drift，不輸出任何投資結論）／UNAVAILABLE／PARTIAL／VALID；availability 只由資料推導，`SummaryResult` 的 `state` 等欄位由 Digest 建構時推導、不可手造。AB-0 `validate()`、AB-1 `validate_rule_ids`／`validate_action_order` 原樣沿用，AB-2a 只**新增收緊**（文字字元類別、引用 id 保留前綴／碰撞、symbol 字元集、單位、缺值原因家族、市場事實標籤歧義），不放寬任何 AB-0／AB-1 語意。
  2. **G1～G6 與 C §2.4 字面的差異（以正式文件為準，逐項標明）**：(a) **G1 產業名稱結構性消失**——C §2.4 的允許名單寫 `holdings[]`／`candidates[]`／`industry_trend[]`，AB-0 Digest 沒有 candidates／industry_trend，且句型根本沒有能放產業名的位置，故代號只能來自持股／行動目標；(b) **引用 id 空間擴充** `section:*`／`holding:*`（持股用長度前綴編碼 `holding:<len>:<portfolio_id>:<symbol>`），因 AB-0 無 C §4 草案的 `sources[]`，定義狀態段／缺值段沒有 fact 可引；(c) G3 洗白字眼不再是執行期黑名單，改為「標示語由模板產生、句型前置條件綁項目狀態」；(d) G5 本檔只回報事實，不執行「退回規則式」政策（屬 AB-2b／消費端）；(e) G6 丟棄無 `Ref` 的句子，消費端只能用 `surviving`；G7 不在本批。
  3. **主防線由「黑名單字眼＋quote 豁免」改為「句型白名單」**：初版 G3／G4 靠黑名單加 quote 豁免；兩組獨立 QA（語意治理＋紅隊）實測出 bypass（自由文字夾帶結論、同形異字／簡體／同義詞／中文數字、標示語子字串偽造、行動句加字換代號、多 ref 池化、搭便車 section ref 等）。總管決定**不補名單**（黑名單擋不完），改為讓壞句子沒有地方可以寫：一句話＝`Lit`（`TEMPLATES` 的模板 id）／`Ref`（對 Digest 項目的欄位展開）的 segment 序列，**沒有任何型別能承載任意文字**，骨架須吻合唯一句型（`SHAPES`），同一 slot 只能指同一項目；文字只在 `SummaryResult.lines`／`render_draft` 由「Digest＋模板」展開。黑名單降級為**建置期 lint**（掃我們自己寫的模板／標籤／標示語）。後續歷經三輪 re-QA 與回修（總管轉述，QA 報告未逐字附）。**代價**：合法的 AI 改寫也無法通過，只能挑句型（見第 9 點）。
  4. **INVALID 整份不保留（單組判斷，待覆核）**：違規涉及跨物件不變量（fact_id 唯一、evidence 指向可用事實、行動 vs 持股）代表 builder 違反契約、影響範圍未知；AB-0 的 `evidence_refs` 本身是跨段依賴，無法證明段落彼此獨立 ⇒ `sections=()`、`retained_sections=()`，`notices` 只指出哪一段 invalid／哪個閘門失敗／其他段落未保留。替代方案「保留未受影響段落」需先證明段間無依賴，不採。**此為承重判斷，單組，待第二組覆核。**
  5. **Risk Cap 比任務字面更保守**：摘要連 `exposure_lo/hi_pct` 也**不顯示**，只放 DEC-081 Q2-2 客戶核准的卡面措辭（`risk_wording`，不展開任何 Risk Cap 數值／資料日）；理由＝`final_hi` 已含 cap，顯示數值等於繞過 DEC-081 Q2-2。**是否放行顯示屬 RC-VISIBILITY Gate，不在本批決定。** 市場段可得性推導**不含** risk_cap（它的數字本就不顯示，不該左右市場段可得性）。
  6. **VALID 在現行契約下不可達**：產業趨勢與策略分類的正式定義未核准，產業段恆 UNAVAILABLE、市場段恆含「尚未定義」的趨勢；這是誠實，不是 bug（已有測試）。
  7. **`SummaryResult` 僅 `rule_only`**：`mode` 必須是 AB-0 既有 `AiParticipation` 且與 `digest.ai_participation` 一致，本批只允許 `rule_only`，`ai_explained`／`ai_rejected` 建構一律 `ValueError`（留給 AB-2b）；`build_rule_summary` 對合法但非 `rule_only` 的 Digest 明確 `ValueError`，對不合規 Digest 回 INVALID 結果、不 raise。**assess 與 build 一致性**：assess 放行者 build 不得 raise、assess 擋下者 build 回 INVALID（含 `:` 鍵的 300 組 fuzz 與 `terms.SUPPORTED_UNITS`／`SHAPE_UNITS` import 時比對，不一致 `RuntimeError`）。
  8. **「AB-2b 的 AI 只能選句型＋填 slot」是建議，待 AB-2b Decision Gate，不是既成事實**：自由文字的 AI 輸出不可能通過本檢查器，這是設計；若客戶要自然語言潤飾須另走 Gate 重新決定。`mode` 何時才能是 `ai_explained` 同屬建議。本批已鎖死的只有 `SummaryResult` 目前只接受 `rule_only`。另：`structural_failure` 沒有對應的 G id，而 AB-0 的 `ai_rejected` 要求 `ai_failed_checks` 非空 ⇒ **AB-2b 須自行決定映射**（BACKLOG `AB2B-INTERFACE-NOTES`）。
- **已知殘留限制（誠實揭露，細節見規格 §9）**：(a) **A10**：`ActionRef.text` 與其 `rule`（分支碼）未綁定，Digest 層放行「行動文字與規則不對應」——AB-1 缺口、本批不改 AB-1，測試 `test_known_gap_a10_…` 釘住現況 → BACKLOG `AB1-ACTION-TEXT-RULE-BINDING`；(b) 規則層原文（`Fact.text`／`ActionRef.text`）若本身有誤導，摘要**忠實轉述** → `AB2A-RULE-TEXT-FAITHFUL-RELAY`；(c) 句型選擇權仍在呼叫端（可省略 ok 事實、調整同段順序，行動段除外），受限證據的過期無法揭露 → `AB2A-COMPLETENESS-CALLER-CHOICE`；(d) `copy`／`pickle`／`object.__setattr__` 同行程繞過**不在威脅模型內**，不防；(e) Unicode `Cn`（未指派）判定依 Python 的 Unicode 資料庫版本：沙箱 3.13 與 CI 3.11 不同，舊環境可能過度拒收（fail-closed，不會漏擋）；(f) 指數代號（如 `^TWII`）被 `bad_symbol` 擋，`SYMBOL_PATTERN` 為保守白名單、新代號格式 fail-closed → `AB2A-SYMBOL-PATTERN-REVIEW`；(g) `number_literal` 對 numpy float32 顯示長尾小數（Digest 數值本應為 Python float）；(h) 未分類持股不個別列出，只以整體句涵蓋。
- **範圍**：資料驗證／規則式摘要層（New UI D2.5 AB-2a）｜**日期**：2026-10-27｜**狀態**：生效（~~隨 AB-2a PR；**PR 待開，implementation complete／waiting CI，待 merge，尚未合併**~~ **已合併 PR #953（squash，main `5c9b2750`，CI 綠；Fast checks 與 Slow tests 皆 success）**（2026-10-27 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）））
- **來源**：分支 `ccr-fa5b6ded-9rhvoj` commits `949d824`、`9e129d3`、`8eb90c3`、`8e7cfc7`（`shared/decision_digest_{terms,validator,grounding}.py`、`src/services/decision_digest_summary.py`、`tests/test_decision_digest_{validator,grounding,round2,summary}.py`、`tests/decision_digest_factory.py`）；規格 `docs/vnext/NEWUI_D25_AB2A_SPEC_2026-10-27.md`（§7 內部決定、§8 突變、§9 殘留）。
- **與其他 DEC 的關係**：不重新解釋 DEC-091／DEC-092／DEC-093／DEC-094；DEC-092 Q2（趨勢＝尚未定義）、Q3／Q4（行動沿用既有建議動作、AI 不得創造動作）、DEC-081 Q2-2（Risk Cap 卡面措辭）為上位約束，衝突以其為準。DEC-084（Model×Effort）、DEC-003（內部自決區）呼叫。**未經客戶**；未動 AB-0／AB-1。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本條由單一撰寫組依 diff／規格與實作者回報撰寫。**突變 356 個（348 killed／8 等價逐一論證／0 倖存）清單由實作者自列**；另有 QA 紅隊三輪各自獨立設計突變（共約 170 個，總管轉述），不等於獨立複跑實作者的清單。規格檔頭仍寫「回修版未經第二組獨立複驗」，後續三輪 re-QA 結論為總管轉述、未逐字附報告。**沙箱為 Python 3.13，CI 為 3.11 尚未實跑**；沙箱缺 `markdown_it`（fast lane 須 deselect 1 項，待 CI 實跑）。承重判斷（INVALID 不保留、句型白名單完備性、Risk Cap 保守顯示、VALID 不可達）**均為單組判斷**。~~本條不宣稱 PR 已通過 CI 或已合併。~~ 補記（2026-10-27 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））：已合併 PR #953（squash，main `5c9b2750`，CI 綠；Fast checks 與 Slow tests 皆 success）。PR #953 CI 首輪紅燈兩項：(1) AB-2a 測試 `test_a8` 的 Python 3.11 `ValueError`／3.13 `TypeError` 差異（已修）；(2) `test_c1_observability::test_old_rows_unchanged_after_append` 與 cron 資料耦合（main `aacdb9e` 起 base 即紅，非 AB-2a 引入；只改該測試，一併併入 #953）。規格檔仍寫「回修版未經第二組獨立複驗」與實況一致，第四輪小修只經實作者自驗。

### DEC-096｜AB-4r 策略分類唯讀契約的內部設計選擇（`portfolio_id` 來源、`strategy_class` 獨立分頁、缺值／未分類／不合法／衝突語意、零寫入）（AI 總管內部，2026-10-28）
> 2026-10-28 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-096"` 0 命中、`docs/DECISIONS.md` 最大為 DEC-095）。**本條不是客戶裁示**，只記錄 AB-4r 實作時的技術選擇，供接線批（`AB4R-WIRE-BUILDER`）、AB-4w 與獨立 QA 對照；不改 `CLAUDE.md`／`PROJECT_RULES.md`。
- **決策者**：**AI 總管內部（技術實作，依 `CLAUDE.md` §-1.5 v3 §03-1 內部自決）；非客戶裁示、不得引用為客戶裁示**。上位約束＝DEC-092 Q1（鍵＝`portfolio_id + symbol`，值＝存股／資本利得／未分類，未分類不得預設、AI 不得猜）；邊界來自 `docs/vnext/NEWUI_D25_PLAN_2026-10-27.md` §5 序 5：L1 唯讀、缺值＝未分類、`portfolio_id` 來源在此明定；不含寫入、不含 UI；現有 5 欄表頭不得破壞。
- **內容**（細節以規格 `docs/vnext/NEWUI_D25_AB4R_SPEC_2026-10-27.md` 為準）：
  1. **`portfolio_id` 來源**：`derive_portfolio_id(sheet_id, portfolio_name)`＝`"pfv1-"`＋`sha256((sanitize_sheet_id(sheet_id) + "\x00" + portfolio_name.strip()).encode("utf-8")).hexdigest()[:20]`（L0 `shared/strategy_class_schema.py`；常數 `PORTFOLIO_ID_PREFIX="pfv1-"`、`PORTFOLIO_ID_HEX_LEN=20`）。名稱只 `strip`（與 `gsheet_portfolio` 篩組合方式一致；不做 NFKC／大小寫折疊）；任一為空／非 str／sid 消毒不過 → `ValueError`，不退回任何預設 Sheet。
  2. **候選比較（摘要，完整表見規格 §3.1）**：A. sheet_id＋名稱原文拼接（鍵含使用者原文、會被 AB-0 `_key_problem` 拒收，且把 Sheet ID 全文帶進 Digest）✗；**B. 雜湊截 20 hex＋版本前綴 ✓**（零寫入、決定性、字元集 `[a-z0-9-]` 必過 AB-0／AB-2a、不同 Sheet 同名不互撞、不外洩 ID 與名稱）；C. 只用名稱（不同 Sheet 同名互撞＝錯配分類）✗；D. 新增 ID 欄（需寫入＝HI-5，且動 `portfolios` 表頭）✗；E. Sheets developerMetadata（需寫入 API 與 scope 審查）✗。選 B＝唯讀批次唯一同時滿足上列條件者；`pfv1-` 前綴讓日後換演算法時新舊 id 不互撞。
  3. **儲存位置**：同一本 Sheet 的**獨立分頁** `strategy_class`，表頭 `name | ticker | strategy | updated_at`（`STRATEGY_WORKSHEET_NAME`／`STRATEGY_HEADERS`）；**`portfolios` 分頁 5 欄表頭不動**。
  4. **缺值／未分類／不合法／衝突語意**：Sheet 未綁定（None／空白）→ `not_bound`（不打 Google）；非空但 sid 不合法 → `ValueError`；分頁不存在 → `worksheet_missing`（⛔ 不建）；空表 → `ok`＋0 筆；表頭不符（含窄表頭、欄名重複、首列空白下有資料）→ L0 `StrategySchemaMismatchError`，L1 轉 `gsheet_portfolio.SheetSchemaMismatchError`；strategy 經 strip→NFKC 後須**恰為**「存股／資本利得／未分類」，否則 `invalid_rows`（`bad_strategy`，⛔ 不默默當未分類）；name／ticker 空或非文字格、鍵建不出 → `invalid_rows`（`missing_name`／`missing_ticker`／`non_text_cell`／`bad_key`，只記列號與代碼、不回顯內容）；同鍵不同值（含「未分類」vs 其他）或同鍵合法列＋`bad_strategy` 列 → `conflict_keys`、該鍵不入 entries（⛔ 不擇一）；「未分類」列合法但不入 entries；`lookup` 查無 → 未分類；有分類時 `strategy_source`＝`google_sheet:strategy_class`。~~孤兒列（不對應任何持股鍵）只能經 `unmatched_keys(result, holding_keys)` 揭露，不改 `lookup`。~~ 孤兒列由 `unmatched_keys(result, holding_keys: Iterable[HoldingKey])` 揭露：須傳**整本 Sheet 所有組合的持股鍵聯集**（str／bytes／Mapping 一律 `TypeError`），`conflict_keys` 不列為孤兒；純揭露、不改 `lookup`。另加嚴驗證：`InvalidRow` 的 row 須為 ≥1 的 int（拒 bool）、reason 須為 `INVALID_*` 之一；`HoldingKeysResult` 的 keys 與 rejected 不得重疊、keys 須同一 `portfolio_id`；`StrategyReadResult` 以 `HoldingKey(pid, symbol)` 重建 entries 鍵、重跑 AB-0 鍵規則。（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新：`1870472` 回修））
  5. **範圍邊界**：不寫入、不建分頁、不接 AB-1 builder、無 production caller；不改 AB-0／AB-1／AB-2a（`git diff origin/main --stat` 實查：只新增 `shared/strategy_class_schema.py`、`src/data/portfolio/strategy_class_reader.py`、兩個測試檔與規格檔，`src/data/portfolio/gsheet_portfolio.py` 為**加法式 +46 行**新增 `read_worksheet_values`，既有函式未改）。
- **已知限制（據實，細節見規格 §7）**：(a) 改名、複製 Sheet → pid 變 → 讀成未分類（fail-safe，不錯配）；刪除後重建同名組合 → 繼承舊分類；(b) 孤兒列／打錯字（如 `50` vs `0050`、大小寫不符、組合名打錯）讀成未分類、不進 `invalid_rows`，~~只能經 `unmatched_keys` 揭露（需呼叫端提供持股鍵）；~~ `unmatched_keys` 只列 entries 中對不上的鍵，不涵蓋 `conflict_keys`／`invalid_rows`／寫成「未分類」的列，且呼叫端只傳單一組合的鍵會把其他組合合法列誤報為孤兒（須傳整本 Sheet 鍵聯集）；（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新：`1870472` 回修））(c) AB-0 Digest 沒有欄位可帶 `invalid_rows`／`conflict_keys`／`unmatched_keys` ⇒ 現行契約下 Digest 端**無法區分「寫錯／衝突／孤兒」與「沒設定」**；~~(d) 接線**必改 AB-1**（builder 目前把策略寫死為未分類）→ `AB4R-WIRE-BUILDER`；~~ (d) 接線**必改 AB-1**（builder 目前把策略寫死為未分類）；且依 C §7.2 (8) 原文「在寫入面核准並上線前：Digest `holdings[].strategy_type` 一律 `未分類`」——**使用者手動建立的 `strategy_class` 分頁不得在 AB-4w（HI-5）核准上線前生效（除非重新送 Gate）**，不是開放決策 → `AB4R-WIRE-BUILDER`；（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新：`1870472` 回修））(e) 全域 `clear_read_cache()` 清不到 `read_worksheet_values` 的快取（改它＝改既有函式行為），靠 B5 失效世代或 TTL_15MIN → `AB4R-CACHE-CLEAR`；(f) emoji／標籤值（`🌱 存股`、`存股😀`）不收，判 `bad_strategy`；AB-4w 寫入端須寫純文字三值 → `AB4R-HI5-NOTICE`；(g) 截短碰撞 80 bit，機率可忽略（規格 §7 第 4 點）；(h) `read_worksheet_values` 未列入 `tests/test_sheet_safety_guards.py` `_READ_ENTRIES`，零寫入由新測試覆蓋 → `AB4R-SHEET-SAFETY-ENTRIES`。
- **範圍**：資料契約／Sheet 唯讀層（New UI D2.5 AB-4r）｜**日期**：2026-10-28｜**狀態**：生效（隨 AB-4r PR；~~**implementation complete／waiting CI，待 merge**；PR 號待開，尚未合併）~~ ~~**implementation complete／waiting CI，待 merge**；PR #955（Draft），尚未合併）（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））~~ 已合併 PR #955（squash，main `d97afec9`，CI 綠；Fast checks 與 Slow tests 皆 success，head `935df34`））（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））
- **來源**：分支 `ccr-fa5b6ded-9rhvoj` ~~commits `c2c3486`（初版）、`eb87591`（依兩組獨立 QA 回修：`unmatched_keys`、`bad_strategy` 污染改記 conflict、不可變複製、跨身分測試、不合法 sheet_id → `ValueError`）；~~ commits `c2c3486`（初版）、`eb87591`（依兩組獨立 QA 回修：`unmatched_keys`、`bad_strategy` 污染改記 conflict、不可變複製、跨身分測試、不合法 sheet_id → `ValueError`）、`1870472`（第三組複驗回修：`unmatched_keys` 改收鍵聯集、`InvalidRow`／`HoldingKeysResult` 不變量、鍵重建驗證；規格 §7(2) 依 C §7.2 (8) 原文改寫、§7(9) 去全稱句）；（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新：`1870472` 回修））規格 `docs/vnext/NEWUI_D25_AB4R_SPEC_2026-10-27.md`（§3 pid、§3.1 候選、§5 解析、§7 限制）。
- **與其他 DEC 的關係**：不重新解釋 DEC-092／DEC-093／DEC-094／DEC-095；DEC-092 Q1 為上位約束，衝突以其為準；DEC-083（Sheet SSOT、B3 sheet_id 消毒、B5 只失效本人）沿用不放寬；寫入面仍屬 HI-5（`DEC092-STRATEGY-CLASS-WRITE-GOVERNANCE`、PLAN §5 序 10 AB-4w），本條不授權。DEC-084（Model×Effort）、DEC-003（內部自決區）呼叫。**未經客戶**。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本條由單一撰寫組依 diff、規格與實作組／總管轉述撰寫。~~品管＝**兩組獨立 QA（QA-A、QA-B）＋一組回修複驗**（總管轉述，QA 報告未逐字附）。**突變清單由實作者自列**：第一輪 35 個全紅（killed）；回修後 48 個中 47 個套用、全紅，M9 由 N11／N12 取代（實作組回報，未獨立複跑）。~~ 品管＝**兩組獨立 QA（QA-A、QA-B）＋第三組複驗**：第三組複驗第一輪回修（`eb87591`）6 項 PASS；~~**第二輪回修（`1870472`）複驗進行中、尚未完成**（總管轉述，QA 報告未逐字附）。~~ 第二輪回修（`1870472`）複驗亦 **PASS**（第三組自選 9 突變全紅）（總管轉述，QA 報告未逐字附）。殘餘 MINOR：鍵重建驗證只套 entries，`conflict_keys`／`HoldingKeysResult.keys`／`lookup` 需 `object.__new__` 刻意繞過，風險低（未修）。（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））**突變清單由實作者自列**：第一輪 35 個全紅；現行 58 個中 57 個套用、全紅，M9 由 N11／N12 取代（實作組回報，未獨立複跑）。（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新：`1870472` 回修））撰寫組沙箱無 pytest，**本組未重跑測試**；CI 未跑。承重判斷（候選 B、窄表頭判不符、衝突不擇一、`bad_strategy` 污染整鍵）**均為單組設計判斷**。本條不宣稱 PR 已通過 CI 或已合併。

### DEC-097｜D2.5 後續 UI 結論：手機版底部固定 4 按鈕主導航；NAV-1 時舊 UI 從一般使用者預設畫面／導航隱藏（不刪、不等於通過 Old UI Removal Gate）（客戶 2026-10-28）
> 2026-10-28 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-097"` 0 命中、`docs/DECISIONS.md` 最大為 DEC-096）。**本條只落盤客戶裁示並排入 NAV-1，不改任何產品 code／測試／navigation，不改 CLAUDE.md／PROJECT_RULES.md。** 來源類別＝**客戶裁示**（D 類；經總管轉交之原文要點，非逐字全文）。
- **決策者**：**客戶**（2026-10-28）。
- **內容（客戶原文要點）**：
  1. **手機版主導航採底部固定 4 按鈕**：📊 市場／🎯 標的／💼 持股／👤 我的。
  2. **NAV-1 實作時，舊 UI 從一般使用者的預設畫面／導航中隱藏**，讓畫面乾淨。附帶條件：舊 UI 程式碼**不得刪除**；**不得破壞 rollback 能力**；**不代表通過 Old UI Removal Gate**（DEC-019／DEC-020、BACKLOG `UIM-REMOVAL-GATE` 不變）；正式刪除仍須等新四頁完成實機驗收後另行處理；技術上**優先 routing／feature switch 隱藏**，不大量註解舊程式造成腐化；**legacy／rollback 入口不得出現在一般使用者主導航中**。
- **效力邊界（⛔ 不是本批授權）**：本條只落盤與排程，**不授權本批（AB-4r）任何 UI 修改**；NAV-1（PLAN §5 序 6）開工時仍依 DEC-084 重判 Model×Effort；若與既有 wireframe／規格（`docs/vnext/NEWUI_D25_PLAN_2026-10-27.md`、A 規格、`docs/vnext/d25_wireframes/`）衝突，須先查證並在 NAV-1 規劃中揭露。
- **待查證的可能衝突（INFERENCE，撰寫組單組讀法，未比對 wireframe 檔）**：PLAN §5 序 6 寫 NAV-1「以 N2（主畫面**頂端** 4 項控制列）取代 D2 六向殼」；本條第 1 點為手機版**底部**固定 4 按鈕。兩者是否衝突（例如桌機頂端／手機底部並存，或需修改 wireframe）由 NAV-1 規劃查證並揭露；若屬版面佈局異動，依 `CLAUDE.md` §-1.5 v3 §03-2 ① 草稿先行處理。
- **範圍**：UI／導覽（New UI D2.5 NAV-1）｜**日期**：2026-10-28｜**狀態**：生效（已排入 NAV-1；尚未實作）
- **來源**：客戶 2026-10-28 裁示（經總管轉交）。
- **與其他 DEC 的關係**：DEC-092 Q6（固定四主導航、D2 殼過渡保留）**同向具體化**；DEC-019／DEC-020（舊 UI Removal Gate）**不變、本條不構成通過**；DEC-082（先草稿後施工）、DEC-084（Model×Effort）、DEC-085（Long-lived UI）**呼叫**。不降低任何 Security／Investment／Data／CI／Audit Gate；衝突取較嚴者。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：要點摘自總管轉交，非客戶逐字全文；「待查證的可能衝突」為單組推論，未比對 wireframe 原檔。
### DEC-098｜NAV-1 內部設計選擇（預設翻轉為新四頁導覽；桌機 `st.sidebar`＋手機底部固定列，同一 SSOT key；`?legacy=1` 為 rollback）（AI 總管內部，2026-10-28）
> 2026-10-28 補登（ID 取下一個未用號；落盤前實測 `git grep -n "DEC-098"` 0 命中、`docs/DECISIONS.md` 最大為 DEC-097）。**本條不是客戶裁示**（DEC-097 才是客戶裁示），只記錄 NAV-1 實作時的技術／結構選擇，供 UI-M／UI-T／UI-H／UI-ME、`CROSS-VIEW-DATA-CONSISTENCY-AUDIT` 與獨立 QA 對照；不改 `CLAUDE.md`／`PROJECT_RULES.md`。
- **決策者**：AI 總管內部（依 `CLAUDE.md` v3 §03-1 內部自決；**非客戶裁示**）。
- **狀態**：~~隨 NAV-1 PR；implementation complete／waiting CI／**待客戶裁示標的頁葉選擇**，未合併。~~（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）） 已合併 PR #957（squash，main `5ff860b3`，CI 綠）；客戶已裁示 DEC-099（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））
- **內容（實作事實，來源 `docs/vnext/NEWUI_D25_NAV1_SPEC_2026-10-28.md` §1～§3、`git diff origin/main --stat`）**：
  1. **預設翻轉**：預設入口＝新四頁導覽（📊 市場／🎯 標的／💼 持股／👤 我的，標籤逐字取自 DEC-097）；舊 UI（D2 側欄雙層 radio＋舊 7 頁籤）＝legacy 模式。
  2. **桌機／手機形式**：桌機＝`st.sidebar` 內垂直 radio；手機＝底部固定列（`st.container(key="nav4_bottom")`＋CSS 注入，`@media (max-width: 768px)` 才固定到底）；CSS 失效時降級為主內容流中的一般橫排 radio（仍可點、仍寫同一格 SSOT）。**兩個元件共用同一個 SSOT key `_nav4_page`**（只經 `on_change` 回呼寫入）。
  3. **新檔／不動檔**：新增 L0 `shared/ia_nav4.py`、L5 `src/ui/views/shell_nav4.py`；**不改** `shared/ia_nav.py`（D2 事故模組）、不改 `PAGE_LABELS`、不改 `src/ui/tabs/**`。
  4. **legacy＝`?legacy=1`**（`?legacy=0` 清除）：寫入 session 旗標（黏性），**無任何可見入口**；legacy 行為不變（`tests/test_nav1_app_routing.py` 以 HEAD AST 逐節點對照守衛），且 **legacy 路徑不依賴新模組**（旗標解析為 `app.py` 內零 import 小函式；新模組僅在新模式分支 late-import；測試以 meta_path 毒化新模組驗證 `?legacy=1` 仍完整載入）。
  5. **預設模式頁內死路句分模式替換**：`page_me`／`page_market`／`page_hold` 的「切回舊版」類指路句在預設模式改為「此功能新版尚未提供，後續批次處理。」或略去；legacy 與無旗標（單元測試）輸出原句逐字不變。
  6. **late-import**：`app.py` 對 `shared.ia_nav4`／`shell_nav4` 只在函式內 import（`tests/test_boot_import_smoke.py` 與 `test_nav1_app_routing.py` 釘住），沿用 D2 boot 事故後的守衛精神。
  7. **與 PLAN §5 序 6／A 規格 N2「主畫面頂端」的差異**：以 **DEC-097＋wireframe 為準**。查證結果（FACT，讀 wireframe 原始碼，`docs/vnext/NEWUI_D25_NAV1_SPEC_2026-10-28.md` §4）：`docs/vnext/d25_wireframes/` `index.html` 圖例「桌面左側欄、手機底部列」，四頁檔皆為 `<aside class="side">`（桌機）＋`<nav class="bn">`（手機，4 等寬）——即 wireframe 本身就是桌機左側欄＋手機底部列，PLAN／A 的 N2「頂端」才是偏離者；回應 DEC-097「待查證的可能衝突」。
- **已知限制（揭露，見 spec §7，皆當作未驗）**：
  - Cloud 啟動與手機實機未於沙箱實測（底部固定、safe-area、窄螢幕單行、iOS／Android 均未驗）；
  - CSS 依賴 `st-key-<key>` class、`:has()` 等 Streamlit 非公開保證（floor 1.56 是否具備未驗，沙箱僅 1.59.2）；
  - 768px（底部列斷點）與側欄抽屜（約 640px，INFERENCE）兩套導覽並存於中間寬度；
  - Google 登入轉跳回來為新 session、網址不帶 `legacy` ⇒ 掉回新（預設）模式；
  - **預設畫面暫時取不到、僅 `?legacy=1` 可達的舊功能**：🚦 今天、📖 憑什麼的資料體檢、AI 問答、🔧 工具箱（資料診斷）、📁 組合管理 CRUD（新增／刪除）、🏦 ETF、🌍 總經深度（含板塊資金潮汐、產業熱力圖）。這是暫時缺口，**不是「已併入」**；**不代表通過 Old UI Removal Gate**（DEC-019／DEC-020、`UIM-REMOVAL-GATE` 不變）。
- ~~**偏離 wireframe（待客戶裁示，非本條可定案）**~~（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）） **已由客戶裁示方案 A（DEC-099）**；原述：🎯 標的頁多一條「🔍 找標的／🔬 查一檔」橫排 radio（wireframe 標的頁為單一頁）——過渡項，UI-T 合併為單頁時移除；若客戶視為「版面佈局異動」須於合併前裁示（`NAV1-TARGET-LEAF-SELECTOR`）。
- **與其他 DEC 的關係**：DEC-097（客戶裁示）**具體實作**；DEC-092 Q6 同向；DEC-019／DEC-020 不變、本條不構成通過；DEC-082（草稿先行）、DEC-084（Model×Effort）、DEC-003（內部自決區）呼叫；不降低任何 Gate。**未經客戶**。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：QA-A（對抗）＋QA-B（語意）＋第三組回修複驗；~~**第三組複驗進行中，不得寫為已通過**。~~（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）） 第三組兩輪回修複驗皆 PASS（無 BLOCKER／MAJOR），殘餘 MINOR 已補行為測試或登記 BACKLOG（總管轉述，PR #957 已合併）。突變依實作組自報 **40 項（M1–M26＋N1–N14）全數轉紅**，清單由實作者自列（M23／M25 首跑 GREEN、已補強守衛後轉紅），未獨立複跑；spec §3～§7 判斷為實作組單組結論；~~CI 未跑~~（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）） CI 已跑：#957 Fast checks 與 Slow tests 皆 success（head `3f3c0b5d`）；撰寫組（本 docs 同步）未重跑測試。


### DEC-099｜NAV-1 🎯 標的頁「🔍 找標的／🔬 查一檔」過渡切換：客戶裁示方案 A（保留，僅作 NAV-1 → UI-T 之間的過渡控制）（客戶 2026-10-28）

> 2026-10-28 補登（ID 取下一個未用號；落盤前 `grep -o 'DEC-0[0-9]*' docs/DECISIONS.md` 最大為 DEC-098、DEC-099 0 命中）。要點經總管轉交，**非客戶逐字全文**。

- **決策者**：**客戶**（2026-10-28；經總管轉交之要點）。
- **日期／效力日期**：2026-10-28 起生效。｜**狀態**：生效。
- **內容（客戶選方案 A，五點明確落盤）**：
  1. 該切換**不是最終 wireframe 設計**；
  2. **不視為新增正式 IA**；
  3. **UI-T 實作時，「找標的＋查一檔」必須整合回單一 🎯 標的頁，並移除此過渡切換**（連同 `NAV4_TARGET_LEAF_KEY`、`render_target_leaf_selector`）；
  4. **不得因本次過渡方案改變既有功能語意或新增投資規則**；
  5. **PR #957 其他範圍不變**。
- **效力邊界（⛔ 只裁示這一項偏離）**：本條**只**針對 🎯 標的頁葉選擇切換這一項偏離 wireframe；**不涵蓋**：`NAV1-WAYFINDING-I1`（I-1 頁名）、`NAV1-PAGE-TODAY-LEGACY-WORDING`（legacy 殘留字樣）、`NAV1-DEFAULT-MISSING-CAPABILITIES`（舊功能預設不可達）、`NAV1-CLOUD-MOBILE-VERIFY`（客戶實機點驗仍為驗收必要條件）等其他項；舊 UI Removal Gate（DEC-019／DEC-020、`UIM-REMOVAL-GATE`）不變、本條不構成通過。
- **與 DEC-097／DEC-098 的關係**：DEC-097（客戶裁示：手機底部 4 按鈕、舊 UI 預設隱藏）**不變**；DEC-098 為 **AI 總管內部設計選擇，不是客戶裁示**——其中「標的頁葉選擇＝過渡項、待客戶裁示」一點，由本條（客戶裁示）**回答**；DEC-098 其餘內容不因本條升格為客戶裁示。DEC-082（草稿先行）：客戶已就此偏離裁示，毋須再出草稿。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：撰寫組（docs-only）未重跑測試；本條只落盤裁示，不改任何程式碼。

### DEC-100｜Cross-View 資料一致性稽核的處置分類＋本批 4 項半安全小修（AI 總管內部，2026-10-28）

> 2026-10-28 補登（ID 取下一個未用號；落盤前 `grep -o 'DEC-[0-9]*' docs/*.md docs/vnext/*.md` 最大為 DEC-099、DEC-100 0 命中）。**本條不是客戶裁示**，只記錄 `CROSS-VIEW-DATA-CONSISTENCY-AUDIT` 稽核結果的處置分類與 AI 總管依 `CLAUDE.md` v3 §03-1 內部自決的安全小修；報告 `docs/vnext/NEWUI_D25_XVIEW_AUDIT_2026-10-28.md`。

- **決策者**：AI 總管內部（依 `CLAUDE.md` v3 §03-1；**非客戶裁示**）。
- **狀態**：~~隨 xview PR；implementation complete／waiting CI，**未合併**。~~ **已合併 PR #959（squash，main `c6ad4567`，CI 綠：Fast checks／Slow tests 皆 success，head `7a233144`）**（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。
- **處置分類**（報告 §4.1～§4.4）：38 項不一致分為 (1) 本批安全小修 S1～S5；(2) 客戶 Gate（業務語意／版面）→ BACKLOG `XV-H3`、`XV-H1-EXT`、`XV-ASOF`；(3) 內部技術 Gate（§8 完整流程＋獨立 QA）→ BACKLOG `XV-X1`、`XV-C02`、`XV-C01`、`XV-C03`、`XV-C04`、`XV-M1`、`XV-M3`、`XV-M4`、`XV-M5`、`XV-C13`、`XV-C05`、`XV-H2-EXT`；(4) 登記（§-1，待任務碰到時處理）。
- **本批安全小修（不新增 provider／API／schema，不改投資語意、公式或版面）**：
  - **(a) S1 ⑦／LINE AI prompt**（`188c20e7`＋QA 回修 `183dbdc3`）：`build_summary_prompt` 有效判斷檔數 `total` 須為**有限值且 ≥1** 才放「續抱、定期定額即可」句（缺／非數／NaN／inf／0／0.5 一律不放）；total>0 正常路徑逐字不變；LINE `_maybe_ai_summary` 共用同一支 prompt 同步受益。部分失敗／燈全⚪／無現價**不在範圍**（Z51／Z52 既有測試釘住，轉客戶 Gate `XV-H1-EXT`）。
    - 📌 **2026-10-28 補註（append-only；原文不改）**：部分語意已由 DEC-101(2) 取代（2026-10-28 客戶）—— 部分失敗／燈全⚪／無現價時不得以「續抱」代替缺資料結論；Z51／Z52 舊語意與相關測試同步修正（有意識的更新，不是漏刪，決策者 客戶；DEC-101）。
  - **(b) S2 側欄「🔄 強制刷新數據」help 文字據實**（`96880543`＋QA 回修 `183dbdc3`）：只改說明文字，列出不在清除範圍的模組自有暫存（總經戰情快照、個股股價與籌碼、台灣與美國總經含 VIX／匯率、多檔批次結果、proxy 原始回應、失敗冷卻等，結尾表明非完整清單）；按鈕標籤、key、行為、版面不變。該按鈕兩模式共用 ⇒ **legacy 模式亦可見新說明**（舊 UI digest 已更新並依 DEC-019 揭露）。行為統一轉 `XV-H2-EXT`。
  - **(c) S3 🔬 葉2 個股抓價失敗顯示整列錯誤**（`7dbfaf4b`）：`page_inspect._batch_row` 對個股傳 `failed=`，價格抓取失敗沿用既有 `BatchRow.error` 整列錯誤態；查無資料仍「—」。⚠️ **取捨（已揭露）**：同列的財報分數一併被錯誤態蓋掉；財報腿失敗仍「—」（不在範圍）。屬「修正錯誤」非「改變設計」（`CLAUDE.md` §-1.5.A-8）。
  - **(d) S4 `sector_heatmap_render` 去後綴順序**（`8bc93e8e`）：改為先 `.TWO` 再 `.TW`（只對調順序、不換 helper、不改大小寫）；現行子項無 `.TWO`，畫面零變化。**半項**：同型兩處在 `etf_smart_analysis`（僅舊 UI `etf_tab_smart` 使用）依 DEC-019 舊 UI 凍結**停手未修**，登記。
  - **(e) S5 本益比對照表只快取成功＋FailCooldown**（`99e10bc6`＋QA 回修 `183dbdc3`）：TWSE／TPEX 兩支 fetcher 快取層移到內層、失敗 raise 不入快取；公開函式為外層 wrapper 照舊回空表（簽章／回傳形狀／3 個 caller 不變），接 `shared.fail_cooldown`（上市／上櫃各一份）。⚠️ **INFERENCE（已揭露）**：冷卻表為模組層、跨 session 共用 ⇒ 冷卻期間**所有使用者**都拿空表；補「晚到失敗不得覆蓋成功」測試。
  - 守衛同步 `3c1a7550`：舊 UI 零改動 digest（舊值刪除線保留＋DEC-019 揭露）、新增 `tests/test_xview_revert_chain.py`。
- **與其他 DEC 的關係**：DEC-019／DEC-020（舊 UI 凍結／Removal Gate）**不變**——(d) 停手即依此；DEC-003（內部自決區）、DEC-084（Model×Effort）呼叫；客戶 Gate 項不由本條定案。不降低任何 Gate。**未經客戶**。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：三組獨立稽核（A／B／C）＋一組獨立複驗（V）＋一組修正 QA（抓到 1 MAJOR＋2 MINOR，皆已於 `183dbdc3` 回修）；**回修後未再經第二組複驗**（總管轉述）。突變測試由實作者與 QA **各自自列**，未獨立複跑。**限制**：沙箱無部署端網路、Streamlit Cloud 未驗（快取／冷卻行為皆讀碼與單元測試推得）；報告內全稱句（「只有兩條價格路徑」「38 項即全部」等）為單組或 grep 結論，不得當前提（報告 §6）。撰寫組（本 docs 同步）未重跑測試。

### DEC-101｜Cross-View 稽核客戶 Gate 裁示：XV-H3＝A（外幣不得直接與 TWD 加總、先排除並列出）／XV-H1-EXT＝A（missing ≠ HOLD，不得以「續抱」代替缺資料結論）／XV-ASOF＝A（價格旁顯示資料時間＋來源，先出線框）＋基金範圍聲明＋其餘內部技術議題授權邊界（客戶 2026-10-28）

> 2026-10-28 補登（ID 取下一個未用號；落盤前 `grep -o 'DEC-[0-9]*' docs/*.md docs/vnext/*.md` 最大為 DEC-100、DEC-101 0 命中）。要點經總管轉交，**非客戶逐字全文**。

- **決策者**：**客戶**（2026-10-28；經總管轉交之要點）。
- **日期／效力日期**：2026-10-28 起生效。｜**狀態**：生效；(1)(2) 實作中、(3) 線框草稿待客戶確認（`docs/vnext/NEWUI_D25_XVIEW_ASOF_WIREFRAME_2026-10-28.md`）。
- **背景**：DEC-100 將稽核報告 `docs/vnext/NEWUI_D25_XVIEW_AUDIT_2026-10-28.md` 的三項客戶 Gate（G1／G2／G3）登記為 BACKLOG `XV-H3`／`XV-H1-EXT`／`XV-ASOF`，附總管推薦；客戶三項皆選 A。
- **內容**：
  1. **XV-H3 選 A（外幣資產）**：
     - 未定義**匯率來源、匯率時點與成本幣別**前，外幣資產**不得直接與 TWD 加總**；
     - 外幣資產**先排除於 TWD 總市值**；畫面須**明確列出哪些標的未納入及原因**；
     - 排除後**不得把剩餘資產包裝成完整 80/20 或完整配置比例**；完整 denominator 不存在時顯示「**⬜ 部分外幣資產未納入，總市值／配置比例無法完整判定**」；
     - 日後外幣換算**另開 Gate**，正式定義 asset currency、cost currency、FX source、FX as_of 與 canonical TWD value（BACKLOG `FX-CANONICAL-GATE`）。
  2. **XV-H1-EXT 選 A（缺資料不得說續抱）**：
     - 部分持股抓不到、全部燈號無法判定、持股缺現價時，**不得以「續抱」作為缺資料的替代結論**；**missing ≠ HOLD、unavailable ≠ safe**；
     - 有充分資料的個別標的**保留既有可證明結論**；缺資料標的顯示「**⬜ 資料不足／無法判定**」；
     - 組合層只要關鍵資料不足，**不得產生「全部續抱」等 blanket conclusion**；
     - **同步修正 Z51／Z52 舊語意與相關測試**：本條**取代**其「缺值／部分失敗時 prompt 與修前逐字相同、仍帶『續抱』指示」那一部分語意（批 Z51 #838、批 Z52 #839 的測試釘住者，例：`tests/test_batch_z52.py::test_prompt_normal_and_missing_identical_to_pre`、`tests/test_batch_z51.py::test_prompt_normal_identical_and_keeps_instruction`、`tests/test_dividend_station_service.py::test_summary_prompt_contains_facts_and_hold_instruction`，清單取自稽核報告 §4.2 G2，為 grep 結論）；原 DEC（DEC-031、DEC-100(a)）**加註指向本條，不刪原文**。
  3. **XV-ASOF 選 A（價格資料時間＋來源）**：
     - 新四頁價格旁顯示**簡潔的「資料時間＋來源」**；stale／fallback **必須明確標示**；**不得只用顏色**表達 stale；
     - **先依既有治理出線框草稿，確認後再實作，不自行擴張版面**（DEC-082；`CLAUDE.md` §-1.5.D v3 §03-2 ①）；
     - Level 1 簡潔，完整 methodology 可留在「查看依據」。
  4. **範圍聲明（基金）**：股票 repo 的 Cross-View Audit **不代表基金資料一致性已驗收**（本 repo 無基金資料；報告 §1.2）；姊妹 repo `my-Fund-dashboard` **須另做**同類 Cross-View Data Consistency Audit（特別查單一基金 NAV 與組合頁同基金 NAV／日期／幣別／級別／來源一致性；BACKLOG `FUND-REPO-XVIEW-AUDIT`）；**不得把股票 Audit 標記為基金問題已結案**。
  5. **其餘內部技術議題授權邊界**：
     - 純技術一致性（cache key、大小寫／alias）且**不改客戶語意、不引入新來源／公式／schema** 的安全修正，可依自治規則處理（DEC-003；`CLAUDE.md` v3 §03-1）；
     - 涉及 **canonical identity、資料契約 schema、新 provider／API、公式、投資語意或客戶可見的新計算口徑**，**必須另停 Gate**；
     - **策略分類 key 大小寫須在接摘要前完成並驗證**（`XV-C05`，`AB4R-WIRE-BUILDER` 前），**不得造成同一標的兩個 identity**。
- **效力邊界**：本條**不**決定過期價是否計入市值／損益／停利（報告 G4；未裁示）；**不**核准外幣換算；**不**核准 XV-ASOF 的實作（線框確認前 0 UI code）；**不**通過舊 UI Removal Gate（DEC-019／DEC-020）；不降低任何 Gate。
- **與其他 DEC 的關係**：DEC-100（AI 總管內部處置分類）之三項客戶 Gate 由本條**回答**；DEC-100 其餘內容不因本條升格為客戶裁示。DEC-031（數值異常不顯示、不續算）**原則不變**，僅其實作批 Z51／Z52 中「缺值仍帶續抱」的測試語意由本條第 2 點取代。DEC-082（草稿先行）、DEC-003（內部自決區）、DEC-084（Model×Effort）呼叫。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：撰寫組（docs-only）未重跑測試；本條只落盤裁示，不改任何程式碼；Z51／Z52 受影響測試清單為報告 grep 結論，實作組須自行全面盤點。

## 2. 產品／UI

### DEC-017｜IA v2 五頁線框為台股前端實作依據
- **內容**：7 頂層／14 葉 → 5 頂層／11 葉；版面架構、決策動線與四態模型確認。
- **範圍**：UI｜**日期**：2026-09-05｜**決策者**：客戶｜**狀態**：生效（後續逐頁修訂）
- **來源**：B `67affe8d`（直推）「客戶 2026-09-05 拍板：版面架構、決策動線與四態模型全數確認，13 項裁決與 v2 線框」；檔案 `docs/wireframes/stock_ia_v1.html`。

### DEC-018｜雙軌入口：舊 7 頁籤維持第一排、新版五頁由側邊欄進入（方案 A）
- **範圍**：UI｜**日期**：2026-09-08｜**決策者**：客戶｜**狀態**：生效至正式入口切換（DEC-020）；撰寫組實測 `app.py@8bb52427` 仍有 `_IA_NAV_OFF = '不使用（用下方原功能）'`（單組）
- **來源**：B #671 PR head commit `b5bdb36e`（main 上；merge commit `eb1c67d8`）「總管出線框草稿，**客戶明確回覆「A 照做」**，本 commit 即該設計。」

### DEC-019｜New UI 是唯一開發主線；舊 UI 凍結（以 main 實際 call path 判定）
- **內容**：新 UI＝`src/ui/views/**`、`src/ui_v2/**`＋經 main 實際 import／call path 證實為新 UI 必須使用的共用層；舊 UI＝`app.py` 預設 7 頁籤所用 `src/ui/tabs/**`、`src/ui/etf/**`、`src/ui/pages/**`、`src/ui/render/**` 中經 call path 證實只有舊 UI 使用的部分；禁止修改舊 UI（含一般 bug、nan／inf、文案、顏色、版面、重構、新功能）；共用層只在新 UI 確實依賴時修根因；舊 UI 壓測 stash 不恢復、不提交、不推送。
- **範圍**：產品／UI｜**日期**：2026-10-13｜**決策者**：客戶｜**狀態**：生效
- **來源**：C 第四則〈UI 邊界更正 A〉`H:1346`「- src/ui/views/**」、`H:1356`「1. 從現在開始禁止修改舊 UI。」；第三則 `H:1211`。D 客戶訊息 2026-10-15T13:40Z（本 session；本檔首次入庫）§20「New UI：/ 唯一開發主線」。B 旁證：#860 `ef7cf41c`、#862 `fa26914b` 皆未改舊 UI。
- **取代鏈**：**取代** 2026-10-13〈Q-z30〉「舊 UI 只允許 4 類修正」（C，HO `d836a2f2`；取代判讀見 `H:1336`，編修組單組）。第三則「ui_v2/** 唯一、ui/views/** 屬舊 UI」的路徑寫法**被第四則更正**（`H:1334`）。

### DEC-020｜正式切換路線與舊 UI 刪除前置；切換前必做清單（Q-z31＝B）
- **內容**：新 UI 問題收斂 → New UI Readiness Audit → 功能／資料／計算對等驗收 → regression／CI → 正式入口切換 → production smoke → 舊 UI 依賴稽核 → 確認無依賴後刪除舊 UI → 整理 → 最終 regression；目前不提前刪舊 UI；database／歷史資料／raw／traceability 不得因舊 UI 不用就刪；切換前必做：持股／組合管理新增刪除、觀察清單新增刪除、今天頁交易日格、其他經 audit 證明不可缺者；不得追求 100% parity 無限延後。
- **範圍**：產品｜**日期**：2026-10-13（第三則）；2026-10-14（Q-z31）｜**決策者**：客戶｜**狀態**：生效（路線未完成）
- **來源**：C `H:1287`「舊 UI 的最終目的不是繼續維護，而是在新 UI 正式接管後安全刪除。」；`H:1300`「database／歷史資料／raw data／traceability data 不得因為舊 UI 不再使用就直接刪除。」；`H:1396`「不得因追求舊 UI 100% parity 無限延後切換。」。D 客戶訊息 2026-10-15T13:40Z（本 session；本檔首次入庫）§20「舊 UI 實體刪除：/ 仍屬重大 irreversible operation。」
- **取代鏈**：2026-10-01 藍圖「舊 UI 退場三關（並行觀察 ≥2 週、先隱藏）」（C `H:128`）是否被本條取代**未明示** → `CV1-DR-03`。

### DEC-021｜寫入功能做進新 UI（Q-z32＝A、題 1＝A 線框）；Q-z33＝A 測試依賴
- **內容**：新增／刪除功能正式做進新 UI；「💼 我的持股 › 組合設定」預覽表下方放編輯區預設收合；同處換一本／建新 Sheet；「🔍 找標的」可加入觀察清單；逐筆操作、寫入前預覽、刪除二次確認、同本重複加入阻擋；舊「📁 組合管理」只作短期過渡。Q-z33：補 markdown-it-py 讓被 skip 的測試實際執行（一次性指示）。
- **範圍**：UI／產品｜**日期**：2026-10-14｜**決策者**：客戶｜**狀態**：生效；寫入功能**尚未實作**（Z6x-a1～e，見 BACKLOG `BL-MIGRATE-1` 📌 註）
- **來源**：C `H:1397-1398`「Q-z32＝A / 新增／刪除功能正式做進新 UI。」；`H:1434-1436`「題 1＝A。/ 同意附件／草稿方案，包括：/ - 「💼 我的持股 › 組合設定」預覽表下方放編輯區，預設收合。」；`H:1402`「Q-z33＝A」。

### DEC-022｜全站不產生直接買賣建議（合規母法）＋再平衡硬禁令
- **內容**：禁用語：建議買進、立即出清、應該加碼、推薦、必漲、目標價；再平衡只做偏離提示／客觀對照／情境試算；禁一鍵再平衡按鈕、禁預設最佳配置推薦。
- **範圍**：產品（合規）｜**日期**：S1-6 收錄；2026-09-29 規矩升級重申｜**決策者**：客戶｜**狀態**：~~**形式上生效；與客戶 2026-10-15 MSG 1 §7 Action Layer 長期目標存在未調和張力** → `CV1-DR-01`（最高優先，本檔不擇一）~~ **部分取代 → DEC-054（全面禁止方向性 Action 部分）**（2026-10-16 更新；理由：客戶 2026-10-16T16:26Z 裁示 `CV1-DR-01`，見 DEC-054）
- **來源**：A `docs/v2/spec/S1-6_COMPLIANCE_COPY_GUIDE.md@f0a6c474:23-25`「### 母法（客戶原文，本文一切判準的上位）/ > 全站不產生任何直接買賣建議。」。C `H:4668`「① ⛔ 不產生買賣建議（只能偏離提示／客觀對照／情境試算）」。
- 📌 **2026-10-16 指標（append-only；本條標題、內容、來源一字未改，只改上方狀態欄）**：「全面禁止方向性 Action」部分由 DEC-054 取代；本條其餘護欄在 DEC-054 之後**逐項**的效力與承接者，見 DEC-054「DEC-022 護欄承接表」。本條保留作歷史 Decision。

### DEC-023｜總經 16 盞燈：台幣與加權指數只畫走勢、不算一盞燈
- **內容**：不進「x/16 有值」分母、不進五桶 worst-of、不進訊號可信度卡。
- **範圍**：公式／UI｜**日期**：2026-08-27｜**決策者**：客戶｜**狀態**：生效
- **來源**：B `36f9d234`（直推）「客戶 2026-08-27 裁示：台幣與加權指數要畫走勢，但不進「x/16 有值」分母、」；`22921ed6`「頁5 把 16 盞燈算成 18 盞 —— 修回客戶 2026-08-27 的裁示」。

### DEC-024｜移除策略回測功能
- **範圍**：產品／方法論｜**日期**：2026-06-24｜**決策者**：user｜**狀態**：生效（理由見 `CLAUDE.md` §2.3：只有現存公司快照＋短歷史，回測必踩 lookahead 與存活者偏誤）
- **來源**：B `bdfe1cbb`（#284）「user 反饋:回測功能不再需要(S-WFT-1 walk-forward train phase 討論延伸)。」

### DEC-025｜改採前進式驗證（Forward-test）：凍結選股、事後對帳；每月自動凍結到 git 追蹤 parquet
- **範圍**：產品／方法論｜**日期**：2026-07-22｜**決策者**：user｜**狀態**：生效；已凍結 cohort 不改寫（DEC-050）
- **來源**：B `ba25538f`「user 選 (a) Google Sheet + 凍結時連因子組一起記」；`2c08975c`「落地 git 可追蹤檔,數據自己累積、可稽核。user 選「完整選股網版」。」。A `CLAUDE.md@f0a6c474` §2.3。

### DEC-054｜解除「全站不產生任何直接買賣建議」的全面禁止；允許有證據、受風險護欄約束的方向性 Action（`CV1-DR-01` 裁示）
> 2026-10-16 追加（第 8 節「收到當輪追加」）。依主題放在本節（產品／合規）末，ID 照序取下一個未用號（撰寫組對本次修改前的 `HEAD:docs/DECISIONS.md` 跑 `grep -o "DEC-[0-9]*" | sort -u` 實測最大為 DEC-053；全 repo 查無 `DEC-054`）。
- **內容**（逐點對應客戶原文第 1～7 點，用語照原文，不增不減）：
  1. 系統**允許**輸出方向性投資行動：建立第一筆部位／加碼／續抱／暫停加碼／減碼／全部退出／無法判定。
  2. 方向性行動**不是無條件推薦**。每個 Action 必須由既有、可追溯資料與正式決策規則支持，並能說明主要理由、資料 as-of／freshness 與關鍵風險。
  3. 資料不足時**不得硬給方向**：missing ≠ 0；unavailable ≠ neutral；not evaluated ≠ safe；Required Core 不足時，相關決策必須「無法判定」；不得由 AI 補造客觀資料。
  4. Risk Cap、Position Sizing、Thesis、Core Decision／Context Overlay 等既有風險護欄繼續有效；方向性 Action **不得繞過** Risk Cap 或其他正式風險限制。
  5. **禁止無證據的強斷言**，例如：必漲／必跌、保證獲利、無風險、AI 自行生成目標價或客觀市場資料。
  6. 「全部退出」等強 Action 可以存在，但必須由明確條件／Thesis break／風險規則或其他正式 Decision 支持，**不得只靠生成式 AI 主觀判斷**。
  7. 以新 DEC 記錄、**不竄改 DEC-022 歷史**：保留 DEC-022 作為歷史 Decision；本條**只取代其「全面禁止方向性 Action」部分**；DEC-022 中仍合理的合規護欄，如禁止保證獲利、假精確或無證據強斷言，若沒有其他上位規則承接，應明確保留（見下方承接表）。
- **範圍**：產品（合規）／Action 語意｜**日期**：2026-10-16｜**決策者**：客戶｜**狀態**：生效（治理語意）
- **本條不是實作授權**：客戶同訊息「本批只做治理語意對齊，不修改產品 code、UI、投資公式、門檻、資料來源或 Action Layer 實作。」、「不要自行開始 CV1-DR-02 或產品功能 Batch。」。⚠️ 撰寫組併讀（非本訊息明示）：Action Layer 日後施工仍受 DEC-009 Decision Gate、DEC-053（正式加減碼比例程序）、DEC-003（UI 草稿先行）、DEC-015／DEC-002 拘束，本條未改變上述任何一條。
- **來源**：D 客戶訊息 2026-10-16T16:26Z（本 session；本檔首次入庫）「採用 Action Layer 的較新方向，解除「全站不得產生任何直接買賣建議」作為全面禁止規則。」；「方向性行動不是無條件推薦。」；「新 Decision 取代其「全面禁止方向性 Action」部分；」。佐證：七種 Action 名稱與客戶 2026-10-15T13:40Z MSG 1 §7 Action Layer 長期目標一致（`docs/BACKLOG.md` `CV1-DR-01` 列原文）。
  - ⚠️ 用字對映（撰寫組）：客戶本訊息寫「全站**不得**產生任何直接買賣建議」，DEC-022 所載母法原文為「全站不產生任何直接買賣建議」；兩者指同一條（客戶本訊息明指 `CV1-DR-01` 與 DEC-022）。
- **取代鏈**：**部分取代 DEC-022**（僅「全面禁止方向性 Action」部分；客戶明示）。
- **DEC-022 護欄承接表**（第 1～3 列為撰寫組單組判讀；第 4～7 列為「總管判讀（依 MSG 11 第 1、7 點）」；⚠️ 全表待第二組 evidence audit；再平衡射程待客戶確認 → `docs/BACKLOG.md` `CV1-FU-02`）：

  | # | DEC-022 所載內容 | DEC-054 之後 | 承接者 |
  |---|---|---|---|
  | 1 | 母法「全站不產生任何直接買賣建議」作為**全面禁止規則**（含 `H:4668` 2026-09-29「① ⛔ 不產生買賣建議」之同義重申） | **被取代** | DEC-054 第 1、2 點 |
  | 2 | 禁用語「必漲」 | 保留 | DEC-054 第 5 點（必漲／必跌） |
  | 3 | 禁用語「目標價」 | 保留 | AI 自行生成目標價：DEC-054 第 5 點＋DEC-027（AI 不得創造客觀資料）；**非 AI 生成**的「目標價」用語，DEC-054 未提及 → **DEC-022 保留** |
  | 4 | 禁用語「建議買進」「立即出清」「應該加碼」「推薦」 | 「總管判讀（依 MSG 11 第 1、7 點）」：此詞表即「全面禁止方向性 Action」的實作（第 1 點明文允許加碼／減碼／全部退出等），其「全面禁止」部分 → **被取代**。此類措辭現在**只有**符合 DEC-054 第 2、3、5、6 點時才允許：由可追溯資料＋正式決策規則支持，並說明主要理由、資料 as-of／freshness 與關鍵風險；資料不足 →「無法判定」；不得含無證據強斷言；強 Action 只能經正式條件 | DEC-054 第 2、3、5、6 點 |
  | 5 | 再平衡「只做偏離提示／客觀對照／情境試算」 | 「總管判讀（依 MSG 11 第 1、7 點）」：再平衡是投組層級功能，不在 DEC-054 列舉的七種 Action 內 → **DEC-022 暫時保留**；DEC-054 是否延伸至再平衡 Action 未裁示 | DEC-022（暫時）；`CV1-FU-02` |
  | 6 | 禁一鍵再平衡按鈕 | 「總管判讀（依 MSG 11 第 1、7 點）」：同第 5 列理由（再平衡不在七種 Action 內）→ **DEC-022 暫時保留** | DEC-022（暫時）；`CV1-FU-02` |
  | 7 | 禁預設最佳配置推薦 | 「總管判讀（依 MSG 11 第 1、7 點）」：同第 5 列理由 → **DEC-022 暫時保留** | DEC-022（暫時）；`CV1-FU-02`；DEC-054 第 4 點（Position Sizing 等護欄續有效）、DEC-053 同向 |

- **客戶點名的護欄**（客戶第 7 點舉例「禁止保證獲利、假精確或無證據強斷言」）：

  | 護欄 | 是否在 DEC-022 所載文字內 | 承接者 |
  |---|---|---|
  | 保證獲利、無風險、必跌 | 否（DEC-022 所載禁用語僅六詞） | DEC-054 第 5 點 |
  | 無證據強斷言 | 否 | DEC-054 第 5 點（第 2 點的證據要求同向） |
  | 假精確（no fake precision） | 否 | DEC-040 |
  | AI 生成目標價／客觀資料 | 「目標價」是（不限 AI） | DEC-054 第 5 點、DEC-027 |
  | missing ≠ 0 | 否 | DEC-026、DEC-040、DEC-054 第 3 點 |
  | unavailable ≠ neutral；not evaluated ≠ safe | 否 | DEC-040、DEC-054 第 3 點 |
  | Required Core 不足 → 無法判定 | 否 | DEC-048、DEC-054 第 3 點 |
  | 不得繞過 Risk Cap | 否 | Risk Cap 相關 DEC：DEC-041～DEC-044、DEC-046、DEC-048、DEC-049、DEC-051、DEC-052（撰寫組逐條核對標題／內容；DEC-045 推播、DEC-047 季財報、DEC-050 revenue_yoy 非 Risk Cap，不列）；DEC-054 第 4 點 |
  | 正式加減碼比例須經驗證程序 | 否 | DEC-053 |

- ⚠️ **未查證／缺口（不得當成已成立前提）**：第 4、6 點所稱「既有」的 Thesis、Core Decision／Context Overlay，在本 repo **查無正式 DEC 或規格**（撰寫組 `git grep -i -E 'thesis|context overlay|core decision'` 實測只命中 `CV1-RC-01` 候選方向與 `AUD-L9`「持股帳本無…thesis」）；Position Sizing 的已落盤規則只有 DEC-040（缺 Cap → 建議持股「無法判定」）、DEC-044、DEC-048、DEC-053 → `docs/BACKLOG.md` `CV1-FU-04`。另：七種 Action 與現行 `suggest_action` 語彙（DEC-045）的關係 → `CV1-FU-03`。
- **實作紀錄指標**（2026-10-16 追加，append-only；本條以上一字未改）：`CV1-FU-01` 的實作裁示見 **DEC-055**（客戶訊息 2026-10-16T22:15Z）；DEC-055 實作本條、不修改本條。改版後新增缺口 → `CV1-FU-05`、`CV1-FU-06`。

### DEC-055｜S1-6 合規指南與 `AI_QA_DISCLOSURE` 對齊 DEC-054（`CV1-FU-01` 實作裁示）
> 2026-10-16 追加（第 8 節「收到當輪追加」）。ID 照序取下一個未用號（撰寫組 `git grep -oh "DEC-0[0-9]*" | sort -u` 實測最大為 DEC-054）。
- **內容**（逐點對應客戶原文第 1～9 點，引號內為原文）：
  1. 「"docs/v2/spec/S1-6_COMPLIANCE_COPY_GUIDE.md" 不再以「全站不產生任何直接買賣建議」作為現行全面母法。」
  2. 「文件必須忠實反映 DEC-054」：允許七種方向性 Action（建立第一筆部位／加碼／續抱／暫停加碼／減碼／全部退出／無法判定）。
  3. 「但必須保留 DEC-054 的條件」：「Action 必須由可追溯資料＋正式決策規則支持」；「顯示主要理由、as-of / freshness、關鍵風險」；「資料不足 → 無法判定」；「不得繞過 Risk Cap 等正式護欄」；「禁止必漲／必跌、保證獲利、無風險、無證據強斷言」；「AI 不得自行生成客觀資料或無正式依據的目標價」；「強 Action 必須有正式條件支持」。
  4. `AI_QA_DISCLOSURE`：「只修正到與 DEC-054 一致；」「不要趁機設計新的免責聲明體系；」「保留一般「非投資建議」類合理揭露，只移除與正式 Action 自相矛盾的語意。」
  5. 「不把 DEC-054 擴張到「投資組合再平衡」。」「FU-02 保持待裁示；DEC-022 的再平衡三項限制目前繼續有效。」
  6. 「不處理 FU-03」（七種 Action 是否封閉清單、`suggest_action` 舊標籤 mapping 留到 Action Layer 正式設計批）。
  7. 「不處理 FU-04」：「不要現在自行創作 Thesis / Core Decision / Context Overlay 正式規格；保留為待後續設計的缺口。」
  8. 「全 repo 搜尋所有仍引用舊「全面禁止方向性 Action」的 active 規格／強制文案。」「若只是同一 DEC-054 造成的文件漂移，可在本批做 Minimum Necessary Change；」「歷史紀錄不得改寫。」
  9. 「本批只允許文件／治理語意同步。」禁止：「修改產品 code」「修改 UI」「修改公式／門檻／資料來源」「實作 Action Layer」「擴張再平衡」「自行補 Thesis / Core Decision 規格」「開始 CV1-DR-02～09」（撰寫組判讀：`AI_QA_DISCLOSURE` 依第 4 點為本條唯一允許的 code 文字修改）。
- **範圍**：產品（合規）文件／強制文案｜**日期**：2026-10-16｜**決策者**：客戶｜**狀態**：生效（~~隨本批 PR 合併~~ 已隨 #866 `2647a0fd` 合併，main CI run 38980399324 success；2026-10-17 收尾同步補登）
- **來源**：D 客戶訊息 2026-10-16T22:15Z（本 session；本檔首次入庫）「先處理 CV1-FU-01，不開始 CV1-DR-02，也不要開始產品 Action Layer。」；「本批目標：讓既有合規文件與 DEC-054 對齊，消除「治理允許方向性 Action，但 S1-6 文件仍全面禁止」的規格漂移。」
- **與其他 DEC 的關係**：**實作 DEC-054，不修改 DEC-054**；不取代任何 DEC。DEC-022 再平衡三項限制依本條第 5 點繼續有效（`CV1-FU-02`）。BACKLOG 登記：DR-2026-10-16-7。

### DEC-056｜新 UI 產品方向＝「投資決策 OS／Investment Inbox」（只核准方向，不是實作授權）
> 2026-10-17 追加（第 8 節「收到當輪追加」）。ID 照序取下一個未用號（撰寫組 `git grep -oh "DEC-0[0-9]*" | sort -u` 實測最大為 DEC-055）。BACKLOG 登記：DR-2026-10-17-1；方向項目逐項見 `docs/BACKLOG.md` **第 5 節（`VN-*`）**。
- **內容**（逐點對應客戶原文，引號內為原文）：
  1. 「客戶已正式同意後續新 UI 朝「投資決策 OS / Investment Inbox」方向發展。」長期方向清單（客戶原文第 2 點，逐項）全數登記於 `docs/BACKLOG.md` 第 5 節，本條不重抄。
  2. 「這次客戶同意的是「產品方向」，不是一次授權全部實作。」
  3. **仍須未來獨立 Decision Gate、不得因本次登記視為已核准**（客戶原文第 4 點，逐字）：「投資公式與 threshold」「Action transition rules」「Position Sizing」「Confidence calculation」「新資料來源」「API / MCP」「production source replacement」「irreversible migration」「production switch」「old UI deletion」「branch deletion」。
  4. **四檔責任**（客戶原文第 5 點，逐字）：「Blueprint：最終產品方向」「BACKLOG：尚未完成的工作」「DECISIONS：正式客戶裁示」「HANDOFF：目前接手位置」；「不得把長期方向只塞進 HANDOFF。」
  5. **關閉規則**（客戶原文第 6 點）：「後續只有真正完成、經測試／audit／CI／main verification 的項目才能關閉；部分完成不得把整個長期方向標成完成。」
  6. 本批範圍（客戶原文第 7 點）：「本次只做治理登記與必要文件同步。」「不要開始 vNext UI、OAuth、選股、Action、Thesis 或其他產品實作。」「不要修改產品 code。」「不要修改舊 UI。」「不要刪 branch。」
- **範圍**：產品方向／治理｜**日期**：2026-10-17｜**決策者**：客戶｜**狀態**：生效（方向）；**所有方向項目實作狀態＝未開始**
- **來源**：D 客戶訊息 2026-10-17T01:52Z（本 session MSG 14；本檔首次入庫）「請把這批已確認的長期產品方向正式保存到 repo，避免只存在聊天紀錄而在後續對話遺失。」
- **與其他 DEC／項目的關係**（撰寫組單組判讀，⚠️ 待第二組 evidence audit）：
  - **不取代任何 DEC**。DEC-009（Decision Gate 清單）同向，第 3 點清單是 DEC-009 的重申／補列（新增明列「Action transition rules」「Confidence calculation」），兩者取聯集。
  - **DEC-054／DEC-055**：Action Layer 方向與 DEC-054 一致；DEC-054 仍不是實作授權，`CV1-FU-02`（再平衡射程）、`CV1-FU-03`（七種 Action 封閉清單）、`CV1-FU-04`（Thesis／Core Decision 規格缺口）**不因本條裁示**。
  - **CV1-RC-01**（MSG 1 §1～§17）、**CV1-RC-07**（§18 推播、§26）：其中與本條清單重疊的方向（Core Decision＋Context Overlay、雙軌、Thesis、Decision Log、LINE 推播）已由客戶核准為**方向**；兩列的**規格細節**（欄位、四態、metrics 等）未因本條裁示，仍為 Research Candidate。對映見 `docs/BACKLOG.md` 第 5 節 cross-ref 欄。
  - **DEC-019**（舊 UI 凍結）、**DEC-020**（切換路線、舊 UI 刪除前置）、**DEC-012**（分支刪除）、**DEC-053**（加減碼比例程序含 Shadow Mode）、**DEC-022** 再平衡三項限制：皆**繼續有效**，本條未改變。
  - ⚠️ **Blueprint 缺口**：第 4 點指名「Blueprint：最終產品方向」，但 main 上撰寫組 `git grep -il -e blueprint -e 藍圖 -- docs PROJECT_RULES.md` 只命中稽核／重構舊文件，**查無現行 Blueprint 文件**（`S2-PRD.md` 只在 handoff 分支）。本批依客戶第 7 點不新建大型文件；缺口登記 `docs/BACKLOG.md` `VN-00`。在 Blueprint 建立前，方向的持久落點＝本條＋BACKLOG 第 5 節。

### DEC-057｜指派 VN-00：建立 vNext Product Blueprint（產品架構／UX／IA 設計批；只設計、不施工）
> 2026-10-17 追加（第 8 節「收到當輪追加」）。ID 照序取下一個未用號（撰寫組 `git grep -oh "DEC-0[0-9]*" | sort -u` 實測最大為 DEC-056）。BACKLOG 登記：DR-2026-10-17-2；落點 `docs/BACKLOG.md` `VN-00` 與第 5.1 節。
- **內容**（逐點對應客戶原文，引號內為原文）：
  1. **取代先前提示**：「本訊息取代先前尚未執行的 UI Audit／UI 改善提示語。」
  2. **本批性質**：「這是一個「產品架構／UX／資訊架構設計批」。」
     - 可以（逐字）：「可以讀 code」「可以實際啟動新 UI」「可以做 Desktop + Mobile audit」「可以建立 wireframe / spec / architecture proposal」「可以更新治理文件／BACKLOG（若符合現行 Constitution）」「可以提出後續 Batch 切分」。
     - 禁止（逐字）：「修改產品 UI code」「修改產品行為」「修改選股公式」「修改 Risk Cap」「實作 Action Layer」「接新 API / MCP」「修改 production data source」「修改舊 UI」「刪除舊 UI」「刪 branch」「production switch」。
     - 「任何尚未有正式規格的部分不得自行用 AI 猜規則。」
     - 產出：「請建立一份可長期維護的 vNext Product Blueprint。」
  3. **客戶明示的產品原則**（⛔ 全部是**方向，不是實作授權**；逐點短引）：
     - 產品定位：「每天替使用者過濾市場噪音，只把真正需要做決定的事情送到面前；每個結論都可以一路追溯到正式規則與客觀資料。」
     - 核心 UX：「Decision first / → Attention / → Risk / → Evidence / → Raw data」。Mobile 核心：「現在怎麼做 / → 為什麼 / → 下一步」；「禁止把 Desktop Dashboard 直接縮小當 Mobile UI。」
     - 分層：「資料層、規則層、決策層、AI 解釋層必須保持分離。」「AI 不得成為客觀資料來源，也不得偷偷修改正式規則。」
     - Google 登入：「使用者開啟 App 後，Google 登入應成為非常明顯的第一級入口。」「請盤點並優先「重用」舊 UI／既有資料層 OAuth 能力，不重造 OAuth。」「Google 登入不是觀看所有公開市場資料的硬 Gate。」「公開市場功能仍可匿名使用。」
     - 使用者語言：「一般 User UI 不直接暴露內部程式術語。」
     - 首頁：「首頁不是 Dashboard。」「不要為了讓首頁有內容而製造 Action。」「不要為了 engagement 製造訊號。」
     - Action 與部位：「Action Engine： / 決定方向。」「Position Sizing Engine： / 決定幅度。」「沒有正式 sizing 規則時禁止 fake precision。」
     - 現金：「UI 不得暗示： / 「沒買股票 = 錯失機會」。」「「維持現金」可以是合理結果。」
     - 選股：「選股方向正式改為雙軌產品設計」（客戶原文標題）；「現行 fundamental prescreen 必須先盤點，但本批禁止修改公式。」「不要再設計一條很長的 hard Gate chain。」「只有有正式風險理由時才 hard veto。」（雙軌 Track A／B 與 Core Decision＋Context Overlay 的**方向**；條件與門檻屬 G1，見下第 4 點與 Blueprint `BP-DR-07`）
     - Not Now：「本輪請建立「Not Now / Won't Do Without Decision」清單。」—— 客戶列舉的「至少」各項逐項收錄於 Blueprint 第 27 節；該清單是客戶列的禁止事項，未經客戶裁示不得做。
  4. **仍需客戶裁示**（客戶原文第五十一節，逐字）：「Backlog ≠ implementation authorization。」「任何： / - 投資公式 / - threshold / - 新資料語意 / - 新 production source / - API/MCP / - Action formula / - Sizing / - major UI flow final approval / 仍需客戶裁示。」
  5. **完成條件與停點**：「本批不要因為藍圖完成就開始施工。」「然後停在安全點。」「不要開始 vNext 1.0 implementation。」「完成後停止，不開始施工。」
  6. **Blueprint 位置**：`docs/vnext/VNEXT_PRODUCT_BLUEPRINT.md`（附 `docs/vnext/UI_AUDIT_2026-10-17.md`）。⚠️ 位置與檔名是**總管內部決定**（`CLAUDE.md` §-1.5 v3 §03-1「目錄如何動態拆分、資料夾如何命名」屬內部自決），**不是客戶裁示**。
- **範圍**：產品方向／治理｜**日期**：2026-10-17｜**決策者**：客戶（第 6 點位置：AI 總管內部）｜**狀態**：生效（指派）；Blueprint 內所有線框、BP-DR-* **皆待客戶裁示**，實作狀態＝未開始
- **來源**：D 客戶訊息 2026-10-17（本 session；本檔首次入庫；確切 UTC 時戳未記錄，只保留日期）「客戶已正式同意將新 UI 朝「投資決策 OS / Investment Inbox」方向改善。」；「請建立一份可長期維護的 vNext Product Blueprint。」
- **與其他 DEC 的關係**（撰寫組單組判讀，⚠️ 待第二組 evidence audit）：
  - **實作 DEC-056 第 4 點**（「Blueprint：最終產品方向」），**不取代任何 DEC**；DEC-056 第 3 點 Decision Gate 清單與本條第 4 點取聯集。
  - **DEC-017**（IA v2 五頁線框）**不因本條改變**：Blueprint 提議的主導航改動（今天／機會／持股／我的，2.0 加動態）列為 Blueprint **BP-DR-01**，未裁示前五頁 IA 照舊。
  - **DEC-003**（草稿先行）：Blueprint 線框即「文字線框草稿」，未經客戶拍板（Blueprint **BP-DR-16**）不得寫 UI code。
  - **DEC-019**、**DEC-020**、**DEC-012**、**DEC-022**、**DEC-053**、**DEC-054**、**DEC-055**：繼續有效，本條未改變。

### DEC-058｜授權 `BP-ERR-01` 第 4 輪最小必要文件修正（Blueprint §8.9 分母、§29.3 自查敘述）
> 2026-10-17 追加（第 8 節「收到當輪追加」）。ID 照序取下一個未用號（文件修正組 `git grep -oh "DEC-0[0-9]*" | sort -u` 實測最大為 DEC-057）。BACKLOG 登記：DR-2026-10-17-3；落點 `docs/BACKLOG.md` 第 5.1.1 節 `BP-ERR-01`。
- **內容**（引號內為客戶原文）：
  1. **授權**：「允許針對 "BP-ERR-01" 進行第 4 輪最小必要文件修正。」
  2. **事實來源**：「請以目前 GitHub main 與實際 production code／"shared/macro_buckets.py::BUCKET_DANGER_SPECS" 為事實來源」。
  3. **修正對象**：「修正 Blueprint §8.9 的錯誤分母，以及因此失效的 §29.3 自查敘述。」
  4. **範圍限制**：「本次只修文件 correctness，不改產品 code、不改公式、不改資料語意、不擴大 Blueprint 產品方向，也不開始 vNext 1.0 implementation。」
- **範圍**：治理／文件｜**日期**：2026-10-17｜**決策者**：客戶｜**狀態**：生效（一次性授權；限 `BP-ERR-01`）
- **來源**：D 客戶訊息 2026-10-17（本 session；本檔首次入庫；確切 UTC 時戳未記錄，只保留日期）「允許針對 "BP-ERR-01" 進行第 4 輪最小必要文件修正。」
- **與其他 DEC 的關係**（文件修正組單組判讀，⚠️ 待第二組 evidence audit）：
  - **DEC-010**（同檔回修超過 2 輪停手問客戶）：本條是**依 DEC-010 停手問過之後**的客戶授權，**不取代、不放寬** DEC-010；授權只涵蓋本次 `BP-ERR-01`，日後 Blueprint 再回修仍適用 DEC-010。
  - **DEC-057**（Blueprint 只設計、不施工）、**DEC-003**（草稿先行）：不變；本次只更正線框示意數字，不是核准線框（BP-DR-16 仍待裁示）。
  - **DEC-049**：不變；Blueprint 只揭露「M1B−M2 現行仍計入危險度燈長期桶分母」這個程式事實，分母要不要排除仍屬 Blueprint `BP-DR-19`。

### DEC-059｜永久治理：Minimum Sufficient Effort、Effort 雙向主動提醒、Silent Autonomous Cruise 強化
> 2026-10-17 追加（第 8 節「收到當輪追加」）。ID 照序取下一個未用號（治理編修組 `git grep -oh "DEC-0[0-9]*" | sort -u` 實測最大為 DEC-058）。BACKLOG 登記：DR-2026-10-17-4。規則本文落點：`PROJECT_RULES.md` 第 3 節（巡航）、第 4 節（打斷清單對映註）、第 9 節（9.1～9.3）、第 11 節（自動繼承）。
- **內容**（引號內為客戶原文）：
  1. **目的**：「請新增一項永久治理要求，避免客戶未來每個對話重複提醒。」
  2. **A. Minimum Sufficient Effort**：「將「推理強度採夠用即可，避免不必要 token／額度浪費」寫入正式 "PROJECT_RULES.md"。」「使用「能可靠完成下一完整階段的最低 Effort」。」「不得因為 High 比較強就預設 High。」「若 Low 足夠，不使用 Medium。/ 若 Medium 足夠，不使用 High。」「等待 CI、等待 audit、等待 workflow 等待狀態，不得要求提高 Effort。」Low／Medium／High 適用清單逐項收錄於 `PROJECT_RULES.md` 9.1。
  3. **B. Effort 主動提醒**：「如果「下一完整階段」明顯應使用不同 Effort，專案 AI 必須在安全停點主動提醒客戶，不得等客戶詢問。」格式「⏸️ 建議切換推理強度 / 下一階段：___ / 建議 Effort：Low / Medium / High / 原因：___ / 切換完成後請回覆「改好了」。」；「若目前 Effort 已足夠：/ - 不要提醒 / - 不要每次重複報告目前 Effort / - 直接工作」；不得在「未 commit 的實作中途」「PR 尚在修正中途」「CI 正在跑」「一個不可安全中斷的完整工作階段中」要求切換；「Effort 切換本身不是產品 Decision Gate。」
  4. **B 追加（同批，雙向）**：「若客戶目前選擇的 Effort 高於下一階段實際所需，且已到安全停點，也應主動提醒「可以降低 Effort」，以避免不必要的 token／額度消耗。」範例格式（逐字收錄於 `PROJECT_RULES.md` 9.2）。撰寫組讀法：第 3 點「若目前 Effort 已足夠：不要提醒」在追加後讀作「目前 Effort 恰好合適時不提醒」（⚠️ 讀法，客戶可推翻）。
  5. **C. Silent Autonomous Cruise**：「預設採靜默自主巡航。」可自行完成的流程鏈（研究 → 實作 → tests → independent audit / review → 修正 → push → PR → CI → 修 CI → merge → main verification → BACKLOG / HANDOFF / DECISIONS 必要同步）；「安全工作以最多 3 個緊密相關項目為一批，避免 scope creep。」禁止回報的中間狀態清單（逐項收錄於 `PROJECT_RULES.md` 第 3 節）；「只有三種情況可以主動打斷客戶」：完整階段完成（「精簡回報，原則 ≤5 行。」）、真正需要客戶裁示、需要切換 Effort；「已經有正式 DECISION 的問題不得重新詢問客戶。」「已確認的 bug，若修法單一且不涉及 Decision Gate，應自行修正、測試、audit、CI，不要包裝成客戶選擇題。」
  6. **D. 持久化**：「"PROJECT_RULES.md"：永久規則」「"docs/HANDOFF.md"：只放 pointer，不複製整套規則」「不得只寫在 HANDOFF。/ 不得只留在 Claude 對話。/ 不得只寫進單次 prompt。」「若已有，整合／強化，不建立互相重複或矛盾的第二套規則。」「保留既有治理優先序。」
- **範圍**：治理｜**日期**：2026-10-17｜**決策者**：客戶｜**狀態**：生效（~~隨本批 PR 合併~~ 已隨 #869 `15bc173e` 合併，main CI run 39019586971 success；2026-10-18 收尾同步補登，證據同 `docs/BACKLOG.md`「3. 已結案」`BP-ERR-01` 列）
- **來源**：D 客戶訊息 2026-10-17（本 session；本檔首次入庫；確切 UTC 時戳未記錄，只保留日期）「請新增一項永久治理要求，避免客戶未來每個對話重複提醒。」；同批追加「若客戶目前選擇的 Effort 高於下一階段實際所需…也應主動提醒「可以降低 Effort」」。
- **與其他 DEC 的關係**（治理編修組單組判讀，⚠️ 待第二組 evidence audit）：
  - **DEC-007**、**DEC-006**（巡航、每批 ≤3 項）：**強化**，不取代；DEC-006 的停止條件與防膨脹 Gate 不變。
  - **DEC-014**（模型／模式／Effort 自主管理）：**部分取代** —— Effort 的分級改依本條清單、Effort-only 切換改用本條格式並改為雙向提醒；DEC-014 的模型／模式切換格式、「改好了」後不重摘要／不重問／不重做、等 CI 不切換等仍有效（`PROJECT_RULES.md` 9.3）。
  - **DEC-013**（不重問）、**DEC-009**（Decision Gate）：同向；本條打斷清單逐項對映 `PROJECT_RULES.md` 第 4 節既有表，未增刪該表。
  - **DEC-001**（派工）／`CLAUDE.md` §-2：不變 —— 巡航擴大的是「不必問客戶」，不是「不必派工」；Effort 不影響派工與稽核。
  - **`CLAUDE.md`**：不取代、不修改。≤5 行回報與 `CLAUDE.md` §-2 規則 6／§-1.5.A-7 揭露義務並存；與 `CLAUDE.md` §-1.5 v1 第三條「自我審核五段呈現」、§-1.5 第四條／v3 §04 三段式交付報告（含判定 6 清理項目），以及 `PROCESS.md` §1（/compact 提醒）、§4（四段報告）的張力登記 `docs/BACKLOG.md` `CV1-DR-10`，裁示前以 `CLAUDE.md` 為準。（2026-10-17 更新：`CV1-DR-10` 已由客戶裁示，見 **DEC-060**；`CLAUDE.md`／`PROCESS.md` 依客戶授權同步加註）

### DEC-060｜回報格式定案（`CV1-DR-10` 裁示）：完整證據留 PR、一般完成回報 ≤5 行、裁示題只留裁示所需資訊
> 2026-10-17 追加（第 8 節「收到當輪追加」）。ID 照序取下一個未用號（治理編修組 `git grep -oh "DEC-0[0-9]*" | sort -u` 實測最大為 DEC-059）。BACKLOG 登記：DR-2026-10-17-5；裁示對象：`docs/BACKLOG.md` `CV1-DR-10`。
- **內容**（引號內為客戶原文）：
  1. 「同意 CV1-DR-10 推薦方案：」
  2. 「完整技術／稽核證據留在 PR。」
  3. 「對客戶的一般完成回報原則 ≤5 行。」
  4. 「若真正需要客戶裁示，可超過 5 行，但只保留完成裁示所需資訊。」
  5. 「請正式同步治理文件，消除 CLAUDE.md／PROCESS.md／PROJECT_RULES 之間的回報格式張力。」
- **落地讀法**（治理編修組依上列原文整理，⚠️ 讀法，客戶可推翻）：`CLAUDE.md` §-1.5 v1 第三條「自我審核」五段、第四條／v3 §04 三段式交付報告（含 §-1.5.F 判定 6 清理項目逐檔列出）、`PROCESS.md` §4 四段報告 —— **仍必須完整產出**，落點改為 **PR 描述**（repo 可追溯）；對客戶的完成回報為其 ≤5 行摘要＋PR 連結；`PROCESS.md` §1 的 /compact 提醒併入完成回報的 ≤5 行內。⛔ **揭露義務不減**：未經第二組驗證的全稱句、沒實測的部分仍須在 ≤5 行內標明（可濃縮一句並指向 PR）（`CLAUDE.md` §-2 規則 6、§-1.5.A-7）。
- **範圍**：治理（回報格式）｜**日期**：2026-10-17｜**決策者**：客戶｜**狀態**：生效（~~隨本批 PR 合併~~ 已隨 #870 `7b803b4f` 合併，main CI run 39042558728 success；2026-10-18 收尾同步補登）
- **來源**：D 客戶訊息 2026-10-17（本 session；本檔首次入庫；確切 UTC 時戳未記錄，只保留日期）「同意 CV1-DR-10 推薦方案：」。
- **與其他 DEC／文件的關係**：**補充 DEC-059**（第 3 點「≤5 行」的射程與例外由本條定案），不取代任何 DEC。依客戶第 5 點，`CLAUDE.md`（§-1.5.A-3、§-1.5.A-7、§-1.5.F 判定 6 附近加註）與 `PROCESS.md`（§1、§4 加註）**同步加註**；逐字封存的 v1／v3 頒布原文區塊**未動**。`PROJECT_RULES.md` 第 3 節暫行讀法改為正式規則。

### DEC-061｜Effort 防漏：每個階段邊界強制內部 Effort Check（含 High → Medium／Low 主動降級提醒）
> 2026-10-18 追加（第 8 節「收到當輪追加」）。ID 照序取下一個未用號（治理編修組 `git grep -oh "DEC-0[0-9]*" | sort -u` 實測最大為 DEC-060）。BACKLOG 登記：DR-2026-10-18-1。規則本文落點：`PROJECT_RULES.md` 9.2（就地修改）；第 3 節第 3 種打斷情況、9.1 各加一行 pointer。
- **事件**：#872（`UIA-01`／`02`／`07` 高推理批）合併後，專案 AI 直接進入純文件收尾同步（#873，BACKLOG／HANDOFF 同步），**未提醒客戶把 Effort 從 High 降為 Low**；客戶須自行詢問。（同批之前 Low→High 升級提醒、#873 後 High→Medium 提醒皆有正確觸發。）
- **內容**（客戶原文，逐字）：
  「1. 重新檢查 DEC-059、PROJECT_RULES.md 與實際執行流程，找出為什麼「主動降 Effort」沒有被觸發。
  2. 將防漏機制永久化，但不要建立重複規則。
  3. 從今以後，每個「完整工作階段結束／下一完整階段開始前」都必須先做一次內部 Effort Check：
     - 下一階段最低足夠 Effort 是 Low／Medium／High？
     - 與目前 Effort 是否一致？
  4. 若一致：保持靜默，直接繼續。
  5. 若不一致：必須在開始下一完整階段前停下，主動使用既定格式提醒客戶升級或降級。
  6. 特別注意「High → Medium／Low」也必須主動提醒，不能只提醒升級。
  7. CI 等待、audit 等待、commit/push、PR 開啟等短暫狀態，不算新的完整階段，不要頻繁切換。
  8. 不得在未提交實作、PR 修復途中或不可分割工作階段中要求切換。」
  提醒格式沿用 `PROJECT_RULES.md` 9.2 既定格式（不新增格式）。
- **根因**（治理編修組依規則原文判讀，⚠️ 單組結論，待第二組 evidence audit）：
  1. **裁量式觸發、無強制檢查步驟**：舊 9.2「如果「下一完整階段」**明顯應使用**不同 Effort…主動提醒」—— 只有「感覺不同」時才會想到去比對；9.1「必須自行判斷所需 Effort」沒有定義在哪個時點、以什麼步驟做。
  2. **收尾同步未被定義為獨立完整階段（主因）**：第 3 節巡航鏈把「merge → main verification → BACKLOG／HANDOFF／DECISIONS 必要同步」寫成同一條流程，第 7 節 DoD 也把文件更新列為「完成」的一部分 → 收尾同步被當成同一批延續，「下一完整階段開始前」這個邊界從未成立。
  3. **時機限制被擴張解讀**：舊 9.2「不得在…一個不可安全中斷的完整工作階段中要求切換」配合上點，被讀成整批到收尾都不可中斷；第 3 節「完整階段完成才回報」再把提醒推遲到最終回報。
  4. 升級方向未漏、降級方向漏：升級時「下一批明顯更難」容易被感知；降級時任務仍在同一條巡航鏈上、無感知落差 —— 與第 1 點的裁量式觸發一致。
- **改了什麼**：`PROJECT_RULES.md` 9.2 就地修改（舊觸發句與舊時機句皆以刪除線保留）：(a) 每個階段邊界強制內部 Effort Check 兩題；(b) 一致靜默、不一致停下以既定格式提醒，明文 High → Medium／Low 必須提醒；(c) 階段邊界定義（新批次開始前、Decision Gate 裁示後動工前、**merge＋main verification → 收尾文件同步**、收尾完成後）；(d) 不算階段的短暫狀態（CI／audit／workflow 等待、commit／push、PR 開啟）；(e) 不切換時機原四項保留並補「未提交實作」「PR 修復途中」，射程以階段邊界為界。第 3 節、9.1 只加 pointer，不重複規則本文。
- **範圍**：治理｜**日期**：2026-10-18｜**決策者**：客戶｜**狀態**：生效（~~隨本批 PR 合併~~ 已隨 #874 `5cec364e` 合併，main CI run 39107408166 success；2026-10-18 收尾同步補登，證據為總管 GitHub 實查、撰寫組未重查）
- **來源**：D 客戶訊息 2026-10-18（本 session；確切 UTC 時戳未記錄，只保留日期），原文如上。
- **與其他 DEC 的關係**：**強化 DEC-059**（B. Effort 主動提醒：裁量式觸發改為強制檢查，並定義階段邊界），不取代、不新增第二套規則系統；DEC-059 的 9.1 分級表、雙向提醒、格式、「改好了」後不重摘要（DEC-014）全部不變。DEC-007／DEC-006（巡航）不變 —— 巡航仍不必問客戶，只是在階段邊界多一個內部 Check。`CLAUDE.md`、`PROCESS.md` 無 Effort 規則（治理編修組 `grep -i "effort\|推理強度"` 實測 0 命中），未動。

### DEC-062｜vNext 1.0 Decision Gate 裁示（`VN1-Q1`～`VN1-Q5`）
> 2026-10-18 追加（第 8 節「收到當輪追加」）。ID 照序取下一個未用號（治理編修組 `git grep -oh "DEC-0[0-9]*" | sort -u` 實測最大為 DEC-061）。BACKLOG 登記：DR-2026-10-18-3。題目全文與各題逐條紀錄見 `docs/vnext/VNEXT_1_0_DECISION_GATES.md`。
- **內容**（客戶原文，逐字）：
  「Q1：B。
  Q2：B，並同意短期保存一次性驗證碼；不得保存 Google 密碼或憑證。
  Q3：A。正式環境是否有系統帳號，請自行檢查可取得的設定；無法確認再回報，不要猜。
  Q4：A；但暫不核准「每日紀錄存 repo 追蹤檔」。先研究最小、可靠、可持久化且符合「資料層 ≠ AI 推理層」的保存方式，再提出建議；不要直接把 Git repo 當 production datastore。保存方式未定前可先採 B 顯示「從今天開始記錄」。
  Q5：A，並確認代理值不計分、停用項明示停用、無資料來源不得宣稱通過。
  請先正式登記以上裁示。開始實作前依 §9.2 做 Effort Check；若登入／安全批需要 High，先停下提醒我切換。vNext 1.0 請分安全小批次執行，不要一次全面施工。」
- **正式裁示文本**（客戶同日重送的詳細版，逐字；與上方簡短版並列，兩者衝突時以本版為準）：
  「1. VN1-Q1：選 B。先核准四格導覽（今天／機會／持股／我的）、登入晶片＋我的頁、Sheet 選擇、今天頁、狀態配色／資料狀態；持股維持唯讀，新版不設 production default；其餘 1.0 線框下一輪，持股四組分組延 2.0。
  2. VN1-Q2：選 B。重新整理後以「維持登入」為目標；先完成 SEC-2 防偽造與可行性驗證，若不可可靠實作則退回 A。同意伺服器短期保存一次性驗證碼；不得保存 Google 密碼或 Google 憑證。
  3. VN1-Q3：選 A。匿名使用者不得透過 system/service account 讀私人持股 Sheet。只有登入且本身具該 Sheet 權限者才能讀取。請自行檢查目前可取得的 production 設定／證據，確認 system/service account 是否存在；無法確認就明示 unknown，不要猜。
  4. VN1-Q4：方向選 A，但「每日紀錄直接存在 repo 追蹤檔」目前不核准。先研究並驗證最小、可靠、可持久化且符合「資料層 ≠ AI 推理層」的保存方案，包括 Streamlit Cloud persistence、restart/deployment、concurrency、寫入可靠性與資料責任。保存方式尚未決定前，1.0 UX 可先採「從今天開始記錄」，不得製造不存在的歷史比較。不得自行新增變動大小門檻。
  5. VN1-Q5：選 A。延續最差燈＋N/M 揭露。Required Core 完整且新鮮才能宣稱「資料正常」。代理值只顯示、不計分；已停用明示「已停用」；沒有資料來源／資料缺漏不得宣稱通過。同意上述原則同樣適用於總經彙總燈。」
  另（客戶原文）：「不要一次施工整個 vNext 1.0」；「後續按安全小 Batch 推進」；「建議第一個 implementation Batch 優先處理安全前置依賴（SEC-2／SEC-3），但請先依最新 repo、依賴與風險自行確認最小安全批次」。
- **逐題對映**（撰寫組依題目檔對映，⚠️ 單組判讀，待第二組 evidence audit）：
  - **Q1＝B**：先核准 1.0 重點範圍（四格導覽、首屏登入晶片＋「我的」登入卡、Sheet 選擇位置、持股唯讀直讀、新舊並存兩入口且新版不設 production default、今天頁、「我的」頁、BP §2.1／§15 狀態配色與資料狀態表）**作為線框送審範圍**；機會頁等其餘 1.0 線框留 1.0 下一輪送審；持股四組分組（`BP-DR-14`）延 2.0。⚠️ **這是核准「送審範圍」，不是核准線框本身**：依 DEC-003，線框須依此範圍送審、客戶拍板後才可寫 UI code。
  - **Q2＝B＋附帶同意「是」**：保持登入（先修 `SEC-2` → 可行性驗證 → 不過退回 A）；同意伺服器短期保存一次性驗證碼；⛔ **不得保存 Google 密碼或憑證**（客戶原文，屬硬限制）。
  - **Q3＝A**：關閉匿名訪客經系統帳號（Service Account）讀 Sheet 的路徑（`SEC-3`）；正式環境是否有系統帳號 → 依指示「自行檢查、無法確認再回報、不要猜」，檢查結果見題目檔 VN1-Q3 節（結論：**unknown／無法確認**）。
  - **Q4＝A，附帶問題「否（暫不核准）」**：比較規則採 A；⛔ **暫不核准**「每日紀錄存 repo 追蹤檔」、⛔ 不得把 Git repo 當 production datastore；保存方式**先研究並驗證再提建議**（新開研究項 `VN1-STORE`，範圍含 Streamlit Cloud persistence、restart/deployment、concurrency、寫入可靠性、資料責任）；⛔ 不得製造不存在的歷史比較；⛔ 不得自行新增變動大小門檻；保存方式未定前採 B「從今天開始記錄」。
  - **Q5＝A＋三點確認**：代理值不計分（DEC-037）、停用項明示停用（DEC-049／DEC-051）、無資料來源不得宣稱通過（延伸 DEC-044）—— 客戶確認上述適用於總經彙總燈。
  - **流程指示**：開始實作前依 `PROJECT_RULES.md` 9.2 做 Effort Check（DEC-061）；登入／安全批若需 High → 先停下提醒客戶切換；vNext 1.0 分安全小批次、不一次全面施工。
- **範圍**：產品／UX（Q1、Q4、Q5）、credentials／account access（Q2、Q3，DEC-009）、資料保存（Q4 附帶，DEC-009）、治理流程｜**日期**：2026-10-18｜**決策者**：客戶｜**狀態**：生效（裁示登記；**不是**各批實作完成）；📌 2026-10-18 實作進度（append-only）：`1.0-B1`（Q2 前置 `SEC-2`＋Q3 `SEC-3`）完成 —— #877、`a9ba83c1`、main CI run 39132620519 success；~~Q2 保持登入 PoC（`1.0-B2`）尚未開始~~；📌 2026-10-19 實作進度（append-only；上句刪除線為有意識的變更，不是漏刪）：`1.0-B2`（Q2 保持登入）**in-progress** —— commits `23596359`（重新整理後以 Google `prompt=none` 靜默恢復登入；⛔ 不保存任何 Google 憑證）、`1d169927`、`e7c2cba7`（稽核修正第 1、2 輪）、`efd3d369`（第 3 輪，客戶依 DEC-010 核准，DR-2026-10-19-1；⛔ 不得自行進入第四輪）；PR 待開／未合併；未在 Streamlit Cloud 實測（BACKLOG `B2-FU-1`）；可行性結論未定（總管轉述）；📌 2026-10-19 更新（append-only）：上述「PR 待開／未合併」自本日起不再成立（有意識的變更，不是漏刪）—— `1.0-B2 程式已合併（#879、`cef52c2e`、main CI run 39203796408 success（Fast＋Slow；總管轉述））；**待客戶正式網站驗收（`B2-FU-1`）**；驗不過依裁示退回 A（可先以 secrets `oauth_silent_reauth=false` 關閉）；`B2-FU-1`～`5` 仍 open；⚠️ 可行性結論未定，不得視為已結案
- **來源**：D 客戶訊息 2026-10-18（本 session；確切 UTC 時戳未記錄，只保留日期），原文如上。
- **與其他 DEC 的關係**（撰寫組單組判讀，⚠️ 待第二組 evidence audit）：
  - **DEC-057**（「不要開始 vNext 1.0 implementation。」）：本條客戶要求「vNext 1.0 請分安全小批次執行」，視為客戶對 1.0 施工的**分批授權方向**；⚠️ 各批仍須依 9.2 Effort Check 與 `CLAUDE.md` §-1 逐批進行，本登記本身**未開始任何實作**。總管提出的小批次順序（`1.0-B1`～`B4`）為**建議、不是授權**，見題目檔第 6 節。
  - **DEC-003**（草稿先行）：不變；Q1 只定送審範圍，UI code 仍待線框拍板。
  - **DEC-009**：Q2 附帶同意與 Q4 附帶問題即依本條保留的客戶同意；Q4 保存位置**未同意**，維持待客戶。
  - **DEC-020**（新 UI 切預設另送）、**DEC-037**、**DEC-044**、**DEC-046**、**DEC-048**、**DEC-049**、**DEC-051**：不變；Q5 確認 DEC-037／049／051 與 DEC-044 的延伸同樣適用於總經彙總燈。
  - **DEC-061**：本條流程指示即依 DEC-061 執行，不新增規則。

### DEC-063｜`VN1-STORE` 保存位置裁示 A：系統專用 Google Sheet（只核准方向＋最小 PoC，未核准 production 排程寫入）
> 2026-10-19 追加。ID 照序取下一個未用號（撰寫組 `git grep -oh "DEC-0[0-9]*" | sort -u` 實測最大為 DEC-062）。BACKLOG 登記：DR-2026-10-19-2。研究與 PoC 結果見 `docs/vnext/VN1_STORE_RESEARCH.md`（第 8 節「PoC 結果」）。
- **內容**（客戶原文，逐字）：
  「裁示：A。採用「系統專用 Google Sheet」作為每日 System Risk Cap 歷史紀錄的持久化位置。但先不要直接進入正式 production 寫入，下一步先做最小 PoC：1. 驗證 GitHub Actions／無 Streamlit 網頁環境下，是否能依既有正式資料層與規則完整計算每日 System Risk Cap。2. 不得為了讓排程成功而另造一套公式、另造資料來源、補 0、猜測缺值，或讓 AI 參與客觀資料產生。3. 若 Required Core 不完整／資料過期／取數失敗，必須保留真實資料狀態；不得寫成正常有效 Risk Cap。4. 系統歷史 Sheet 與我的個人持股 Sheet 必須完全分離。5. 寫入端與網站讀取端權限分離：排程帳號：僅具必要寫入權限。網站帳號：只讀這張系統歷史 Sheet。不得重新引入 SEC-3。6. 每日紀錄須可追溯，至少保留 as-of、資料狀態、正式 Risk Cap 值、規則版本／必要 provenance；實際 schema 先依既有規則設計，不得自行新增投資語意。7. 歷史不存在時仍顯示「從今天開始記錄」；資料過期／排程失敗時不得產生假的「和上次比」。8. 同一天重跑的 idempotency／重複紀錄處理必須在 PoC 中驗證。9. PoC 完成後先做獨立稽核，再回報結果與需要我手動建立 Google Sheet／帳號的精簡步驟；涉及新憑證或權限時依 DEC-009 停下。10. PR #881 若 CI 全綠，可依既定流程先合併研究文件；PoC 另開小批次，不混入 #881。本次只核准保存方向 A 與最小 PoC；尚未核准正式 production 排程寫入。」
- **逐點對映**（撰寫組單組判讀，⚠️ 待第二組 evidence audit）：
  - 保存位置＝研究報告方案 (c) 系統專用 Google Sheet（`VN1_STORE_RESEARCH.md` 第 3、5 節）；次選 GCS 不採用。
  - 第 1～8 點＝最小 PoC 的驗收條件；PoC 實作見分支 `claude/investment-inbox-product-design-m1lu7v` commits `f236507f`、`3edc0872`（未開 PR、未合併；總管轉述）。
  - 第 9 點：PoC 後先獨立稽核、再回報與送客戶「建立 Sheet／帳號」精簡步驟；**新憑證或權限依 DEC-009 停下**。
  - 第 10 點：#881（研究文件）與 PoC 分批；#881 已合併（`8c4722f4`；main CI 撰寫組未查）。
  - ⛔ **尚未核准**正式 production 排程寫入；⛔ 未建立任何 Sheet／帳號／secret。
- **範圍**：資料保存（DEC-009）、credentials／account access（DEC-009）、產品（「從今天開始記錄」維持）｜**日期**：2026-10-19｜**決策者**：客戶｜**狀態**：生效（方向＋PoC 授權；production 寫入未授權）<br>📌 2026-10-19 狀態補註（append-only）：PoC 已合併 #882（`a45c7405`、main CI run 39234825821 success）；Actions 環境實跑待客戶手動觸發（代理觸發 403）；Sheet／帳號／secrets 待客戶建立；production 寫入仍未授權<br>📌 2026-10-19 狀態補註（append-only）：憑證設計已裁示 DEC-064（G1 WIF 無 key writer、G2 唯讀 key reader、G3 只調查）；PoC Actions dry-run 客戶回報 run 39249934107 success；production 寫入仍未授權<br>📌 2026-10-20 狀態補註（append-only）：客戶已以 **DEC-066** 裁示 Production Gate —— **首次人工** production-write 有條件核准（未來以獨立 PR 一次性翻 `PRODUCTION_WRITE_APPROVED`，前提為 Environment `production-risk-cap`＋WIF 強化先完成，寫完立即改回 `False`）；**每日排程仍 NOT APPROVED**（DEC-066 F，獨立 Gate）。上兩則「production 寫入仍未授權」自本日起只剩「首次人工寫入前提未完成、排程未核准」（有意識的變更，不是漏刪）；本條原文不改
- **來源**：D 客戶訊息 2026-10-19（本 session；確切 UTC 時戳未記錄，只保留日期；經總管轉交，逐字未經第二組比對），原文如上。
- **與其他 DEC 的關係**（撰寫組單組判讀，⚠️ 待第二組 evidence audit）：
  - **DEC-062**（Q4 附帶「Q4 保存位置**未同意**，維持待客戶」）：本條裁示了保存**方向**；DEC-062 該句的「未同意」自本條起只剩「production 寫入與新憑證未同意」—— DEC-062 原文不改（append-only）。
  - **DEC-009**：新 Sheet／兩支 service account／secrets 屬須客戶同意事項；本條**未**授權建立，第 9 點明示涉及時停下。
  - **DEC-027**（資料層 ≠ AI 分析層）：第 2 點重申；PoC 呼叫鏈直接檔案不 import AI 模組（AST 守衛，非全遞移圖）。
  - **SEC-3**（#877 已結案）：第 5 點要求不得重新引入；PoC 不使用個人持股 Sheet 的既有 SA 金鑰。

### DEC-064｜`VN1-STORE` 憑證與權限裁示（G1／G2 核准、G3 只核准調查；production 寫入仍未核准）
> 2026-10-19 追加（第 8 節「收到當輪追加」）。ID 照序取下一個未用號（撰寫組 `git grep -oh "DEC-0[0-9]*" | sort -u` 實測最大為 DEC-063）。BACKLOG 登記：DR-2026-10-19-2（append）。設定規格：`docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md`。
- **內容**（客戶原文，逐字）：
  「G1：核准。VN1-STORE writer 採 GitHub OIDC + Google Workload Identity Federation。建立專用 risk-cap-writer Service Account，但禁止建立 writer JSON key。
  G2：核准。reader 採獨立 risk-cap-reader Service Account + 唯讀 JSON key。只允許讀 System Risk Cap 專用 Sheet，不得與 writer 共用身分。
  G3：目前只核准調查，不核准修改。請確認既有 GCP_SERVICE_ACCOUNT_JSON 對應的 client_email / project_id，判斷它實際屬於哪個 Google Cloud 專案及目前用途。不得在回報中輸出 private_key、完整 JSON 或其他 Secret。不得刪除、輪換、替換既有 key，也不得改動既有每日持股推播。
  共同權限原則：risk-cap-writer / reader 都不得取得個人持股 Sheet 權限。不得沿用 fund-nav。System Risk Cap Sheet 與 holdings Sheet 完全隔離。上線前必須做反向權限測試。正式每日 production 寫入仍未核准。」
- **客戶補充（同日，經總管轉交；非逐字）**：既有 `GCP_SERVICE_ACCOUNT_JSON` 可能屬於 fund-dashboard 專案的 fund-nav SA。G3 調查範圍：確認是否為 fund-nav；股票 repo 哪些功能使用（現為 `push_holdings_daily.yml`＋`scripts/push_holdings_daily.py` 經 `gsheet_sa_reader.py`（`spreadsheets.readonly`），另手動 `scripts/diagnose_etf_total_return_fix.py`）；評估跨專案／權限過大風險；日後遷移到股票專用 SA 另案評估。⛔ 禁止修改／刪除／輪換／停用 fund-nav、影響每日持股推播、沿用 fund-nav 作 Risk Cap writer／reader。
- **落地讀法**（撰寫組單組，⚠️ 待第二組 evidence audit）：GitHub secret `RISK_CAP_HISTORY_WRITER_SA_JSON` 退役、不建立（G1 無 writer key）；只新增 `RISK_CAP_HISTORY_SHEET_ID`；reader key 只放 Streamlit secrets 獨立表格（提案 `[risk_cap_history_reader]`，不得與 `[gcp_service_account]` 同名）。程式端保留名 `shared/risk_cap_history_policy.py:177` 於未來實作批次退役（本批不改 code）。
- **範圍**：credentials／account access（DEC-009）｜**日期**：2026-10-19｜**決策者**：客戶｜**狀態**：生效（身分設計核准；資源由客戶手動建立；⛔ production 寫入未核准；⛔ G3 未核准任何修改）<br>📌 2026-10-19 狀態補註（append-only）：#884 已合併（`a6eaf72c`、PR Check run 39265077027 success；撰寫組 GitHub API 實查）；客戶回報 G1／G2 手動設定已完成（客戶回報，非 repo 查證；總管對照與本條一致，待確認項與反向權限測試未完成，見 `docs/BACKLOG.md` `VN1-STORE`）；程式接線未實作；G3 唯讀調查完成、遷移另案待客戶決定（`docs/BACKLOG.md` `VN1-G3-FU-1`）；production 寫入仍未核准<br>📌 2026-10-19 狀態補註 2（append-only）：#886 已合併（main `2c693a20`；PR Check fast＋slow success on head `80898b08`）—— workflow `mode` 輸入（預設 dry-run／`wif-auth-only`）、job `wif_auth_only`（僅 job 層級 `id-token: write`、actions 完整 SHA 釘版）、`.gitignore` `gha-creds-*.json`；`WRITER_SA_ENV_VAR` 退役（上方「落地讀法」所述「程式端保留名…於未來實作批次退役」自本日起已完成，有意識的變更，不是漏刪）。WIF auth-only run 39336051675 **PASS**（impersonate `risk-cap-writer`，未讀寫 Sheet）。客戶確認 (a)～(f) PASS（(c) Sheet ID secret 刻意延到 Sheet 接線批）。⛔ 仍未做：規格第 5 節 P1／P2／R1～R5、writer 分享給 Sheet、gate 檢查 WIF 憑證、Streamlit reader 接線；⛔ production 寫入仍未核准（`PRODUCTION_WRITE_APPROVED=False`）<br>📌 2026-10-20 狀態補註（append-only）：規格第 5 節 P1／P2／R1～R5 全部 PASS（runs 39372770704／39373289602／39374189381／39374562365，main `c01b74b9`＝#888；總管自 Actions log 查證）；憑證／權限邊界 Gate **正式關閉**；⛔ production 寫入仍未核准。測試例外見 DEC-065<br>📌 2026-10-20 狀態補註 3（append-only；撰寫組依總管轉述，非客戶原文）：Production Wiring 批（分支 `claude/jolly-mccarthy-sonbl8`，commits `67701562`、`ef905cf0`（回修第 1 輪）；兩組獨立 QA 對 `67701562` 均 0 MUST-FIX（總管轉述）；**未開 PR、未合併**）。reader：L3 `src/services/risk_cap_history_reader_service.read_history` 已接線（只讀 Streamlit secrets `[risk_cap_history_reader]`＋`risk_cap_history_sheet_id`；只快取成功讀取；VALID 列缺上限值 ⇒ `CONTENT_SUSPECT`、不比較；**沒有任何 UI 呼叫端**）；writer：workflow `risk_cap_history_poc.yml` 新增 `production-write` mode（compute job 無 id-token → main-only 寫入 job），寫入 job 在任何 auth 之前先檢查核准旗標 ⇒ **目前恆紅、什麼都不寫**；`PRODUCTION_WRITE_APPROVED` 仍為 `False`；無 schedule；未變更 IAM／WIF／Sheet 分享。⛔ 本補註**不是**新的客戶裁示，也不是 production 授權；production 每日寫入最終核准的前置清單見 `docs/BACKLOG.md` 1.1 `VN1-STORE-PROD`。<br>📌 2026-10-20 狀態補註 4（append-only）：補註 3 的 Production Wiring 批**已合併**（#890、main `56904662`、PR Check run 39389812753 success；撰寫組 `gh run view` 實查）—— 補註 3 所述「未開 PR、未合併」自本日起不再成立（有意識的變更，不是漏刪）。其後 Pre-Hardening 批（經總管指派；分支 `claude/jolly-mccarthy-sonbl8`、未開 PR）只做 hash 鎖定依賴、共用 concurrency group、首次寫入檢查程式（未執行）、log-only reader smoke（旗標預設關）與 GitHub Environment／WIF 條件**設計提案**（`docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 第 8 節）；⛔ 未改 IAM／WIF／Sheet 分享、⛔ 未建立 environment；G1／G2 身分設計不變。⛔ 本補註**不是**新的客戶裁示，也不是 production 授權。<br>📌 2026-10-20 狀態補註 5（append-only）：Pre-Hardening **已合併**（#891、main `49009687`）；空白分頁修正 **已合併**（#892、merge `35f67c0c`；PR Fast＋Slow success、合併後 main push run 39428438762 success）；網站 reader 真連線 smoke（客戶實跑、總管轉述）`read_status=EMPTY identity_ok=True header_state=ABSENT data_rows=0 compare_status=START_RECORDING` **PASS**、smoke 旗標已由客戶刪除 —— 補註 4 所述「Pre-Hardening…未開 PR」自本日起不再成立（有意識的變更，不是漏刪）。客戶已以 **DEC-066** 裁示 Production Gate（首次人工寫入有條件核准；Environment＋WIF 強化為首寫前 MUST，順序 Environment → workflow `environment:` → WIF condition → 首寫；每日排程 NOT APPROVED）；G1／G2 身分設計不變，WIF condition 收緊屬 DEC-066 C Step 3。
- **來源**：D 客戶訊息 2026-10-19（本 session；確切 UTC 時戳未記錄，只保留日期；經總管轉交，逐字未經第二組比對），原文如上。PoC Actions dry-run：客戶回報 run 39249934107 success（VALID、`exposure_limit_pct` 30、同日重跑 APPENDED→NOOP_DUPLICATE；撰寫組未重查）。
- **與其他 DEC 的關係**：**補充 DEC-063**（第 5 點寫入／讀取權限分離的具體身分設計），不取代；DEC-009 credentials gate 由本條就 G1／G2 開放「客戶手動建立」，未開放 AI 建立任何資源；SEC-3（#877）不重新引入。

### DEC-065｜`VN1-STORE` 權限測試例外：一次性 reader 測試 secret＋R1 安全唯讀解讀（不是 production 設計變更）
> 2026-10-20 追加（第 8 節「收到當輪追加」；ID 照序取下一個未用號，撰寫組 `git grep` 實測最大為 DEC-064）。BACKLOG 登記：DR-2026-10-20-1。
- **內容**（客戶裁示，經總管轉交；**非逐字**）：(1) 為執行規格第 5 節 P2／R2／R3，核准**一次性**測試例外 GitHub secret `RISK_CAP_READER_TEST_SA_JSON`（另建測試用 reader JSON key）；測試後刪除。這**不是** production 設計變更 —— reader key 仍只放 Streamlit secrets（DEC-064 G2 不變）。(2) R1 採**安全唯讀解讀**：writer 對持股 Sheet 只做讀取 GET，不做寫入嘗試。
- **範圍**：credentials／account access（DEC-009）｜**日期**：2026-10-20｜**決策者**：客戶｜**狀態**：已執行完畢（客戶回報：該 secret 已刪除、2026-10-20 測試 key 已自 GCP 刪除、2026-10-19 Streamlit key 保留、R4 暫時分支已刪除）；⛔ production 寫入仍未核准<br>📌 2026-10-20 狀態補註（append-only）：production 寫入的首次人工寫入已由 **DEC-066** 有條件核准（前提未完成、旗標仍 `False`）；上句「仍未核准」自本日起依 DEC-066 讀（有意識的變更，不是漏刪）；本條測試例外內容不受影響
- **來源**：D 客戶訊息 2026-10-20（本 session；經總管轉交，非逐字）。結果見 `docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 5.4。
- **與其他 DEC 的關係**：補充 DEC-064（測試程序例外），不取代；DEC-063 production 寫入 gate 不變。

### DEC-066｜`VN1-STORE` Production Gate 裁示：首次人工寫入有條件核准（一次性旗標＋Environment／WIF 先行）、FAIL-STOP、單一 writer；Daily Schedule **NOT APPROVED**
> 2026-10-20 追加（第 8 節「收到當輪追加」；ID 照序取下一個未用號，撰寫組 `git grep -oh "DEC-0[0-9]*" | sort -u` 實測最大為 DEC-065）。BACKLOG 登記：DR-2026-10-20-3。盤點要點、Environment 設定要求、首次寫入 Runbook：`docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 8.11。
- **內容**（**客戶提示語原文經總管轉交；以下為要點整理，非逐字**；「」內為盡量保留的關鍵原句，同樣經總管轉交、撰寫組未見客戶訊息原件、未經第二組比對）：
  - **A｜一次性開關**：核准**未來以獨立 PR** 將 `PRODUCTION_WRITE_APPROVED`（`shared/risk_cap_history_policy.py`）由 `False` 改為 `True`，並同步政策測試；**本批不改**。首次人工 production-write 完成後，「不論成功或失敗中斷」，下一個動作必須立即以獨立 PR 改回 `False`；「main 不得長期維持 True」；「Production Write 授權 ≠ Daily Schedule 授權」。
  - **B｜第一筆**：正式寫入當天必須先跑 `mode=dry-run`，只有 `status=VALID` 且 `exposure_limit_pct` 等必要輸出正常，才允許觸發 `production-write`。若 dry-run VALID、但寫入時因不可抗力留下非 VALID 列：保留、不刪、不覆寫、當天不重寫，視為真實系統歷史；「不得為漂亮第一筆而改歷史」。
  - **C｜Environment／WIF**：客戶**正式否決**「首寫先跳過 Environment」方案；首次正式寫入前 Environment＋WIF 強化為 **MUST**。固定順序：
    - **Step 1**：客戶手動建立 Environment `production-risk-cap` —— Required reviewer＝客戶本人；Prevent self-review＝**關閉**；Deployment branch＝**Selected branches → `main`**；Admin bypass＝依 GitHub 當下 UI 可達成的**最嚴格**設定；若 UI 能力與盤點不同，「不猜、停下回報」。Environment 必須**先建好** workflow 才能引用；⛔ 禁止先引用不存在的 Environment（會自動建立一個**無保護**的 environment；註：技術事實，非客戶原話）。
    - **Step 2**：客戶確認建好後，才允許下一批 PR 在 `production_write` job 加 `environment: production-risk-cap` 並同步測試守衛。
    - **Step 3**：該 PR 合併後，客戶提供 WIF provider **現行 describe 原文**；確認原始 condition 後才修改 provider，預定新增 `environment == production-risk-cap`、`event_name == workflow_dispatch`；「不得猜測現行 condition」。
    - **Step 4**（Step 4 為撰寫組依 DEC-066 A／B 整理，非客戶另立的步驟）：才是首次寫入 —— 開旗標 PR → 當天 dry-run → production-write → readback → 立即改回 `False` 的 PR。
  - **D｜單一 writer**：接受 read→append 非原子限制；只允許單一 workflow writer、`concurrency` 繼續作為保護；⛔ 不新增 distributed lock、⛔ 不新增第二 writer；未來若出現第二 writer ⇒ 重開 Decision Gate。
  - **E｜失敗政策 FAIL-STOP**：⛔ 禁止自動刪列、自動 rollback、自動覆寫、盲目 retry、為修漂亮改歷史。exit 4＝寫前檢查阻擋 ⇒ 維持原狀、當天不再重跑。exit 1／3／5 ⇒ 保留完整 logs／evidence、人工檢查 Sheet、停下等客戶裁示。若需刪除無效列：只能由客戶在 Google Sheets UI 人工執行、刪前保存證據／截圖；production 程式「永久不得」因此新增自動刪列功能。
  - **F｜Daily Schedule＝NOT APPROVED**：首次人工寫入與 daily schedule 是**兩個獨立 Gate**；⛔ 禁止新增 `schedule:`；排程設計、Environment 分流、unattended write 全部延後到首次人工寫入驗證完成後**另案裁示**。
- **總管推薦被否決（誠實紀錄）**：上一輪總管推薦的方案是「首寫先跳過 Environment」（理由：GitHub repo 為 public 個人帳號、main 無分支保護與 rulesets，唯一 reviewer＝觸發者，Environment 只是「刻意多按一次」）。客戶**正式否決**該推薦，改採 C（Environment＋WIF 強化為首寫前 MUST）。⛔ 後人不得引用總管舊推薦主張 Environment 可省略。
- **落地讀法**（撰寫組單組判讀，⚠️ 待第二組 evidence audit）：
  - 本條是 `VN1-STORE` production 寫入的**第一次客戶核准**，射程只到「**首次人工** production-write（`workflow_dispatch`、`main`）」，且以 C Step 1～3 全部完成為前提 —— 開旗標 PR 屬 Step 4，⛔ Step 3 完成前不得開立／合併。
  - 旗標 `True` 的期間只涵蓋「開旗標 PR 合併 → 首次寫入 → 改回 `False` 的 PR 合併」這一段；第二次寫入（含失敗後重試）不在 A 的射程內，須客戶另行裁示（E「停下等客戶裁示」）。
  - E 未個別點名 exit 2（閘門未過／紀錄檔不合格，什麼都沒寫）與 exit 0 以外的其他非預期中斷；撰寫組讀法：一律落在 E 總則（禁盲目 retry、保留證據、停下回報）—— 這是讀法、不是新裁示。
  - `RISK_CAP_HISTORY_WRITE_ENABLED: '1'` 在 workflow 寫入步驟寫死（盤點事實）；本條**未**要求改動，其架構是否調整登記為 backlog 候選（`docs/BACKLOG.md` 5.1.4），⛔ 不構成動工授權。
- **範圍**：credentials／account access（DEC-009）、資料保存（production 寫入）、資料歷史完整性｜**日期**：2026-10-20｜**決策者**：客戶｜**狀態**：生效（A～F 已裁示；⛔ 本條登記批**未**翻旗標、**未**加 `environment:`／`schedule:`、未改 IAM／WIF；下一 Gate＝C Step 1 客戶手動建立 Environment）
- **來源**：D 客戶訊息 2026-10-20（本 session；經總管轉交，**非逐字**；確切 UTC 時戳未記錄，只保留日期）。盤點事實：本 session 四組獨立唯讀稽核（總管彙整，撰寫組未重查；Environment 現存與否 UNKNOWN —— API 被代理擋；WIF 現行 condition repo 內無逐字原文）。
- **與其他 DEC 的關係**（撰寫組單組判讀，⚠️ 待第二組 evidence audit）：
  - **DEC-063**：本條就「production 寫入」開放**首次人工寫入**（有條件）；DEC-063 標題「未核准 production 排程寫入」的**排程**部分由本條 F 維持未核准。DEC-063 原文不改（append-only 狀態補註）。
  - **DEC-064**：G1／G2 身分設計不變；C Step 3 是收緊既有 provider 的 attribute condition，不換身分、不新增 key。
  - **DEC-065**：不影響（測試例外已執行完畢）。
  - **DEC-009**：Environment 由客戶手動建立；WIF provider 修改須以客戶提供的 describe 原文為準，AI 不建立、不修改任何 GCP／GitHub 設定資源（撰寫組讀法：修改的執行者客戶原文未逐字指明；依現況 AI 無 GCP 存取，預期由客戶手動執行）。
  - **DEC-003 ①**：畫面顯示歷史仍須先過線框；本條不涉 UI。
  - 規格 8.4「自動回滾（刪列）未經客戶核准 —— 需要的話須另行裁示」由本條 E **定案為永久禁止**；規格 8.9「每日排程 vs environment 人工核准（未送題）」由本條 F **裁示為延後、另案**。
- 📌 2026-10-21 狀態補註（append-only；撰寫組依總管轉述＋GitHub API 實查）：C **Step 1**（Environment）、**Step 2**（#894 wiring，`17e8ee44`）、**Step 3**（WIF hardening＋反向驗證）完成。Step 3：客戶以 `update-oidc` 只改 `--attribute-condition`（四條保留＋`environment=='production-risk-cap'`、`event_name=='workflow_dispatch'`；mapping 不變、ACTIVE）；反向驗證 run 39589906182 預期失敗。總管撤回「暫時讓 `wif_auth_only` 掛 environment 做正向驗證」建議、改採靜態比對＋反向驗證，客戶依此執行 —— **不是新 DEC**。⚠️ 正向換 token 未實測（首次正向驗證＝Step 4）。下一 Gate＝Step 4（尚未開始）；`PRODUCTION_WRITE_APPROVED` 仍 `False`；F 不變。本條原文不改
- 📌 2026-10-21 狀態補註二（append-only；Step 4 子步驟 1；**不是新 DEC**）：客戶 2026-10-21 核准開立 DEC-066 A 的**一次性旗標 PR** —— `shared/risk_cap_history_policy.py::PRODUCTION_WRITE_APPROVED` 由 `False` 改 `True`＋政策測試同步（拒絕路徑測試改以 monkeypatch 回 `False` 繼續覆蓋閘門）。⚠️ 本 PR 只翻旗標：**production-write 尚未執行**、⛔ 未加 `schedule:`、未改 workflow job 邏輯／WIF／IAM／Environment。⛔ 依 A：首次寫入嘗試後**不論結果**，下一個 PR 必須立即把旗標改回 `False`；改回前不得有第二次寫入嘗試。F 不變。本條原文不改
- 📌 2026-10-22 狀態補註三（append-only；Step 4 首次寫入 **Fail-Stop**；客戶裁示 B；**不是新 DEC**）：DEC-066 A 的一次性寫入窗口**關閉**。Fail-Stop 證據（run 39755679219，job 119746957010，main `e7e580c`，2026-10-22 17:28 台北 dry-run；總管轉述 Actions log）：`record_date`＝2026-10-22、`status`＝VALID、`exposure_limit_pct`＝30、`required_core_ok`＝TRUE、`missing_core`／`not_evaluated`／`refresh_failed` 空、`refresh_ok`＝TRUE、`git_sha`＝`e7e580c`；^TWII／MA5／Futures_Net_Short 皆用 2026-10-22（證據欄位＝record `input_asof`：Index_Below_MA5、BIAS240_pct、Futures_Net_Short＝2026-10-22；MA5 數值本身 log 未印）；30% 經正式 `calculate_system_state` 重算＝紅線三（外資期貨淨空 < −35,000 口 AND 加權指數跌破 MA5）；MA5 46,631.01、10-22 指數 46,041（低約 1.27%）——**重算值（非 log 直證）**：由獨立核對組以正式函式 `market_strategy.get_market_assessment` 重算，視窗收盤 10-16 47111.26／10-19 46822.08／10-20 46292.93／10-21 46887.77（取自 `data_cache/twii_ohlcv.parquet`）＋10-22 46041（取自 log `[Bias] price=46041`，該行為 2y yfinance 抓取，非 mkt_info 那次抓取）。前兩次 dry-run：39608164307（10-21，80%）；39695843255（10-22 07:50，30%，^TWII 少 10-21 一根、MA5@10-20 配期貨@10-21 跨日配對，客戶不接受）。**未通過原因**：(1) VIX 18.4 標 2026-10-22，但 17:28 台北美股尚未開盤 ⇒ 為盤前／未收盤暫定日線，現行 freshness 無法區分；(2) log 未留 Futures_Net_Short 實際口數、MA5 判定、veto_flags，只能由正式函式＋區間反推確認。 ⛔ production-write **從未執行**；System Risk Cap Sheet **沒有首筆正式紀錄**。依 A，關窗 PR 將 `PRODUCTION_WRITE_APPROVED` 改回 `False`（政策測試同步改回）；⛔ 未改 `.github/`／`scripts/`／`src/`、公式、門檻、VALID 定義、資料來源、freshness、WIF／IAM／Environment。下次重開：須先修正並驗證資料時點問題（BACKLOG `VN1-PG-VIX-ASOF`／`VN1-PG-VETO-TRACE`／`VN1-PG-PIT-CONSISTENCY`），再走**新的**旗標 Gate（新 PR 開旗標＋同日 dry-run 等）；本補註不構成重開授權。F（Daily Schedule NOT APPROVED）不變。前兩條補註原文不改
- 📌 2026-10-22 狀態補註四（append-only；**不是新的重開授權**）：補註三所列三項 MUST 的**資料語意**已由 **DEC-070** 裁示（盤後版、同一錨定交易日 D、VIX 只用已完成收盤資料、^TWII 缺棒 Fail-Stop）；三項仍**未實作**。重開條件不變：實作＋驗證 → 新的旗標 Gate。前三條補註原文不改


### DEC-067｜Handoff Save Check 與跨對話 SSOT（客戶 2026-10-22 頒布）
- **來源**：客戶 2026-10-22 新增正式治理規則（經總管轉交，撰寫組未見原件）。
- **內容**：GitHub 為跨 ChatGPT／Claude Code／新舊對話的共同 SSOT；對話結束前執行 Handoff Save Check、新對話開始先校正 GitHub 實況；不大量保存聊天紀錄或未裁示想法。全文見 `PROJECT_RULES.md` 第 15 節（本條不複製規則）。
- 📌 2026-10-22 狀態補註（append-only）：本條由 **DEC-068** 擴充（五檔分工、`docs/PROJECT_STATE.md`、Handoff Save Check 第五項、Context Loss Check、啟動優先序加 PROJECT_STATE 一層）；本條原文不改、不被取代，兩條併讀。

### DEC-068｜GitHub＝跨 AI 長期專案記憶 SSOT；五檔分工；新增 `docs/PROJECT_STATE.md`；Context Loss Check（客戶 2026-10-22）
> 2026-10-22 追加（第 8 節「收到當輪追加」；ID 照序取下一個未用號，撰寫組 `git grep -oh "DEC-0[0-9]*" | sort -u` 實測最大為 DEC-067）。BACKLOG 登記：DR-2026-10-22-1。
- **內容**（引號內為客戶原文逐字；規則全文見 `PROJECT_RULES.md` 第 0.3 節、第 15 節，本條不複製規則）：
  1. 「客戶已正式裁示：採用「GitHub = 跨 AI 長期專案記憶 SSOT」架構。」
  2. 五檔分工：`PROJECT_RULES.md`＝永久治理規則、AI 工作方式、禁止事項、驗證規則；`docs/DECISIONS.md`＝客戶已正式裁示的決策與必要 rationale；`docs/BACKLOG.md`＝所有未完成工作的唯一 SSOT；`docs/HANDOFF.md`＝短版交接（只保存 current active work、blocker、next safe point、必要的 main／PR／CI 狀態），「不再把它當完整專案記憶」；新增 `docs/PROJECT_STATE.md`＝「ChatGPT + Claude 共用的「目前仍然有效」完整專案狀態」。「不要再新增 PROJECT_CONTEXT.md，避免與 PROJECT_STATE 重疊。」
  3. PROJECT_STATE 原則：「保存專案知識，不保存聊天紀錄。」不得成為第二份 BACKLOG／HANDOFF、複製完整聊天紀錄、保存 secret／credential／private key、把 Candidate 寫成 Approved、把推測寫成 GitHub factual truth、取代 DECISIONS、保存已失效的流水帳。
  4. 跨 AI 啟動：fetch → 讀五檔 → 驗證 main SHA／open／draft PR／relevant commits／diffs／CI／QA／relevant branches；「GitHub factual reality > HANDOFF > PROJECT_STATE 中的狀態快照 > AI memory / conversation summary。」不一致時以 GitHub evidence 為準、不得猜測、必要時修正正式文件。「與現有 §15 / DEC-067 整合，不建立競爭規則」。
  5. Handoff Save Check 加第五項：「仍有效的完整專案狀態、架構關係、重要背景與限制 → PROJECT_STATE」。
  6. Context Loss Check A～E；「任何答案為「有」且尚未保存時：不得宣告交接完成。」
- **範圍**：治理（交接、跨對話 SSOT）｜**日期**：2026-10-22｜**決策者**：客戶｜**狀態**：生效
- **來源**：D 客戶訊息 2026-10-22T14:43Z（本 session；本檔首次入庫）。
- **與其他 DEC 的關係**：擴充 DEC-067（不取代）；DEC-056 第 4 點的四檔責任（Blueprint／BACKLOG／DECISIONS／HANDOFF）不受影響，PROJECT_STATE 不承載 Blueprint 的方向本文。⛔ 本條不是任何功能工作的動工授權（`CLAUDE.md` §-1）。

### DEC-069｜客戶回報語言：一律繁體中文（客戶 2026-10-22）
> 2026-10-22 追加（第 8 節；本條原為聊天裁示，於 DEC-068 Context Loss Check 盤點時補入庫）。BACKLOG 登記：DR-2026-10-22-2。
- **內容**（客戶原文逐字）：「從現在起所有客戶回報一律使用繁體中文；除程式碼、正式欄位名稱、log 原文外，不得改用英文。」規則落點：`PROJECT_RULES.md` 第 3 節。
- **範圍**：治理（回報格式）｜**日期**：2026-10-22｜**決策者**：客戶｜**狀態**：生效
- **來源**：D 客戶訊息 2026-10-22T00:18Z（本 session；本檔首次入庫）。
- **與其他 DEC 的關係**：與 DEC-060（回報格式）併用、不取代；只規範對客戶的回報語言，不規範產品畫面文案。

### DEC-070｜Risk Cap 每日代表時點採「盤後版」語意；Yahoo 缺 ^TWII 必要 K 棒 → Fail-Stop；授權 docs-only Context Loss Check 落盤（客戶 2026-10-22）
> 2026-10-22 追加（第 8 節「收到當輪追加」；ID 照序取下一個未用號，撰寫組 `git grep -oh "DEC-0[0-9]*" -- docs/DECISIONS.md | sort -u` 實測最大為 DEC-069）。BACKLOG 登記：DR-2026-10-22-3。
- **背景**（裁示前總管送出的題目；**非客戶原文**，撰寫組依總管轉交整理）：DEC-066 Step 4 dry-run Fail-Stop（DEC-066 狀態補註三）後，總管研究 `VN1-PG-VIX-ASOF`／`VN1-PG-VETO-TRACE`／`VN1-PG-PIT-CONSISTENCY` 並送兩題：
  - **Q1**｜每日風險上限代表哪個時點：A 盤後版（錨定台股交易日 D 收盤後；台股輸入取 D；VIX 取美東日期早於 D 的最後一根＝前一個已收盤美股交易日；PMI 資料月規則不變；總管原推薦截止台北 16:00）vs B 盤前版。
  - **Q2**｜Yahoo 缺 ^TWII K 棒：A 先 Fail-Stop 明示 vs B 評估證交所官方加權指數（新來源）。
- **內容**（客戶原文**逐字節錄**（裁示部分）；經總管轉交；總管 2026-10-22 已比對客戶原件、確認下列區塊與原件逐字一致（總管轉述，撰寫組未見原件））：

```
裁示如下：

1. Q1 採 A「盤後版」方向。
   
   - 台股輸入以同一錨定交易日 D 為原則。
   - 外資期貨與 MA5 必須屬於同一個台股交易日。
   - VIX 只能使用在該判斷時點已完成收盤、且不造成 look-ahead 的資料。
   - PMI 維持既有資料月規則。
   - 但「台北 16:00」目前不要直接升格為永久正式規則：你目前對期交所資料發布時間只有二手證據。先將「盤後且 D 日必要台股資料均已正式可得」定為正式語意；16:00 可列保守執行時間／Candidate，待官方來源驗證後再決定是否固化。

2. Q2 採 A：
   Yahoo 缺 ^TWII 必要 K 棒時 Fail-Stop／無法評估並明示；不得以前一交易日偷偷頂替，也暫不新增或替換正式資料來源。先累積缺棒頻率與證據，再決定是否研究證交所官方來源。

3. 授權開一個 docs-only PR 做 Context Loss Check 落盤。
   請依 PROJECT_RULES §15 分類，而不是只更新 PROJECT_STATE＋BACKLOG：
   
   - DECISIONS：記錄本次正式裁示；
   - BACKLOG：保留未完成驗證／研究／實作項；
   - PROJECT_STATE：保存仍有效的技術研究結論，並更正舊「互鎖」描述；
   - HANDOFF：若 current/blocker/next safe point 因本裁示改變則同步；
   - PROJECT_RULES：除非治理規則本身真的需要變更，否則不要修改。

本批仍只允許文件落盤，不授權 Risk Cap 核心語意實作、不開 production-write、不開 schedule、不新增資料來源。

外部證據不足的部分必須明確標示 Candidate／未驗證，不得寫成已證實事實。
```

  > 註：以上為裁示部分逐字節錄；原訊息其後另有流程指示（完成後回報方式、模型／模式／Effort 設定），屬流程、非裁示內容，未收錄。

- **裁示要點**（撰寫組整理；與上方原文不一致時以原文為準）：
  1. **Q1＝A「盤後版」方向**：(a) 台股輸入以同一錨定交易日 D 為原則；(b) 外資期貨與 MA5 必須屬於同一個台股交易日；(c) VIX 只能使用在該判斷時點已完成收盤、且不造成 look-ahead 的資料；(d) PMI 維持既有資料月規則；(e) **正式語意**＝「盤後且 D 日必要台股資料均已正式可得」。
  2. **「台北 16:00」不升格為永久正式規則** —— 只列「保守執行時間／Candidate」，待官方來源驗證後再決定是否固化（客戶理由原文：「你目前對期交所資料發布時間只有二手證據」）。
  3. **Q2＝A**：Yahoo 缺 ^TWII 必要 K 棒 → Fail-Stop／無法評估並明示；⛔ 不得以前一交易日偷偷頂替；暫不新增或替換正式資料來源；先累積缺棒頻率與證據，再決定是否研究證交所官方來源。
  4. **第 3 點**（客戶原文編號「3.」；背景所稱 Q1／Q2 為總管題號，本點無題號）：授權**一個** docs-only PR 做 Context Loss Check 落盤，依 `PROJECT_RULES.md` §15 五類分類。撰寫組判定（單組）：本裁示**不涉治理規則本身的變更** ⇒ `PROJECT_RULES.md` 本批**未改**。
- **總管推薦 vs 客戶裁示的界線（必讀；撰寫組讀法，單組）**：
  - **VIX 選值方式**：Q1 背景裡的「取美東日期早於 D 的最後一根」是**總管推薦的候選實作方式**，客戶**沒有逐字核准**這條具體規則。客戶核准的是語意（要點 1(c)）。該實作屬「符合該語意的一種實作」，由實作批定案（技術實作面屬內部拍板，`CLAUDE.md` §-1.5.A-4），且仍須驗證；⛔ 後人不得把它引用為客戶裁示。
  - **16:00**：只能寫「保守執行時間／Candidate」（要點 2），⛔ 不得寫成正式 cutoff。
- **不是什麼**（⛔）：
  - 不是實作授權（客戶原文「不授權 Risk Cap 核心語意實作」）；三項實作仍須客戶指派實作批（DEC-006、DEC-015）。
  - 未固化台北 16:00；未定任何 cutoff 時刻。
  - 未核准新資料來源（含證交所官方加權指數；新增／替換 production 來源屬 Decision Gate，`PROJECT_RULES.md` §4 #3）。
  - 未開 production-write、未開 schedule；`PRODUCTION_WRITE_APPROVED` 仍為 `False`；Daily Schedule 仍 NOT APPROVED（DEC-066 F）。
  - 未改 Risk Cap 公式、門檻、VALID 定義；未改 Required Core（DEC-048）。
  - 未定 `published_at`／`available_at` 欄位契約（本條只定語意）。
  - 不是重開旗標的授權：重開仍須三項**實作＋驗證**，再走**新的**旗標 Gate（DEC-066 狀態補註三）。
- **範圍**：資料語意（`PROJECT_RULES.md` §4 #2）；治理（docs-only 落盤授權）｜**日期**：2026-10-22｜**決策者**：客戶｜**狀態**：生效（語意已裁示；⛔ 未實作）
- **來源**：D 客戶訊息 2026-10-22（本 session；本檔首次入庫；經總管轉交；確切 UTC 時戳未記錄，只保留日期）。
- **與其他 DEC 的關係**（撰寫組讀法，單組，⚠️ 待第二組 evidence audit）：
  - **DEC-028**（觀測日＝真正所屬交易日）：同向；本條把它推進到跨輸入（同一錨定交易日 D）。
  - **DEC-029**（日頻落後 >3 交易日＝未評估）：**不變、不取代**；本條另加「跨輸入日期一致性」與「VIX 須已完成收盤」兩項要求，兩者併用（通過 freshness ≠ 通過本條）。
  - **DEC-039**（No look-ahead）：本條是其在每日 Risk Cap 時點上的具體化。
  - **DEC-048**（Required Core 無法評估 → 不產生新上限、可沿用 7 天內有效快照）：Q2 的 Fail-Stop 落在這條既有路徑上（^TWII 缺棒 ⇒ MA5 無法評估 ⇒ Required Core 不完整），本條**不新增**沿用規則。沿用 7 天內快照時**必須明示**是沿用；這與「不得以前一交易日 K 棒偷偷頂替」是**兩件事** —— 前者是 DEC-048 對整份上限快照的既有沿用路徑，後者是單一輸入的頂替，被本條 Q2 禁止。
  - **DEC-066**（狀態補註三列的三項 MUST）：本條裁示其中的**語意部分**；重開旗標仍須實作＋驗證＋新的旗標 Gate。
  - **`CV1-RC-01`**（Conservative Safe Effective Cutoff 原為候選）：本條把「盤後且 D 日必要台股資料均已正式可得」定為**正式語意**；**具體 cutoff 時刻仍是 Candidate**（BACKLOG `VN1-PG-CUTOFF-VERIFY`）。`CV1-RC-01` 其餘候選內容不受影響。

### DEC-071｜新 UI 方向確認：視覺方向維持、舊 UI 功能為重要參考、主頁以「大盤／市場趨勢」為核心、導航後續改名（候選非 final）、研究兩主軸台股趨勢／國際趨勢、保留「大盤」字樣（客戶 2026-10-22）
> 2026-10-22 追加（第 8 節「收到當輪追加」；ID 照序取下一個未用號，撰寫組 `git grep -n "DEC-071"` 實測 0 命中、最大為 DEC-070）。BACKLOG 登記：DR-2026-10-22-4；落點 `docs/BACKLOG.md` 5.1.6（`VN1-MT-*`）。
- **內容**（客戶【客戶已確認】六點，原文逐字；經總管轉交；總管已逐字比對客戶訊息（撰寫組未見原件））：

```
1. 新 UI 的視覺設計方向維持。
2. 舊 UI 的既有功能與判讀邏輯是新版的重要參考，不應因新版簡化而大量刪除。
3. 第一個主頁不要再以「今天」為核心，應以「大盤／市場趨勢」為核心。
4. 原「今天／找標的／我的持股／我的」導航名稱後續重新命名；目前候選名稱不是 final。
5. 市場趨勢研究只保留兩個主軸：台股趨勢、國際趨勢
6. 「大盤」必須明確保留，不能只留下「趨勢」兩字。
```

- **研究框架指標**：客戶同輪另提供蕭碧燕老師資料（只保存研究框架），保存於 `docs/PROJECT_STATE.md` §22，屬 **Research Framework，非 Approved**；⛔ 不是本條內容、不是 Decision。客戶同輪另要求（客戶原文逐字）：「以上屬 Research Framework；除非 repo 已有正式 Decision，否則不得寫成 Approved production rule。」「不要建立新的綜合分數。」「尤其不要把：「市場位階」「指標危險度」「Risk Cap」「台股趨勢」四者合併成同一概念。」—— 落點同上 §22.2／§22.3、BACKLOG `VN1-MT-TREND-DEF`。
- **範圍**：產品方向／UI 資訊架構（方向確認）｜**日期**：2026-10-22｜**決策者**：客戶｜**狀態**：生效（方向已確認；⛔ 未實作、⛔ 線框未送審）
- **來源**：D 客戶訊息 2026-10-22（本 session；本檔首次入庫；經總管轉交；確切 UTC 時戳未記錄，只保留日期）。
- **不是什麼**（⛔；撰寫組依既有 DEC 讀法）：
  - 不是動工授權（`CLAUDE.md` §-1；DEC-002、DEC-015）。
  - 不取代 DEC-003 線框 gate：主頁核心、導航名稱、大盤頁版面的任何變動，都須先出文字線框送客戶拍板才寫 UI code。
  - 不授權修改或刪除舊 UI（DEC-019、DEC-020 不變）；第 2 點是「新版要參考舊 UI」，不是「改舊 UI」，也不是「把舊功能接回新版」的施工授權。
  - 不定義「台股趨勢」「國際趨勢」（GitHub 無定義來源，`docs/PROJECT_STATE.md` §20）；不核准任何新資料源、公式、門檻或綜合分數。
  - 第 4 點的新名稱未定；本條未核准任何一組導航名稱。
- **與其他 DEC 的關係**（撰寫組讀法，單組，⚠️ 待第二組 evidence audit）：
  - **DEC-017**（IA v2 五頁：現行 `shared/ia_nav.py::PAGE_LABELS`＝🚦今天／🔍找標的／🔬查一檔／💼我的持股／📖憑什麼）與 **DEC-062 Q1**（四格「今天／機會／持股／我的」為**線框送審範圍**，線框本身未送審；`BP-DR-01`）：客戶第 4 點所稱「今天／找標的／我的持股／我的」**與兩套都不完全相同**（「找標的」「我的持股」見於 DEC-017 五頁；「我的」見於 DEC-062 四格；「今天」兩套皆有）。撰寫組**不判定**客戶指哪一套 → BACKLOG `VN1-MT-NAV`（Decision Gate）。DEC-017 現行五頁在新名稱經線框拍板前照舊。
  - **DEC-057**（引客戶原則「首頁不是 Dashboard。」「不要為了讓首頁有內容而製造 Action。」）與 **DEC-062 Q1**（「今天頁」列入 1.0 線框送審範圍）：第 3 點「主頁以「大盤／市場趨勢」為核心」與之**存在需要釐清的張力**（大盤／趨勢為核心的主頁是否落入「Dashboard」；DEC-062 Q1 的今天頁是否改為大盤頁、併入或並存）。⛔ 本條**不解決**此張力 → BACKLOG `VN1-MT-HOME`（Decision Gate）。撰寫組建議（非規則、非客戶裁示）：此題裁示前，`1.0-B4` 線框的今天頁／主頁部分先不定稿送審。
  - **DEC-003**（UI 草稿先行）：不變，見上「不是什麼」。
  - **DEC-019**（New UI 唯一主線、舊 UI 凍結）、**DEC-020**（不提前刪舊 UI；實體刪除屬重大不可逆）：不變。
  - **DEC-023**（加權指數只畫走勢、不算一盞燈）：不變；第 6 點「保留「大盤」字樣」不是新增一盞燈或新評分。
  - **DEC-056／DEC-057**（產品方向與 Blueprint）：第 1 點「視覺設計方向維持」撰寫組讀為維持新 UI 現行視覺方向，**不是**核准任何線框（Blueprint 線框與 `BP-DR-*` 狀態不變）。
  - **DEC-009**（Context → Core／hard veto 須客戶裁示）：研究框架任何項目若要變成正式判斷依據，仍走此 Gate。

### DEC-072｜產品方向：「底層能力完整，前台流程極簡」；投資主流程暫定 📊 大盤／🎯 標的／⚡ 行動／🛡️ 持股，輔助入口 👤 我的／🩺 資料中心（客戶 2026-10-23）
> 2026-10-23 追加（第 8 節「收到當輪追加」；ID 照序取下一個未用號，撰寫組寫入前 `git grep -n "DEC-072"` 實測 0 命中、最大為 DEC-071）。BACKLOG 登記：DR-2026-10-23-1；受影響列 `VN1-MT-NAV`、`VN1-MT-HOME`、`BP-DR-01`（5.1.6／5.1.2 📌 註）；資料中心與全站狀態列見 5.1.7 `DH-DATA-CENTER`。
- **內容**（客戶原文；經總管轉交，撰寫組未見原件，依總管轉交文字逐字收錄）：

```
目前方向是「底層能力完整，前台流程極簡」。
投資主流程暫定：
1. 📊 大盤 — 回答：現在適合承擔多少風險？台股趨勢、國際趨勢、Risk Cap、重要警示；首屏先給結論與少數關鍵原因，詳細指標 progressive disclosure。
2. 🎯 標的 — 回答：現在有哪些值得看的？「找標的＋查一檔」整合為同一主頁。點選標的後直接進同一流程的詳細健檢，不另設「查一檔」主導航。個股／ETF 的財報、技術、籌碼、估值等底層能力保留，但不要製造大量頁面層級。
3. ⚡ 行動 — 回答：現在有什麼需要處理？僅盤點既有 deterministic action 能力。不新增未核准的買賣語意、加減碼比例或新投資規則。
4. 🛡️ 持股 — 回答：我的投資組合健康嗎？持股健檢、曝險、集中度、風險、壓測等。
輔助入口：👤 我的：帳戶／設定等 utility。🩺 資料中心：資料維護與健康狀態，不屬於主要投資流程。「憑什麼」原則上轉為各頁 contextual explainability／資料來源／判斷依據，不作主要導航。
以上目前是產品方向整理；若與既有 DECISION 衝突，請 append-only 記錄 supersession / relationship，不得直接覆寫歷史裁示。
```

  客戶同輪另述（經總管轉交）：主 UI 未來只需要非常簡單的全站狀態，例如「🩺 資料健康：🟡｜3 項需處理」，點擊後才進資料中心。（規格草案見 `docs/vnext/DATA_HEALTH_AUDIT_2026-10-23.md` 第 7 節；⛔ 草案、未實作。）
- **範圍**：產品方向／UI 資訊架構｜**日期**：2026-10-23｜**決策者**：客戶｜**狀態**：生效（產品方向，暫定）；⛔ 未核准線框、⛔ 非動工授權
- **來源**：D 客戶訊息 2026-10-23（本 session；本檔首次入庫；經總管轉交；確切 UTC 時戳未記錄，只保留日期）。
- **不是什麼**（⛔；撰寫組依既有 DEC 讀法）：
  - 不是動工授權（`CLAUDE.md` §-1；DEC-002、DEC-015）；客戶自述「以上目前是產品方向整理」。
  - 不是線框核准：導航、主頁、頁面合併（「找標的＋查一檔」整合）、資料中心與全站狀態列的任何畫面變動，都須先出文字線框送客戶拍板才寫 UI code（DEC-003 ①）。
  - 不定義「台股趨勢」「國際趨勢」（`VN1-MT-TREND-DEF` 不變）；⛔ 不得把「市場位階」「指標危險度」「Risk Cap」「台股趨勢」合併（DEC-071 同輪客戶原文；第 1 點同列四者不代表合併）。
  - 第 3 點不核准任何新的買賣語意、加減碼比例或投資規則（客戶原文）；DEC-053、DEC-054 的護欄不變。
- **與其他 DEC 的關係**（append-only；撰寫組讀法，單組，⚠️ 待第二組 evidence audit；⛔ 客戶原文未用「取代」一詞，本條一律寫「關係／待線框確認」，不寫取代）：
  - **DEC-017**（IA v2 五頁：🚦今天／🔍找標的／🔬查一檔／💼我的持股／📖憑什麼）：**仍為現行實作依據**，直到依本方向的新線框經 DEC-003 拍板。本方向與五頁的對照（撰寫組讀法）：「找標的＋查一檔」→ 🎯 標的；「憑什麼」→ 各頁 contextual explainability，不作主要導航；「今天」→ 主頁改 📊 大盤（DEC-071 第 3 點）；⚡ 行動、🩺 資料中心為五頁所無。對照只供線框參考，⛔ 拍板前不改 `shared/ia_nav.py::PAGE_LABELS`。
  - **DEC-018**（雙軌入口：舊 7 頁籤第一排、新版由側邊欄進入）：不變；本方向只講新版內部的頁面結構，未涉入口切換（DEC-020）。
  - **DEC-057**（引客戶原則「首頁不是 Dashboard。」「不要為了讓首頁有內容而製造 Action。」）：張力見 DEC-071 與 `VN1-MT-HOME`。本方向第 1 點以「首屏先給結論與少數關鍵原因，詳細指標 progressive disclosure」為大盤頁首屏，撰寫組讀為與「首頁不是 Dashboard」同向的處理方式；⛔ 本條**不**宣告 `VN1-MT-HOME` 已解決，待線框拍板確認。
  - **DEC-062 Q1**（四格「今天／機會／持股／我的」為 1.0 線框**送審範圍**，線框未送審；`BP-DR-01`）：本方向的主流程為「大盤／標的／行動／持股」＋輔助「我的／資料中心」，與四格**不相同**（「今天」→「大盤」、「機會」→「標的」、新增「行動」「資料中心」）。關係＝**送審範圍待依新方向調整**；DEC-062 Q1 原條不刪、不改。
  - **DEC-071**：本方向是其第 3 點（主頁以「大盤／市場趨勢」為核心）與第 4 點（導航後續重新命名）的具體化；第 6 點「大盤」字樣保留，本方向首頁名稱即「📊 大盤」，同向。名稱仍為**暫定**（客戶原文「暫定」），與 `docs/PROJECT_STATE.md` §23.2 盤點時的候選「📊 大盤趨勢／🎯 標的雷達／⚡ 交易行動／🛡️ 持股防護」措辭不同，以本條客戶用詞為較新方向；⛔ 仍非 final 名稱裁示。
  - **DEC-019／DEC-020**（New UI 唯一主線、舊 UI 凍結；不提前刪舊 UI）：不變；本方向不授權改或刪舊 UI。
  - **DEC-003**（UI 草稿先行）：不變，見上「不是什麼」。
  - 相關（總管指示未列，撰寫組補）：第 3 點「僅盤點既有 deterministic action 能力」與 DEC-053（正式加減碼比例須先經驗證流程）、DEC-054（有證據、受風險護欄約束的方向性 Action）、`CV1-FU-03`（七種 Action 是否封閉清單）同向，⛔ 不擴大 Action 範圍；全站狀態列「最差燈＋N 項」與 DEC-062 Q5（最差燈＋N/M 揭露）同向；「憑什麼」轉為 contextual explainability 與 `BP-DR-01` 原建議「「憑什麼」改為每個結論上的「為什麼？」」同向。


## 3. 資料語意（data semantics）

### DEC-026｜Missing ≠ 0：未觀測→缺值、真實 0→0、有效值→原值；不得 fillna(0) 或自估合理值
- **範圍**：資料語意｜**日期**：`CLAUDE.md` §1（2026-06-22 起）；2026-10-10～11 Q-z15／Q-z20／Q-z21／Q-z26｜**決策者**：user／客戶｜**狀態**：生效
- **來源**：A `CLAUDE.md@f0a6c474:1104`「凌駕一切的鐵律。錯誤的數字比沒有數字更危險。」及其下禁止 `fillna(0)`。C `H:674`「外資淨額「未觀測」時，必須當作缺值，不得視為「有資料且等於 0」。」；`H:896`「必須區分：未取得／未觀測 → 缺值；真實 0 → 0；有效正負值 → 原值。」。B #822 `0ef68f93`、#823 `0dc8518e`、#824 `43b83a3a`、#826 `f8731edb`。

### DEC-027｜資料層 ≠ AI 分析層；AI 不得生成客觀資料、不得推測缺值
- **內容**：資料層只負責取得、驗證、標準化與缺值狀態；AI 只讀已驗證資料；AI 不得創造客觀資料、猜缺值、補 0、自成 primary data source、把推論寫回客觀資料、偷改公式／權重／rule。
- **範圍**：資料語意／AI｜**日期**：2026-10-11；2026-10-13 重申；2026-10-15｜**決策者**：客戶｜**狀態**：生效
- **來源**：C `H:901`「7. 資料／AI 分層維持不變 資料層只負責取得、驗證、標準化與缺值狀態。AI 分析層只能讀取已驗證資料。不得由 AI 推測缺少的 TPEx 數字。」；`H:1021`。D 客戶訊息 2026-10-15T13:40Z（本 session；本檔首次入庫）§8「永久維持：/ Data Layer 與 AI Analysis Layer 分離」；同節「AI不得：/ - 創造客觀資料」。A 旁證 `CLAUDE.md@f0a6c474:1165`「Gemini API（synthesis only）」。

### DEC-028｜觀測日＝該筆市場觀測真正所屬交易日；恢復歷史須逐筆 provenance、不得猜值
- **範圍**：資料語意｜**日期**：2026-10-15｜**決策者**：客戶｜**狀態**：生效（已實作）
- **來源**：D 客戶訊息 2026-10-15T13:53Z（本 session；本檔首次入庫）「不得單純把 "datetime.now()" 換成另一個任意時間。日期必須代表該筆市場觀測真正所屬交易日。」；「必須逐筆確認 provenance / observation date；不得猜值或自行補資料。」。B #853 `0d063d7f`。

### DEC-029｜Freshness policy（Q-z36／Q-z37／Q-z38）：做成資料層／共用層 SSOT
- **內容**：日頻落後超過 3 個交易日＝未評估／已過期；月頻最多落後一個正常發布期、不寫死 30 天；cache 存活 ≠ 資料新鮮；UI 只如實呈現；不得自創 freshness 天數；既有可追溯、有日期且在核准有效期內的 cached／fallback 不視為捏造。
- **範圍**：資料語意／架構｜**日期**：2026-10-14｜**決策者**：客戶｜**狀態**：生效
- **來源**：C `H:1532`「架構要求（客戶原話）：「把這次核准的 freshness policy 做成資料層／共用層的單一規則來源，不要把 3 天、發布期判斷散落硬編」；`H:1516` 自註其餘為**總管逐條轉述、非逐字**。B #848～#851（F1～F4）。

### DEC-030｜PMI「連兩月」須用兩個不同資料月份（Q-z34＝B）
- **內容**：前月取 PMI 歷史前一資料月官方值；取不到＝該紅線無法判定；門檻 48、上限 40% 不變。
- **範圍**：公式／資料語意｜**日期**：2026-10-14｜**決策者**：客戶｜**狀態**：生效
- **來源**：C `H:1477`「PMI「連兩月低於 48」必須使用兩個不同資料月份。」。B #850 `2460d6fa`。

### DEC-031｜數值異常（NaN／±inf／無效值）不顯示、不用替代值續算；統一文案
- **範圍**：資料語意／UI 文案｜**日期**：2026-10-13｜**決策者**：客戶｜**狀態**：生效
- **來源**：C `H:1125`「「{項目}資料異常，無法計算，不下結論。」」；`H:1074`。B #836 `8ddc8b37`、#835 `18b51ea0`。
- 📌 **2026-10-28 補註（append-only；原文不改）**：部分語意已由 DEC-101(2) 取代（2026-10-28 客戶）—— 本條「異常不顯示、不續算」原則不變；被取代的只有同期實作批 Z51（#838）／Z52（#839）測試所釘「缺值／部分失敗時 AI prompt 與修前逐字相同、仍帶『續抱、定期定額即可』指示」那一部分（有意識的更新，不是漏刪，決策者 客戶；DEC-101）。⚠️ Z51／Z52 與本條的對應為撰寫組判讀（Z51／Z52 程式註解自陳「客戶 2026-10-13 裁示」「沿用批 Z49／Z50 的處置」），單組。

### DEC-032｜等於門檻歸較差側（外資 −30,000 等於門檻歸「防禦」）
- **範圍**：公式（邊界）｜**日期**：2026-10-09（Q-r10b＝A）｜**決策者**：客戶｜**狀態**：生效（「Q-r9d」本身的原文撰寫組未查到；本條依 Q-r10b 原文所述的通則）
- **來源**：C `H:2317-2318`「-30,000 等於門檻時統一歸「防禦」。/ 依既有 Q-r9d「等於門檻歸較差側」原則，全站相關判定統一，不另創規則。」。（原列的 #816 `a6465696` 實作的是 Q-z4～Q-z7 的 −2 萬／−1 萬口，**不是本裁示的實作**，已移除；本裁示的實作 commit 撰寫組未查到。）

### DEC-033｜上市／上櫃法人口徑統一為官方口徑（Q-z24＝A'、Q-z25＝A）
- **內容**：外資不含外資自營商；自營商＝自行買賣＋避險；上市與上櫃口徑一致。
- **範圍**：資料語意｜**日期**：2026-10-11｜**決策者**：客戶｜**狀態**：生效
- **來源**：B `f0a32a3b`（#827）「批 Z40：法人口徑統一為官方口徑（客戶 Q-z24 A'／Q-z25 A）」。C `H:891` 起〈Q-z24～Q-z28 裁示〉。

### DEC-034｜上櫃（TPEx）改接官方新 JSON：受控遷移（Q-z27＝A）
- **內容**：先 Probe 驗證官方來源、歷史日期、欄位，通過才切換。
- **範圍**：資料來源（替換 production source）｜**日期**：2026-10-11｜**決策者**：客戶｜**狀態**：生效（已實作）
- **來源**：B `9c09df3e`（#828）「上櫃（TPEx）法人與收盤改接官方新網站 JSON＋板塊資金自動回補上櫃（客戶 Q-z27 A 受控遷移）」。

### DEC-035｜官方只缺外資時不跨來源拼 FinMind；誠實顯示「未取得」＋核准語句（2026-10-12 Q2＝A、Q3＝B）
- **範圍**：資料來源／UI 文案｜**日期**：2026-10-12｜**決策者**：客戶｜**狀態**：生效
- **來源**：C `H:965-967`「2. Q2：A / - 維持現行來源策略。/ - 官方只缺外資時，不跨來源拼 FinMind。」。B `a7626e9e`（#831）「籌碼卡外資未取得說明改用既有核准語句（客戶 Q3＝B）」。

### DEC-036｜產業板塊名稱標準化在標準化／呈現層完成，資料層保留原始名稱與來源（Q-z29＝A）
- **範圍**：資料語意｜**日期**：2026-10-12｜**決策者**：客戶｜**狀態**：生效
- **來源**：C `H:927`「Q-z29 裁示：選 A。1. 「金融業」（上櫃）合併至「金融保險」。2. 上市 ETF 與上櫃 ETF 合併為同一個 ETF 泡泡。」。B `de79147f`（#830）。

### DEC-037｜M1B 代理值只顯示不計分；裁決設有效期限
- **範圍**：資料語意｜**日期**：2026-10-02｜**決策者**：客戶｜**狀態**：生效（有效期限具體值撰寫組未查）
- **來源**：C `H:2267`「③ M1B 代理值：只顯示不計分；裁決設有效期限」。B `ac56733`（#779）。

### DEC-038｜資料層修錯授權限三類（失敗不快取／缺值不填 0／擋非有限值），逐件不用問、不擴大
- **範圍**：治理＋資料｜**日期**：2026-10-02｜**決策者**：客戶｜**狀態**：生效；與 DEC-008（2026-10-10 Level 1 bug 可修）的範圍關係未明示 → `CV1-DR-09`
- **來源**：C `H:2266`「② 資料層修錯授權：照做，限三類（失敗不快取／缺值不填 0／擋非有限值），逐件不用問；⛔ 不擴大」。

### DEC-039｜No Look-ahead（P0）：歷史決策不能看到當時尚未公開的資料
- **內容**：FRED 用 release_date、禁止用 observation_date 回填；季報用公告日；校準歷史驗算禁止 lookahead；不建 Perfect PIT Database。
- **範圍**：資料語意｜**日期**：`CLAUDE.md` §2.3 既有；2026-10-15｜**決策者**：客戶（通則，MSG 1 §9）；⚠️ FRED release_date、季報公告日等**細則**出自 `CLAUDE.md` §0 Bootstrap 由 AI 依 code 證據填寫的 §2.3（**AI 總管內部**，非客戶逐條裁示）｜**狀態**：生效（Live／Historical 分離與 Conservative Safe Effective Cutoff 僅為候選，不升格 → `CV1-RC-01`）
- 📌 2026-10-22 狀態補註（append-only；本條原文不改）：每日 Risk Cap 的時點語意已由 **DEC-070** 裁示（「盤後且 D 日必要台股資料均已正式可得」；VIX 只用判斷時點已完成收盤的資料）；上句「Conservative Safe Effective Cutoff 僅為候選」中的**具體 cutoff 時刻**仍是候選（台北 16:00＝Candidate，BACKLOG `VN1-PG-CUTOFF-VERIFY`）。
- **來源**：A `CLAUDE.md@f0a6c474:1194` 起〈§2.3 Point-in-Time — 防 Lookahead〉。D 客戶訊息 2026-10-15T13:40Z（本 session；本檔首次入庫）§9「«歷史決策不能看到當時尚未公開的資料。»」。B #854 `8ed6d6ac`（M1B 校準 look-ahead 修正）。A `docs/BACKLOG.md@f0a6c474:55`（DR-2026-10-15-3 含「historical no-look-ahead」）。

### DEC-040｜硬性資料／UI 規則（MSG 1 §19）
- **內容**：缺值不填 0；顏色不是唯一載體；unavailable ≠ neutral；not evaluated ≠ safe；freshness／provenance／as-of 必須屬實；不得 fake precision；不得以另一個百分比冒充缺失建議持股；缺有效 System Risk Cap → 建議持股比例「無法判定」。
- **範圍**：資料語意／UI｜**日期**：2026-10-15（通則）｜**決策者**：客戶｜**狀態**：生效
- **來源**：D 客戶訊息 2026-10-15T13:40Z（本 session；本檔首次入庫）§19「19. 硬性資料／UI規則 / 永久維持：/ - 缺值不填 0」。repo 佐證：顏色 C `H:4670`「③ ⛔ 顏色不是唯一載體」；not evaluated ≠ safe C `H:1502`「不得宣稱紅線已通過」；缺 Cap → 無法判定 C `H:1502` 區塊；provenance／freshness A `CLAUDE.md@f0a6c474:1177`（§2.2）、`:1219`（§2.4）；unavailable ≠ neutral B `ff5f00da`（#620）「缺資料不得偽裝成利空/利多」。
- ⚠️ **落地現況**：通則有效**不代表 production 已全面合規** —— 例：BACKLOG `AUD-C14`「評分函式缺資料回 50（假中性）」仍 open；`CLAUDE.md` §2.2 自承 provenance「尚未統一」。「no fake precision」除本條外無正式產品規則。

## 4. System Risk Cap／公式（formula）

### DEC-041｜缺資料不得表示為危險；8 項總經輸入全缺走「系統異常」（Q-z12～Q-z14＝A）
- **範圍**：資料語意／公式｜**日期**：2026-10-10｜**決策者**：客戶｜**狀態**：**部分取代**（撰寫組判讀、單組，**待客戶確認**：「部分資料仍有效時，不要自行改變現有模型」一句，在新 UI 路徑被 DEC-048 Required Core 閘門修正）
- **來源**：C `H:644`「3. Q-z14：8 項總經輸入全部缺值時，改走既有「系統異常」保護，不得再輸出「震盪／曝險上限 60%」這類正常投資結論。」。B #821 `26a43064`。
- **取代鏈**：→ DEC-048（部分；取代範圍為撰寫組判讀，單組）。

### DEC-042｜新 UI「🚀 更新今日戰情」自動計算既有系統風險上限＝搬遷，不是重新設計（題 2＝A）
- **內容**：沿用已核准公式、條件、門檻、有效期與來源；不新增 AI 金鑰依賴；缺資料不補 0／前值／推定；算不出顯示未取得／無法判定、不放寬風控；新舊對帳；舊公式有錯或多解 → 停下。
- **範圍**：公式／產品｜**日期**：2026-10-14｜**決策者**：客戶｜**狀態**：生效（已實作；後續由 DEC-048～DEC-052 細化）
- **來源**：C `H:1447`「新 UI 執行「🚀 更新今日戰情」時，自動計算既有「系統風險上限」。」。B #852 `70416a6a`（⚠️ 這是 2026-10-15 的舊 commit，**不是目前 main**）。

### DEC-043｜Risk Cap 缺項不計分＋「N 項未評估，上限可能偏寬」（Q-z35＝A）
- **範圍**：公式／UI｜**日期**：2026-10-14｜**決策者**：客戶｜**狀態**：**部分取代**（文案部分有客戶明示；「缺項不計分」部分為撰寫組判讀、單組，**待客戶確認**）
- **來源**：C `H:1483`「維持既有「缺項不計分」規則，不重新設計模型。」
- **取代鏈**：文案「上限可能偏寬」→ **被 DEC-051 取代**（明文「不寫「上限可能偏寬」」）；「缺項不計分」對 Required Core → **被 DEC-048 部分取代**（Optional 缺項仍不計分、須揭露）。

### DEC-044｜Risk Cap 既有細項維持現行（Q-z36＝A 附條件）
- **內容**：只沿用既有已核准 fallback／cache／freshness，不自創天數；完全算不出保留 7 天內最近一次有效上限；新頁取不到有效上限 → 建議持股「無法判定」；Sahm 無資料源 → 不觸發並明示、不得宣稱紅線已通過；65 分 → 60% 維持現行。
- **範圍**：公式｜**日期**：2026-10-14｜**決策者**：客戶｜**狀態**：生效
- **來源**：C `H:1502`「- Sahm 無資料源 → 不觸發並明示：同意，僅屬目前狀態，不得宣稱紅線已通過。」；同區塊「- 65 分→60%：維持現行，不改公式。」。

### DEC-045｜推播行動一致性（DR-2026-10-15-1）
- **內容**：只重用 `suggest_action` 既有優先序；汰弱／停利／暫停加碼不得出現在加碼段；watchlist 與持股分流、不得描述為持股加碼；不新增公式／比例／權重／action semantics；補真實引擎 regression。
- **範圍**：產品／公式邊界｜**日期**：2026-10-15｜**決策者**：客戶｜**狀態**：生效（已實作）
- **來源**：A `docs/BACKLOG.md@f0a6c474:53`。D 客戶訊息 2026-10-15T19:42Z（本 session；本檔首次入庫）「Q1＝A。/ 第一個 Batch 做 C3「推播行動一致性」。」。B #855 `5b7b73b2`。

### DEC-046｜Risk Cap 部分輸入：不接受「N/8 門檻」，先做 semantics audit（DR-2026-10-15-2）
- **內容**：方向原則：真正 Required Core 缺失 → 無法判定；Optional／Context 缺失不得在無證據下讓整個 Decision 癱瘓；不得自行發明「至少 N/8」門檻。
- **範圍**：公式｜**日期**：2026-10-15｜**決策者**：客戶｜**狀態**：生效（具體化於 DEC-048、DEC-049）
- **來源**：A `docs/BACKLOG.md@f0a6c474:54`。D 客戶訊息 2026-10-15T19:42Z（本 session；本檔首次入庫）「「計分項少於一半就不寫上限」本身是一條新的資料充分性／投資規則，現在沒有足夠證據核准 4/8 這個門檻。」

### DEC-047｜季財報累計值須先拆單季再算跨季趨勢（DR-2026-10-15-3）
- **內容**：施工前驗證 Q1 基準、YTD → 單季、fiscal boundary、缺季、restatement、missing、不補 0、historical no-look-ahead；出現多個合理財務語意 → 停下裁示。
- **範圍**：公式／資料語意｜**日期**：2026-10-15｜**決策者**：客戶（方向）；拆季細則為 AI 總管內部語意驗證結論（2 組），屬本條實作註、不另升格｜**狀態**：生效（已實作）
- **來源**：A `docs/BACKLOG.md@f0a6c474:55`；細則 `:153`（AUD-C4 列）。D 客戶訊息 2026-10-15T19:42Z（本 session；本檔首次入庫）「C4 應朝「正確拆出單季值後，再計算跨季趨勢」修正。」。B #857 `0383f9bd`。

### DEC-048｜Required Core＝{VIX、PMI 當期、PMI 前月、外資期貨＋MA5}（DR-2026-10-16-1）
- **內容**：任一 Required Core 無法評估 → 不產生新 System Risk Cap；可沿用 7 天內最近一份有效快照；超過 7 天 →「無法判定」；不得因缺資料放寬風控；M1B/M2、PCR、BIAS240 暫列 Optional、缺失須揭露；**非永久分類**，日後校準／Shadow Mode 證據顯示應調整須回客戶裁示。
- **範圍**：公式｜**日期**：2026-10-16｜**決策者**：客戶｜**狀態**：生效（已實作）
- **來源**：A `docs/BACKLOG.md@f0a6c474:57`。D 客戶訊息 2026-10-16T02:32Z（本 session；本檔首次入庫）「Required Core 暫定為：/ {VIX、PMI 當期、PMI 前月、外資期貨＋MA5}。」；「這是目前證據支持下的正式版本，不代表永久分類」。B #860 `ef7cf41c`。
- **取代鏈**：部分取代 DEC-041、DEC-043（範圍為撰寫組判讀，單組）。

### DEC-049｜M1B−M2 自 System Risk Cap 正式計分停用（DR-2026-10-16-2）
- **內容**：與 `M1B_M2_LEG_ENABLED=False` 同步；保留歷史版本與 versioning，不改寫歷史 Decision；DL-f1-s8 若支持重新啟用另案裁示。
- **範圍**：公式｜**日期**：2026-10-16｜**決策者**：客戶｜**狀態**：生效（已實作，`risk_cap_ruleset_version="risk_cap.v2"`）
- **來源**：A `docs/BACKLOG.md@f0a6c474:58`。D 客戶訊息 2026-10-16T02:32Z（本 session；本檔首次入庫）「將 M1B−M2 從 System Risk Cap 正式計分中同步停用。」；「不要讓已停用訊號繼續偷偷提高 Risk Cap。」。B #860 `ef7cf41c`。

### DEC-050｜revenue_yoy＝當季單季營收 ÷ 去年同季單季營收 − 1（DR-2026-10-16-3）
- **內容**：沿用 #857 拆季邏輯；任一端缺值或去年同季 revenue ≤ 0 → NaN、不補 0；不改寫已凍結的 7/22～10/02 歷史選股；Decision History 保留方法版本切換。
- **範圍**：公式｜**日期**：2026-10-16｜**決策者**：客戶｜**狀態**：生效（已實作）
- **來源**：A `docs/BACKLOG.md@f0a6c474:59`。D 客戶訊息 2026-10-16T02:32Z（本 session；本檔首次入庫）「YoY = 當季 standalone revenue / 去年同季 standalone revenue − 1。」。B #859 `8b8f9e1e`。

### DEC-051｜Risk Cap 卡面揭露 Optional 資料完整性（DR-2026-10-16-4）
- **內容**：今日頁與持股頁卡面直接列「未評估：PCR、BIAS240」等實際項；中性措辭「部分訊號未納入，本次上限資訊不完整」，不寫「上限可能偏寬」；全有效可顯示「必要與選用訊號皆已評估」（擁擠可省）；M1B−M2 不列未評估、可另列「已停用」；詳細摺疊可列資料日期；顏色不得是唯一載體。
- **範圍**：UI／公式呈現｜**日期**：2026-10-16｜**決策者**：客戶｜**狀態**：生效（已實作）
- **來源**：A `docs/BACKLOG.md@f0a6c474:60`。D 客戶訊息 2026-10-16T08:00Z（本 session；本檔首次入庫）「不要固定寫「上限可能偏寬」；改為中性且準確的「部分訊號未納入，本次上限資訊不完整」。」。B #862 `fa26914b`。
- **取代鏈**：取代 DEC-043 的文案。

### DEC-052｜新 UI 獨立 Risk Cap state／snapshot 檔；舊 UI 原檔不改（DR-2026-10-16-5）
- **內容**：新 UI 不得再讓舊 UI 寫入覆蓋其有效快照；只接受符合 Required Core、版本標記與 freshness 的 snapshot；舊 UI 凍結不為相容新 UI 修改；不改寫歷史 Decision／frozen validation；檢查所有新 UI read/write path、無 fallback 偷讀舊檔；AUD-C22 維持獨立 Backlog。
- **範圍**：資料／儲存｜**日期**：2026-10-16｜**決策者**：客戶｜**狀態**：生效（已實作）
- **來源**：A `docs/BACKLOG.md@f0a6c474:61`。D 客戶訊息 2026-10-16T08:00Z（本 session；本檔首次入庫）「新 UI 建立自己的獨立 Risk Cap state / snapshot 檔案；舊 UI 繼續使用原檔，不修改舊 UI。」。B #862 `fa26914b`。

### DEC-053｜正式加減碼比例須經「資料驗證 → 規則設計 → 回測／Shadow Mode → 客戶裁示」才能進 production
- **範圍**：公式（程序規則）｜**日期**：2026-10-15｜**決策者**：客戶｜**狀態**：生效
- **來源**：D 客戶訊息 2026-10-15T13:40Z（本 session；本檔首次入庫）§5「必須日後經：/ 資料驗證 → 規則設計 → 回測 / Shadow Mode → 客戶裁示 / 才能進 production。」

### DEC-074｜DH-GATE-BREADTH 裁示 B：代理廣度不得計分；受 breadth 影響且無法依既有正式規則可靠計算的健康分 →「⬜ 未評估／資料不足」；不重新設計 0.6／0.4 權重（客戶 2026-10-23）
> 2026-10-23 追加（第 8 節「收到當輪追加」；ID 照序取下一個未用號，撰寫組寫入前 `git grep -n "DEC-074"` 實測 0 命中）。BACKLOG 登記：DR-2026-10-23-2；受影響列 5.1.7 `DH-GATE-BREADTH`（已裁示）、`DH-ADL-PROXY`、`DH-JINGQI-HEALTH`。
- **內容**（客戶原文；經總管轉交，撰寫組未見原件，依總管轉交文字逐字收錄）：

```
客戶不同意為了維持健康分而立即重新設計 0.6／0.4 權重。
正式方向：
- 推估的漲跌家數／proxy breadth 不得計分。
- 不得把缺少真實 breadth 當成 0、中性或正常。
- 在正式 breadth 資料，或另一套經客戶核准的計算方式完成以前：
  - 受 breadth 影響且無法依既有正式規則可靠計算的健康分 → "⬜ 未評估／資料不足"
  - 不得自行創造新權重重新正規化。
  - 不得因為產品希望「有結論」而補出投資結論。
```

- **裁示對照**：總管原推薦 **(A)** 重新歸一為只含大盤評分並揭露「廣度未評估」；客戶裁 **(B)**。⛔ **(A) 不採用**（客戶原文「不得自行創造新權重重新正規化」直接排除既有 `health_partial` 重新歸一路徑作為替代結論）。
- **範圍**：公式／資料語意｜**日期**：2026-10-23｜**決策者**：客戶｜**狀態**：生效（裁示登記）；⛔ **本裁示不是實作授權** —— 計分移除、「⬜ 未評估／資料不足」呈現與下游位階／建議持股姿態帶處置的實作，**仍待客戶指派**（`CLAUDE.md` §-1；DEC-002、DEC-015）；畫面變動仍須先出文字線框（DEC-003）。
- **來源**：D 客戶訊息 2026-10-23（本 session；本檔首次入庫；經總管轉交；確切 UTC 時戳未記錄，只保留日期）。
- **與其他 DEC 的關係**（append-only；撰寫組讀法，單組，⚠️ 待第二組 evidence audit）：
  - **DEC-062 Q5**（代理值只顯示、不計分；同樣適用總經彙總燈）：**同向、具體化**。Q5 已禁代理值計分；本條補上 Q5 未答的下游處置 —— 移除代理廣度後，健康分**不得**改權重補結論，而是「⬜ 未評估／資料不足」。
  - **DEC-037**（M1B 代理值只顯示不計分）：**同向**，為同一原則（代理值不計分）的前例；本條延伸至漲跌家數／旌旗。
  - **DEC-072**（📊 大盤頁「首屏先給結論與少數關鍵原因」）：**張力，以本條為準於資料不足時**。大盤頁在 breadth 未到位期間可能無法給健康分結論；客戶原文「不得因為產品希望「有結論」而補出投資結論」—— 撰寫組讀為：DEC-072 的「先給結論」不得被用來要求補結論；呈現方式待線框（DEC-003）。
  - **DEC-026**（Missing ≠ 0）、**DEC-041／DEC-043**（缺資料揭露）：同向（「不得把缺少真實 breadth 當成 0、中性或正常」）。
  - 「受 breadth 影響且**無法依既有正式規則可靠計算**」的判定範圍（例：大盤分單獨是否仍可依既有規則顯示）**未由本條逐項列舉**，屬實作批的語意驗證項；有多個合理讀法時須停下裁示（第 4 節 #2），⛔ 撰寫組不預判。

### DEC-075｜Data Health 修復計畫裁示：D-1 `DH-GATE-REGIME-FALLBACK`＝(a) 位階一併「⬜ 未評估／資料不足」；指派批 A（DEC-074 B 落地＋`DH-TWII-MA200`）＋同意加掛批 1'；批 2 暫不與 VN1-PG 一起指派（客戶 2026-10-23）
> 2026-10-23 追加（第 8 節「收到當輪追加」；ID 照序取下一個未用號，撰寫組寫入前 `git grep -n "DEC-075"` 實測 0 命中、最大為 DEC-074）。BACKLOG 登記：DR-2026-10-23-3（裁示結果 append）；受影響列 5.1.7 `DH-GATE-REGIME-FALLBACK`（已裁示）、`DH-GATE-BREADTH`／`DH-ADL-PROXY`／`DH-JINGQI-HEALTH`／`DH-TWII-MA200`（批 A）、`DH-FOREIGN-FILL0`／`DH-EXPORT-LABEL`／ISM 教學 key（5.1.7「關聯 `VN1-MT-SSOT-ISM`，不另立」列；批 1'）。計畫本文：`docs/vnext/DATA_HEALTH_REPAIR_PLAN_2026-10-23.md`（第 1 節批 A、第 1.5 節 D-1、第 2.1 節批 1'、第 3 節範圍題）。
- **內容**（客戶原文；經總管轉交，撰寫組未見原件，依總管轉交文字逐字收錄）：

```
1. `DH-GATE-REGIME-FALLBACK`：選 (a)。
   * 健康分因缺少正式 breadth 而未評估時，受此資料契約影響、無法可靠成立的市場位階也顯示 `⬜ 未評估／資料不足`。
   * 不允許在使用者無法清楚辨識的情況下，靜默 fallback 到另一套規則引擎產生位階結論。
   * 缺資料不得為了維持畫面結論而補結論。
2. 指派批 A。
   * #908 合併後可以作為下一批工作。
   * 包含已規劃的 DEC-074 B 落地與同批 ^TWII MA200 假值修正。
3. 同意加掛批 1'。
   * 外資缺值不得補 0。
   * 台灣出口燈依實際資料內容修正名稱。
   * 修正 ISM 教學對映。
   * 不得藉此新增資料來源或改變投資公式。
4. 批 2 暫時不要與 VN1-PG 一起指派。
   * 等批 A＋1' 完成、獨立 QA、CI、main verification，確認資料契約與下游影響後，再重新評估批 2／VN1-PG 的最佳邊界。
```

- **同時重申（總管轉述，非逐字）**：批 A 為 High；開工前依 DEC-073 Gate 自判模型；總管已判目前模型足夠（高能力模型），依既有授權進入靜默巡航（DEC-007／DEC-059；DEC-073 為其正式例外，只在能力**不足**時打斷）。⚠️「目前模型足夠」是總管自判，撰寫組無法查證。
- **裁示對照**（送題 vs 裁示）：
  - **D-1**：總管推薦 (a) → 客戶裁 **(a)**。⛔ **(b)「維持現況（健康分 ⬜ 但位階退 `macro_state.json` 規則引擎位階、新 UI 卡③ degraded 照印）」不採用**（客戶原文第 1 點第 2 句直接排除「靜默 fallback 到另一套規則引擎產生位階結論」）。
  - **範圍**：總管推薦「只做批 A（D-1 裁示後）；批 1' 可選加掛；批 2 併 `VN1-PG-*` 實作批」→ 客戶：**批 A 指派**（#908 合併後為下一批）、**批 1' 同意加掛**、**批 2 暫不與 VN1-PG 一起指派**（與總管提案第 4 點不同：不是否決，是**延後重評**，時點＝批 A＋1' 完成、獨立 QA、CI、main verification 之後）。
  - **`DH-EXPORT-LABEL` 的業務確認（訂單 vs 金額）**：客戶原文「台灣出口燈依實際資料內容修正名稱」—— 撰寫組讀為採總管推薦「改名為出口金額（海關）、不換源」（實際資料內容＝海關出口金額 YoY，計畫 2.1 CONFIRMED）；⚠️ 原文**沒有逐字寫「出口金額」**，此為撰寫組讀法，實作批 PR 須揭露最終燈名。
- **範圍**：公式／資料語意（D-1）＋治理（指派）｜**日期**：2026-10-23｜**決策者**：客戶｜**狀態**：生效（裁示登記＋**動工授權：批 A＋批 1'**）。
- **效力邊界（寫死，防兩個方向誤用）**：
  - ✅ **批 A＋1' 已指派＝動工授權**：DEC-074 的「⛔ 本裁示不是實作授權…仍待客戶指派」與 DEC-002／DEC-015 的「待指派」**對這兩批自本條起不再成立**（DEC-074 原文不改，取代關係登第 5 節）。「下一批」的時點為 #908 合併後（客戶原文第 2 點）。
  - ⛔ **授權範圍只到計畫列出的批 A（含 `DH-TWII-MA200`）＋批 1' 三項**（`DH-FOREIGN-FILL0`／`DH-EXPORT-LABEL`／ISM 教學 key）。批 2（`DH-BIAS240-EST`／`DH-PCR-PROXY`／`DH-MACRO-FWD-ASOF`／`DH-REFRESH-STALE`）、批 3、批 4、`DH-LAMP-STALE`、VN1-PG 三項實作批**皆未授權**；批 2／VN1-PG 的**最佳邊界待重評**，重評結果須另送裁示。
  - ⛔ **「畫面結構異動」仍受 DEC-003 ① 線框 gate，本條不豁免**：計畫第 1.6 節判「需線框」者（新增「廣度資料狀態」獨立卡／列、今天頁多一個 fact 列、移除／合併舊 UI 區塊或 ADL KPI 四格、五桶把 `adl` 盞拿掉）**仍須先出文字線框**；判「不需線框」者（既有欄位換文案、既有 None 路徑常態觸發、位階卡改顯示 ⬜＝狀態變不是結構變）為修正錯誤（`CLAUDE.md` §-1.5.A-8），可直接做。
  - ⛔ **批 1' 不得藉此新增資料來源或改變投資公式**（客戶原文第 3 點末句）；批 A 亦不得（DEC-074「不重新設計 0.6／0.4 權重、不重新正規化」續有效）。
  - ⛔ **舊 UI 凍結（DEC-019）不變、本條不是 DEC-019 的豁免**：批 A 改的是共用層（L0 旗標／L2 `calc_traffic_light`／L3 `jingqi_calc`、`market_assessment_apply`、`get_macro_state`）根因，新 UI 確實依賴（`page_today` 五桶、卡①／卡③、找標的頁濾網）；舊 UI 檔（`handlers` 文案表、`app.py` 旌旗徽章等）若因共用層契約改變而連帶改動，須在 PR 逐檔揭露「為何屬新 UI 依賴的根因修正」，由獨立 QA 判是否超出 DEC-019；⚠️ 此為撰寫組讀法，`DH-TWII-MA200` 的新 UI 0 讀者（QA MUST-B3，grep）與 DEC-019 的張力由實作批 PR 揭露、不由本條預判。
  - ⛔ **本條不改 Risk Cap**：Risk Cap VALID 判定與位階／健康分無關（計畫稽核 A5），(a) 不影響 `PRODUCTION_WRITE_APPROVED`／Daily Schedule 狀態（DEC-066／DEC-070 不變）。
- **(a) 的技術落點**（依 DEC-003 屬內部自決區；此處只記錄落點供獨立 QA 驗收與交接，**不是**客戶裁示的一部分；轉錄自計畫 1.5 (a) 技術欄＋QA MUST-A1）：`src/services/macro_state_locker.py::get_macro_state` **不得**在 breadth 缺席導致健康分 None（非有限值）時退回 `macro_state.json` 檔案位階 —— 位階 → 未評估（`regime=unknown`）、`is_loaded=False`；現行 `_wr_ok`（C1 v19.182「NaN 視同未載入」）守衛語意須依本條改寫（health 非有限時仍讀 warroom `regime_source`／未評估原因，不得因 health 缺席就視同 warroom 不存在而退檔案）；`tests/test_macro_state_canonical.py`／`tests/test_batch_z60.py` 相關斷言依本條更新；下游：🎯 找標的頁空頭濾網不套用（走既有「未評估不套用、L3 註記」路徑）、🛡️ 持股頁位階／姿態帶未評估、AI 問答回「未評估」。⚠️ 揭露：`get_macro_state`／`_wr_ok` 符號存在為撰寫組 `grep` 實查；改法未實作、未實跑；AUD-C22「位階第 3 順位來源本批不動」的語意會被 (a) 改寫，AUD-C22 原文未由撰寫組對照（計畫已揭露）。
- **來源**：D 客戶訊息 2026-10-23（本 session；本檔首次入庫；經總管轉交；確切 UTC 時戳未記錄，只保留日期）。
- **與其他 DEC 的關係**（append-only；撰寫組讀法，單組，⚠️ 待第二組 evidence audit；舊 DEC 條文一字不改）：
  - **DEC-074**（Breadth Gate 裁 B）：**落地指派＋下游處置具體化**。DEC-074 第 5 點留白的「受 breadth 影響且無法依既有正式規則可靠計算」範圍，本條明示**市場位階列入**（D-1 (a)）；DEC-074「⛔ 不是實作授權」由本條**部分取代**（批 A 已指派）；「不得因為產品希望『有結論』而補出投資結論」與本條「缺資料不得為了維持畫面結論而補結論」**同向、延伸到位階**。
  - **DEC-073**（Model／Effort Gate）：**適用、不改**。批 A 為 High；開工前已依 Gate 自判（總管判模型足夠，撰寫組無法查證）；Gate「能力不足強制停手」仍為靜默巡航的正式例外。批 1'（Medium）與批 A 同批時以較高者（High）為準 —— **撰寫組讀法**。
  - **DEC-062 Q5**（代理值只顯示、不計分；無資料來源不得宣稱通過；適用總經彙總燈）：**同向**。本條 (a) 把「不得宣稱通過」延伸為「不得靜默換另一套規則引擎給位階結論」；批 1'「外資缺值不得補 0」亦同向（DEC-026、DEC-035）。
  - **DEC-019**（舊 UI 凍結）：**不變、不豁免**（見效力邊界）。
  - **DEC-003**（線框 gate）：**不變、不豁免**（見效力邊界）；D-1 (a) 下位階卡改顯示 ⬜ 屬狀態變、不是結構變，不需線框（計畫 1.6；A-8 修正錯誤）。
  - **DEC-072**（大盤頁首屏先給結論）：**張力同 DEC-074 所載，以 DEC-074／本條為準**。本條 (a) 使大盤頁位階卡在正式廣度到位前**常態 ⬜**；送題時已向客戶列明此影響，客戶知情裁 (a)。
  - **DEC-070／VN1-PG**：批 2 **不併**；VN1-PG 三項實作批授權狀態**不變**（仍未授權，見 `docs/HANDOFF.md` 第 0 節）。
  - **DEC-037**（M1B 代理不計分先例）：批 A 鏡像其 `M1B_M2_LEG_ENABLED` 旗標機制，不發明第二種機制。
  - **DEC-002／DEC-015**（沒指派不動工／Audit 不得順手施工）：對批 A＋1' **已由本條指派**；對其餘 `DH-*` 續有效。
  - **DEC-066**（Risk Cap production Gate）：不受影響（Risk Cap 與位階／健康分無關，稽核 A5）。
- 📌 **2026-10-23 附註（append-only；本條上文一字未改；⚠️ 總管判讀，非客戶原文，不是新 DEC）**：
  - **實作狀態（事實）**：批 A＋1' 已於分支 `ccr-310717b7-37xwl6` 實作（commits `1f4f5b19`、`7ef52869`、`ee4bde01`、`04a9bc2e`），**待 PR #910 合併**；D-1(a) ~~已落地於~~ ~~**只完成於**「warroom 存在、健康分因缺正式 breadth 未評估」路徑（含該路徑下的 ^TWII 全滅情境）；**冷啟動／warroom 不存在路徑未完成（見 `DH-REGIME-NOWARROOM`）**~~（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（QA-4 M-1：D-1(a) 只完成 warroom 存在的路徑））**在代理廣度不計分（旗標關）時涵蓋 warroom 存在（含 ^TWII 全滅）與不存在（冷啟動未載入、warroom 被移除）兩條路徑**（PR #910 `DH-REGIME-NOWARROOM`）（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（依兩組獨立調查裁定冷啟動屬 DEC-075 D-1(a) 射程；客戶 2026-10-23 指示不得只登 BACKLOG 延後））（⚠️ 實作組自述、待 QA 複驗（`CLAUDE.md` §-2 規則 6））。
  - **殘留與射程判讀（總管判讀，非客戶原文）**：warroom **不存在**的路徑（冷啟動未載入；或 `calc_traffic_light` 三源全空回 None 時 warroom 被移除）~~仍回 `macro_state.json` 規則引擎位階且 `is_loaded=True`，AI 評分與 🎯 找標的頁濾網會套用。~~ （PR #910 之前）曾回 `macro_state.json` 規則引擎位階且 `is_loaded=True`，AI 評分與 🎯 找標的頁濾網會套用；現行（PR #910 分支，代理廣度不計分時）：回位階 `unknown`／⬜、`is_loaded=False`，不退規則引擎位階（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（QA-6 S-1））。總管判讀此路徑**屬本條 D-1(a) 射程**（客戶原文「不允許在使用者無法清楚辨識的情況下，靜默 fallback 到另一套規則引擎產生位階結論」）；主要理由：**同一畫面載入前後位階結論不一致**（載入前顯示規則引擎位階、載入後顯示 ⬜），使用者無法辨識結論來源已換。技術落點屬內部自決（DEC-003），~~待下一安全段落處理~~ 已於 PR #910 修正（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（依兩組獨立調查裁定冷啟動屬 DEC-075 D-1(a) 射程；客戶 2026-10-23 指示不得只登 BACKLOG 延後））；登記為 `docs/BACKLOG.md` 5.1.8 `DH-REGIME-NOWARROOM`。
  - 📌 **2026-10-23 再補一行（append-only）**：總管依兩組獨立調查裁定冷啟動屬 D-1(a) 射程並於 #910 修正（客戶 2026-10-23 指示「不得只登 BACKLOG 延後」）。⚠️ 實作組自述、待 QA 複驗（`CLAUDE.md` §-2 規則 6）
  - ⚠️ 若客戶認為 D-1(a) 只涵蓋「健康分已計算但未評估」的情境、不涵蓋「尚未載入」，以客戶為準，本判讀即撤銷，`DH-REGIME-NOWARROOM` 改為送題。撰寫組只記錄總管判讀，未獨立驗證其殘留路徑（`CLAUDE.md` §-2 規則 6）。
  - 📌 **2026-10-23 Freeze 附註（append-only；本條上文一字未改；不是新 DEC）**：PR #910 ~~HEAD `c8e30d84`~~ 最後產品碼 commit `c8e30d84`（HEAD 以 PR #910 為準（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實修正）））（`DH-REGIME-NOWARROOM`）已在代理廣度不計分（旗標關）時補上**冷啟動路徑**（warroom 不存在＋有效 `macro_state.json` ⇒ 位階 `unknown`／⬜、`is_loaded=False`；Risk Cap `exposure_limit_pct` 不變）—— 依客戶 2026-10-23 指示（總管轉述：「CI 綠也先不要合併；冷啟動若違反 D-1(a) 須本 PR 修完」，即不得只登 BACKLOG 延後）。⚠️ **狀態（2026-10-23 23:08 台北量測，會過期）**：QA-6 對 `c8e30d84` 獨立複驗**進行中、結果未知**；CI 進行中；#910 **未合併**。⛔ **#910 合併前不得宣稱 D-1(a) 冷啟動修正已落地 main**；實況以 GitHub（PR #910、main SHA）為準。實作內容為實作組自述，撰寫組未獨立驗證（`CLAUDE.md` §-2 規則 6）。
  - 📌 **2026-10-23 QA-6 結果附註（append-only；上文一字未改；不是新 DEC）**：QA-6 對 `c8e30d84` 判**不可合併（2 MUST）**：契約層（D-1(a) 本體）、Risk Cap、測試守護、突變均成立；但 🛡️ 持股頁卡④（冷啟動、缺真實廣度）／卡⑤（缺真實廣度）在 v2 卡面畫成紅卡（短句表 KeyError），且 AI 評分被擋字串在冷啟動附不實救法。兩項已於 #910 後續修正 commit 處理，**待獨立 QA-7＋CI**；#910 仍**未合併**（有意識的更新，不是漏刪，決策者 AI 總管）。⚠️ 修正內容為實作組自述（`CLAUDE.md` §-2 規則 6）。
  - 📌 **2026-10-24 合併附註（append-only；上文一字未改；不是新 DEC；有意識的更新，不是漏刪，決策者 AI 總管（事實更新））**：PR #910 已於 2026-10-24 squash 合併進 main（merge `066f461e`，完整 `066f461ec716abbc40a3830baf2c686415cd4ecf`）；最後產品碼 commit＝`9714d0b3`（修 QA-6 兩項 MUST）。**QA-7 對 `9714d0b3` 判可合併（0 MUST）**；`9714d0b3` CI Fast＋Slow success；完整判定見 PR #910 留言。⇒ D-1(a) 在旗標關（`BREADTH_PROXY_SCORING_ENABLED=False`）時**含冷啟動路徑已落地 main**；上文「待 PR #910 合併」「待獨立 QA-7＋CI」「待 QA 複驗」自此讀作已合併、QA-7 已判可合併。本條裁示內容不變；DEC-075 第 4 點（批 2／VN1-PG 邊界重評後送題）觸發條件中「批 A＋1' 合併」已成立，~~main CI／main verification 以 GitHub Actions 為準（撰寫組未查）~~ main CI／main verification **已成立**（見下一則附註）（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。QA-7 SHOULD S-1 徽章語意另登 BACKLOG `DH-BADGE-RERUN-SEMANTICS`（視覺規格，待客戶裁示）。
  - 📌 **2026-10-24 main verification 附註（append-only；上文一字未改（僅上一則「撰寫組未查」一句以刪除線更正）；不是新 DEC；有意識的更新，不是漏刪，決策者 AI 總管（事實更新））**：第 4 點前置條件之 **main verification 已成立** —— 依 `PROJECT_RULES.md` 第 7 節定義（main SHA＋main CI conclusion）：main `066f461e`（#910 merge）的「PR Check（pytest fast + AppTest slow）」push run **39995254045 success**；main `649f739`（#911，五 SSOT 事實同步）同 workflow push run **39999485112 success**。總管以 GitHub Actions API 實查，撰寫組另以 `gh api repos/:owner/:repo/actions/runs/<id>` 獨立複查兩個 run 的 `head_sha`／`event=push`／`head_branch=main`／`conclusion=success`，結果一致（2 組）。⚠️ 未驗：squash 後 main 樹是否等同 `9714d0b3`（沙箱取不到該 object）。⇒ 第 4 點「批 A＋1' 完成、獨立 QA、CI、main verification」**全部成立**，重評已完成、送題已裁示：**重評結果見 DEC-077**（採方案 C）。

### DEC-076｜客戶 2026-10-23 Freeze 指示確認之產品方向與語意界線
> 2026-10-23 追加（第 8 節「收到當輪追加」；ID 照序取下一個未用號，撰寫組寫入前 `git grep -n "DEC-076"` 實測 0 命中、最大為 DEC-075）。永久治理部分（Data ≠ AI、Model／Effort、停手條件、舊 UI、branch、production）落點 `PROJECT_RULES.md` **第 16 節**；未完成工作（舊 UI → 新 UI Coverage Matrix、Investment Logic Validity Audit、研究候選等）由 BACKLOG 撰寫組登記於 `docs/BACKLOG.md`（本批 W1 不改該檔）。
- **內容**（客戶 2026-10-23 約 23:05 台北訊息第 4.1、6、7、8、10、12、16、17、20 節，**原文逐字**；經總管轉交、總管逐字轉錄，撰寫組未見原件）：

```
## 4.1 核心產品原則：正式保存：> **底層能力完整保留，前台流程極簡。** 新 UI 不是把舊 UI 原封不動搬過去。也不是因為新版簡化，就可以把舊 UI 的投資能力刪掉。正確方向：舊 UI 有價值的功能／投資判讀邏輯 → 重新整理資訊架構 → 決定新 UI 放置位置 → 重新設計顯示方式 → 驗證能力覆蓋 → 最後才考慮刪除舊 UI。

# 6. 新 UI 已確認方向（請保存／核對）。主要投資流程：
### 📊 大盤／市場趨勢 回答：「現在市場環境適不適合投資？目前可以承擔多少風險？」包含：大盤、市場位階、台股趨勢、國際趨勢、指標危險度、Risk Cap、重要總經／籌碼／技術資訊。但底層語意必須分開。
### 🎯 標的 整合：找標的、查一檔、個股健檢、ETF、財報、籌碼、技術、估值、其他既有標的分析能力。基本體驗：> 標的清單 → 點一檔 → 同頁／淺層 route 完整健檢。
### ⚡ 行動 承接既有 deterministic action logic，例如：exit signal、take profit、swap、汰弱換強、watch、action required。不得因為 UI 需要而自行發明新的加減碼比例或投資語意。
### 🛡️ 持股 承接：個股／ETF 健檢、配息、stress、VaR、risk contribution、concentration、portfolio limits、其他既有組合風險能力。
### 🩺 資料中心 不是第五個主要投資決策頁。它是：系統／資料維護入口。至少能追蹤：資料、狀態、最新資料日、來源、問題、影響功能、下一步／處理方式。處理類型：可自行修復／需研究替代來源／API／MCP／需客戶裁示／暫不處理。
### 👤 我的 作為：account、settings、connection、utility。不要塞回主要投資流程。
### 「憑什麼」 改成每頁 contextual explainability：為什麼這樣判斷、指標、日期、資料來源、規則。不是主要 navigation investment page。

# 7. Progressive Disclosure：第一層 直接給使用者需要的結論／狀態。第二層 告訴使用者主要原因。第三層 需要時才展開：原始指標、日期、source、rule、technical detail、confidence / completeness。不要把舊 UI 的所有燈號、數字、技術細節一次攤在首頁。

# 8. 必須保存的投資語意定義（不得混為單一分數）：市場位階：市場 bull / bear / trend 狀態。指標危險度：目前多少危險條件／門檻被觸發。它不等於市場多空。Risk Cap：允許承擔的最大曝險／風險控制。它不等於市場趨勢。台股趨勢：新的 research / market trend concept。國際趨勢：新的 international research / market trend concept。因此完全可能：> 趨勢偏多 但風險升高 Risk Cap 降低。不得為了 UI 簡化，把以上概念偷偷合成單一 score/light。

# 10. Data Health 現況完整保存：Data Health Audit、DEC-074、DEC-075、Batch A、Batch 1'、Batch 2、Batch 3、Batch 4、new-source research。明確記錄 Batch A / 1'：哪些已完成；哪些在 #910；哪些仍待 QA／CI；哪些 deferred。D-1(a) 完整語意：正式 breadth 不存在／無法可靠計算相關 health 時：不得讓代理 breadth 參與 scoring；不得偷偷 fallback 產生看似正式的 market regime；affected result → ⬜ 未評估／資料不足；不得因產品想保持有答案而補結論。同時：**不要過度擴張成所有市場／Risk Cap 概念都失效。** 只有真正依賴失效資料的 component 才不可判定。Risk Cap 保持自己的既有語意。

# 12. Investment Logic Validity Audit：BACKLOG 必須加入／確認有一個獨立階段。它和 Data Health 是不同工作。Data Health 問：資料正不正確？Investment Logic Audit 問：在資料正確的前提下，投資規則本身是否仍合理？未來獨立檢查：市場判斷、Risk Cap、個股健檢、選股、技術、籌碼、財報、ETF、持股、exit、take profit、swap、position sizing、其他 deterministic investment rules。重要：**第一階段只 Audit，不直接改公式。** 如果證據顯示需要改 threshold、weight、formula、scoring、investment semantics：必須開 Decision Gate 給客戶裁示。不得把「資料錯誤」和「投資模型錯誤」混在一起。

# 16. 舊 UI 不得提前刪除。正式保存：> 新 UI 成立以前，舊 UI 是重要 capability / logic reference。只有完成：capability inventory、new UI mapping、implementation、coverage validation、regression、customer approval 後，才進入舊 UI removal Decision Gate。不得把「新版已經比較漂亮」當作刪除舊 UI 的理由。

# 17. 個股健檢不能遺失。確認舊 UI 已存在的 individual-stock health-check / replacement logic 被登記為新版必須盤點能力。包括 repo 目前已有的：財報健檢、KD / technical inputs、replacement / rotation、stock trend input、individual stock lights、holdings battle-room integration。若「MJ老師」這個來源／名稱沒有 GitHub 證據：不要自行寫成正式來源。只能保存「既有個股健檢邏輯」。

# 20. 新資料來源研究 保留／整理研究候選，例如：real market breadth、Sahm、US 2Y、yield spreads、30Y、TIPS、OECD CLI、securities lending、TDCC、ETF distribution/components、market EPS / PE / forward EPS、CSP / AI capex。這些是 research candidates。**不是已授權接入 production。** 下一個 AI 不得看到 BACKLOG 就自行換資料源。
```

- **範圍**：產品方向／UI 資訊架構／資料與投資語意界線／治理｜**日期**：2026-10-23｜**決策者**：客戶｜**狀態**：生效（方向與語意界線確認）；⛔ **不是動工授權**（`CLAUDE.md` §-1；DEC-002、DEC-015；客戶同訊息第 0 節「23:00 後：禁止開始新的 Batch…禁止改投資公式／權重／門檻／禁止刪舊 UI／禁止刪 branch」）；⛔ 不是線框核准（DEC-003 ①）。
- **來源**：D 客戶訊息 2026-10-23（約 23:05 台北；本 session；本檔首次入庫；經總管轉交）。客戶同訊息第 4 節原文：「已存在就引用／補完整；不存在且屬於客戶已確認方向，就正式落盤；若與既有正式裁示衝突，停止並列出衝突，不得自行覆寫。」

- **逐點比對既有 DEC**（撰寫組讀法，單組，⚠️ 待第二組 evidence audit，`CLAUDE.md` §-2 規則 6；舊 DEC 一字不改）：

| 客戶節 | 要點 | 比對結果 |
|---|---|---|
| 4.1 | 「底層能力完整保留，前台流程極簡」 | **已存在於 DEC-072**（原文「底層能力完整，前台流程極簡」；本則多「保留」二字，同義） |
| 4.1 | 新 UI 不是把舊 UI 原封不動搬過去；也不得因簡化刪舊 UI 投資能力 | 後半**已存在於 DEC-071 第 2 點**（「不應因新版簡化而大量刪除」）；前半「不原封不動搬」**本則新增** |
| 4.1 | 正確方向六步（舊能力 → 重整資訊架構 → 決定放置 → 重新設計顯示 → 驗證覆蓋 → 最後才考慮刪舊 UI） | **本則新增**（步驟序列）；「最後才刪」與 **DEC-020** 刪除前置路線同向 |
| 6 | 📊 大盤 回答「現在市場環境適不適合投資？目前可以承擔多少風險？」 | 後半**已存在於 DEC-072 第 1 點**；前半問句**本則新增** |
| 6 | 📊 大盤包含：大盤、市場位階、台股趨勢、國際趨勢、指標危險度、Risk Cap、重要總經／籌碼／技術資訊；「底層語意必須分開」 | 台股趨勢／國際趨勢／Risk Cap **已存在於 DEC-072 第 1 點**；「大盤」字樣**已存在於 DEC-071 第 6 點**；市場位階、指標危險度、重要總經／籌碼／技術資訊列入大盤頁**本則新增**；語意分開**已存在於 DEC-071 同輪客戶原文**（四者不合併） |
| 6 | 🎯 標的：標的清單 → 點一檔 → 同頁／淺層 route 完整健檢 | **已存在於 DEC-072 第 2 點**（同一流程、不另設查一檔導航）；「同頁／淺層 route」措辭**本則新增** |
| 6 | ⚡ 行動：承接既有 deterministic action logic（exit signal、take profit、swap、汰弱換強、watch、action required）；不得為 UI 自行發明加減碼比例或投資語意 | **已存在於 DEC-072 第 3 點**、DEC-053；例示清單**本則新增**。⚠️ 例示中 swap／汰弱換強是否屬 DEC-054 七種 Action、與 DEC-022 再平衡硬禁令的界線，**仍未裁示**（`CV1-FU-03`、`CV1-FU-02`）—— 本則**不解決**，例示不構成擴大 Action 範圍 |
| 6 | 🛡️ 持股：個股／ETF 健檢、配息、stress、VaR、risk contribution、concentration、portfolio limits | **已存在於 DEC-072 第 4 點**（健檢、曝險、集中度、風險、壓測）；配息、VaR、risk contribution、portfolio limits 例示**本則新增** |
| 6 | 🩺 資料中心：不是第五個主要投資決策頁；追蹤資料／狀態／最新資料日／來源／問題／影響功能／下一步；處理類型五類 | 定位**已存在於 DEC-072**（輔助入口、不屬主要投資流程）；欄位清單與處理類型五類（可自行修復／需研究替代來源／API／MCP／需客戶裁示／暫不處理）**本則新增**。⚠️「需研究替代來源／API／MCP」只是分類，**不是**接入授權（第 4 節 #3、#4） |
| 6 | 👤 我的：account、settings、connection、utility | **已存在於 DEC-072**；connection 例示**本則新增** |
| 6 | 「憑什麼」改每頁 contextual explainability（為什麼這樣判斷、指標、日期、資料來源、規則） | **已存在於 DEC-072**；五項內容清單**本則新增** |
| 7 | Progressive Disclosure 三層（結論／狀態 → 主要原因 → 需要時才展開原始指標、日期、source、rule、technical detail、confidence／completeness） | DEC-072 只對 📊 大盤首屏提「progressive disclosure」；**三層定義與全站適用本則新增** |
| 8 | 市場位階／指標危險度／Risk Cap／台股趨勢／國際趨勢五概念各自定義；不得合成單一 score／light；「趨勢偏多但風險升高 Risk Cap 降低」完全可能 | 不合併**已存在於 DEC-071 同輪客戶原文**（四者）與 DEC-072；**國際趨勢納入不合併清單、五項一句定義、反例本則新增**。⚠️ 見下方「待客戶確認」第 1 點 |
| 10 | D-1(a) 完整語意（代理 breadth 不得參與 scoring；不得偷偷 fallback 產生看似正式的 market regime；affected result → ⬜ 未評估／資料不足；不得為有答案補結論） | **已存在於 DEC-074、DEC-075**（同向，本則逐字重申） |
| 10 | 「不要過度擴張成所有市場／Risk Cap 概念都失效。只有真正依賴失效資料的 component 才不可判定。Risk Cap 保持自己的既有語意。」 | Risk Cap 不變**已存在於 DEC-075 效力邊界**（「本條不改 Risk Cap」）；**「不過度擴張、只有真正依賴失效資料的 component 才不可判定」本則新增**，作為 DEC-074 第 5 點留白範圍的上限 |
| 12 | Investment Logic Validity Audit 為獨立階段；與 Data Health 不同；**第一階段只 Audit，不直接改公式**；需改 threshold／weight／formula／scoring／semantics → Decision Gate；不得把資料錯誤與投資模型錯誤混在一起 | **本則新增**（階段定義）；「只 Audit 不施工」與 **DEC-015** 同向；「改公式須 Decision Gate」與 **DEC-009**（第 4 節 #1）同向。⛔ 本則**不是**啟動該 Audit 的指派 |
| 16 | 新 UI 成立以前舊 UI 是 capability／logic reference；六項完成後才進舊 UI removal Decision Gate；「新版比較漂亮」不是刪除理由 | 凍結與刪除前置**已存在於 DEC-019、DEC-020**；**六項前置清單（capability inventory、new UI mapping、implementation、coverage validation、regression、customer approval）與「漂亮不是理由」本則新增**；與 DEC-020 路線取聯集（`PROJECT_RULES.md` 16.5） |
| 17 | 既有個股健檢／替換邏輯須登記為新版必須盤點能力（財報健檢、KD／technical inputs、replacement／rotation、stock trend input、individual stock lights、holdings battle-room integration） | **本則新增**（在 DECISIONS 首次登記）；盤點本體見 `docs/PROJECT_STATE.md` §23（既有能力總表，撰寫組未逐項比對是否涵蓋這六項） |
| 17 | 客戶原文所提「MJ老師」若無 GitHub 證據，不寫成正式來源 | **撰寫組實查**：全 repo `git grep "MJ老師"` 0 命中；repo 只有已去識別化的舊常數前綴 `MJ_*`（`CLAUDE.md` §3.3：v19.174 改名 `FH_*`、舊名保留 alias），**無法證明**與該名稱同一來源 ⇒ 依客戶指示**不寫成正式來源**，只保存「既有個股健檢邏輯」 |
| 20 | 新資料來源研究候選（real market breadth、Sahm、US 2Y、yield spreads、30Y、TIPS、OECD CLI、securities lending、TDCC、ETF distribution／components、market EPS／PE／forward EPS、CSP／AI capex）**不是已授權接入 production**；下一個 AI 不得看到 BACKLOG 就自行換資料源 | 「新／替換 production 來源須 Decision Gate」**已存在於 DEC-009**（`PROJECT_RULES.md` 第 4 節 #3）；候選清單**本則新增為正式「研究候選、非授權」標記**；部分候選已見於 `docs/BACKLOG.md`／`docs/PROJECT_STATE.md`（例：Sahm、OECD、capex），TDCC 撰寫組 grep 0 命中 |

- **⚠️ 衝突待客戶裁示**：撰寫組逐點比對**未發現**與既有正式 DEC 的硬衝突（單組結論，未經第二組驗證，不得當作「已確認無衝突」引用）。
- **⚠️ 待客戶確認（不是 DEC 衝突，是與現行程式／狀態文件的用語差異；本則不解決、不改程式）**：
  1. **指標危險度的定義**：客戶第 8 節原文「指標危險度：目前多少危險條件／門檻被觸發。」；`docs/PROJECT_STATE.md` §22.3 記錄的**現行程式**為 16 盞燈 `shared/macro_buckets.py::BUCKET_DANGER_SPECS` 經 `src/ui/tabs/tab_macro_v2.py::overall_verdict` 取 **worst-of**。「多少條件被觸發」若讀成「觸發計數」即與 worst-of 不同口徑；若只是描述性說法則無差異。屬資料／投資語意（`PROJECT_RULES.md` 第 4 節 #2），⛔ 不得自行改口徑，待客戶確認讀法。
  2. **⚡ 行動例示的射程**：見上表第 6 節 ⚡ 列（`CV1-FU-02`／`CV1-FU-03` 未裁示）。
- **不是什麼**（⛔）：不是動工授權；不是線框核准（DEC-017 五頁仍為現行實作依據，直到新線框經 DEC-003 拍板，同 DEC-072）；不定義台股趨勢／國際趨勢的公式（`VN1-MT-TREND-DEF` 不變）；不核准任何新資料源、公式、門檻、權重或綜合分數；不改 Risk Cap；不授權改或刪舊 UI（DEC-019、DEC-020）；不授權刪 branch（DEC-012）。
- 📌 **2026-10-24 附註（append-only；本條上文一字未改；不是新 DEC；有意識的更新，不是漏刪，決策者 客戶）**：客戶 2026-10-23 Freeze 禁止清單中的「新 Batch」，**僅對 Data Health C1 解除**（DEC-077 第 1 點）；其餘禁止項（VN1-PG、大型研究、改投資公式／權重／門檻、刪舊 UI、刪 branch、不可逆清理、新資料來源、開 production write／Daily Schedule）**不變**。上方「待客戶確認」第 1 點（指標危險度口徑）仍未裁示，DEC-077 的 C1′ 子批**等待其結果**。

### DEC-077｜Data Health 批 2 × VN1-PG 邊界裁示：採方案 C（拆批）；C1 指派（只做資料可觀測性／provenance metadata、零投資輸出變更）；C1′ 等 DEC-076 ①；C2／VN1-PG 另開 Decision Gate；Freeze「新 Batch」只對 C1 解除（客戶 2026-10-24）
> 2026-10-24 追加（第 8 節「收到當輪追加」；ID 照序取下一個未用號，撰寫組寫入前 `git grep -oh "DEC-0[0-9]*" -- docs/DECISIONS.md | sort -u` 實測最大為 DEC-076）。BACKLOG 登記：§1 `DR-2026-10-24-1`；新節 **5.1.10**（`DH-C1-*`、C1′、C2、`RC-VISIBILITY`、`PROXY-SEMANTICS`、研究發現各列）；受影響既有列 `DH-BIAS240-EST`／`DH-PCR-PROXY`／`DH-MACRO-FWD-ASOF`／`DH-REFRESH-STALE`（5.1.7）、`DH-FT-SCHEMA-ASOF`／`DH-JINGQI-STALE-SESSION`（5.1.8）、`DH-LAMP-STALE`／`DH-ADL-PROXY`（5.1.7）、`VN1-PG-L-TWII-DROPNA-LOG`（5.1.4）。研究摘要：`docs/PROJECT_STATE.md` §30。
- **背景**（⚠️ **總管送題摘要、非客戶原文**：總管 2026-10-24 撰寫並送出的 Decision Gate 摘要，經總管轉交撰寫組；以下依該摘要整理，非逐字）：
  - **觸發**：DEC-075 第 4 點的重評條件（批 A＋1' 合併、獨立 QA、CI、main verification）全部成立（main verification 見 DEC-075 2026-10-24 附註）。〔以下研究方法出處：研究結論檔（摘要見 `docs/PROJECT_STATE.md` §30），**不是**送題摘要〕總管派 A（治理文件）、B（程式碼重疊）、D（資料血緣）、E（VN1-PG 失效傳播，沙箱實跑純函式）四組獨立唯讀調查 → 總管交叉比對 → F 組獨立紅隊否證（14 條承重宣稱：9 成立、4 部分成立已修正、1 條由總管以 GitHub Actions API 自查成立）。基準 main `649f7393`。
  - **方案比較**（總管送題摘要）：
    - **A：批 2 先獨立完成** —— 語意風險高（BIAS240／PCR 代理定義未裁示，且牽動台灣 PMI）；Risk Cap 輸入核心程式（`dated_inputs`／`macro_engine_inputs`）至少改兩輪、PCR「往回找」邏輯可能重寫、兩套日期判斷、規則版本可能升兩次；QA 高；rollback 中；不阻塞新 UI。
    - **B：批 2 與 VN1-PG 合併** —— 無重工，但單一大 PR（引用測試檔約 81 個，grep 計數）、QA 最難、rollback 粗（一退全退）；所有資料修復須等 VN1-PG 語意裁示 ⇒ 阻塞。
    - **C：拆分批 2** —— C1 DH-only（零投資輸出變更、Medium、不需線框）現在做；C1′ 指標危險度子批（16 燈新鮮度＋`bias_240` 燈估算值＋`fut_net` 凍結一致性）等 DEC-076 ①；C2＝VN1-PG「Risk Cap 輸入有效性批」（三項 MUST＋PIT 技術缺口＋凍結值＋代理計分規則 BIAS240／PCR／PMI 一次定、規則版本只升一次），C1 後另行指派。語意風險低、重工很小、QA 低、rollback 乾淨、不阻塞新 UI。
    - **總管推薦：C。**
  - **題 1**（總管送題摘要）：是否採方案 C，並只指派 C1（只解除 Freeze「新 Batch」、範圍限 C1；VN1-PG、C1′、C2 仍凍結）？總管推薦：是。
  - **題 2**（總管送題摘要）：Risk Cap 在位階未評估時看不到數字，要不要另開一題？總管推薦：登記為獨立題，排在 C2 之後再出線框（先修 PIT 漏洞再讓數字回主卡）。
  - **送題時標明「現在不必答」**：C1′ 燈號語意（等 DEC-076 ①）；C2 代理計分規則與實作指派（C1 完成後）。
  - 對映（撰寫組讀法）：客戶第 1 點答題 1（採 C、只解除 C1 的「新 Batch」）；客戶第 3 點 A 項答題 2（Risk Cap visibility 列為獨立待決、PIT／C2 後再做 UI Decision Gate、目前不恢復顯示，與總管推薦同向）；客戶第 2 點（C1 三類範圍）、第 3 點 B 項（Proxy semantics）、第 4、5 點為客戶**主動補充**的範圍與程序要求，非送題題目。
- **內容**（客戶原文；經總管轉交，撰寫組未見原件，依總管轉交文字逐字收錄，第 1～5 點全文）：

```
我裁示：

1. 採方案 C

同意總管推薦的拆分方式。

目前只解除 Freeze 中「新 Batch」對 C1 的限制。

C1′

暫不施工，等待 DEC-076「指標危險度」正式裁示。

C2／VN1-PG

暫不施工，後續另開 Decision Gate。

Production write

繼續維持：

"PRODUCTION_WRITE_APPROVED=False"

不得開啟排程或任何 production write。

---

2. C1 核准範圍

本輪只允許三類「資料可觀測性／provenance metadata」工作：

1. ^TWII／VIX 等既有缺值清理路徑：
   
   - 記錄被清掉的缺值筆數；
   - 先完整盤點實際位置，不要只照原 BACKLOG 寫的兩處；
   - 不因此改變資料取得、fallback、燈號或 Risk Cap 行為。

2. PCR：
   
   - 增加每日來源／來源類型標記；
   - 必須能區分正式來源與目前 fallback／proxy 來源；
   - 只記錄，不改計分資格。

3. Macro forward-validation ledger：
   
   - 增加各 input 自己的資料日期／as-of metadata；
   - 保留既有日期欄原本語意；
   - 本輪不得利用新增日期欄改變任何判斷結果。

核心原則：

«C1 只增加「我們知道資料從哪裡來、是哪一天、清掉多少缺值」的能力。»

不得讓 C1 改變：

- Risk Cap 數字
- 市場位階
- 指標危險度
- 16 燈結果
- 健康分
- scoring
- threshold
- weight
- freshness eligibility
- fallback eligibility
- proxy eligibility
- PIT 判斷
- 投資語意

如果實作時發現任何一項無法做到「零投資輸出變更」，立即停下送 Decision Gate，不要硬塞進 C1。

---

3. C1 開工前先修正 SSOT

把本次研究與我的裁示正式寫入 GitHub，不能只存在本對話。

至少同步：

- DECISIONS
- BACKLOG
- HANDOFF
- PROJECT_STATE

並修正你已發現的文件落差：

- DEC-075 的 main verification 已成立；
- BACKLOG／HANDOFF 不得繼續寫「未做」。

另外登記但不要施工：

A. Risk Cap visibility

#910 後 Risk Cap 本身仍有計算，但新 UI 主卡因健康分未評估而看不到。

列為獨立待決問題。

目前不要恢復顯示，等 PIT／C2 處理後再做 UI Decision Gate。

B. Proxy semantics

新增正式待決項：

BIAS240、PCR、台灣 PMI 的 proxy／estimated 語意必須在 C2 開工前一起研究與裁示。

不得先建立「proxy 一律不能計分」或「proxy 一律可以計分」的通則。

C. 其他研究發現

外資期貨凍結值不一致、出口燈 freshness、schema version 文件衝突等，全部登記到正確 backlog，但本輪不要順手修。

---

4. C1 實作方式

先重新做 Model／Effort Gate。

本批建議：

Model：Opus 5.5
Effort：Medium

若你判斷實際施工會跨入 PIT／Risk Cap／投資語意，必須先升級並停下詢問，不得自行擴 scope。

實作後：

1. 跑針對性測試；
2. 跑完整既有 CI／QA；
3. 確認投資輸出 before／after 沒有因 C1 改變；
4. 做獨立 QA；
5. 若全部通過，依既有治理處理 PR；
6. 合併後重新驗證 main；
7. 同步五 SSOT。

不要把 C1′ 或 C2 混入同一 PR。

---

5. 下一階段先不要自動開始

C1 完成後停下。

下一步不是直接做 C2。

請先回報：

- C1 實際完成內容
- PR／main SHA
- CI／QA
- 是否確認零投資輸出變更
- 新發現
- C2 前仍需裁示的事項

尤其 C2 必須正式處理：

«proxy／estimated 的資料契約與計分資格。»

至少一起研究 BIAS240、PCR、台灣 PMI，不得各自零碎決定。

維持 Silent Autonomous Cruise。

中間安全工作不要逐步回報；只有命中停手條件、需要我裁示，或 C1 整批完成時再回覆。
```

- **裁示要點**（撰寫組摘要；以上方原文為準）：
  1. **採方案 C（拆批）**：C1 **已指派＝動工授權**（限下列三類）；C1′ **暫不施工**，等 DEC-076 ①「指標危險度」口徑正式裁示；C2／VN1-PG **暫不施工**，另開 Decision Gate。
  2. **C1 範圍＝三類「資料可觀測性／provenance metadata」**：(i) ^TWII／VIX 等既有缺值清理路徑記錄被清掉筆數（**先完整盤點實際位置**，不只 BACKLOG 原列兩處）；(ii) PCR 每日來源／來源類型標記（能區分正式來源 vs fallback／proxy；只記錄、不改計分資格）；(iii) 總經前進式驗證帳本各 input 自己的資料日期／as-of metadata（保留既有日期欄原語意；不得用新欄改變任何判斷）。
  3. **零投資輸出變更**：C1 不得改變 Risk Cap 數字、市場位階、指標危險度、16 燈結果、健康分、scoring、threshold、weight、freshness／fallback／proxy eligibility、PIT 判斷、投資語意；**任一項做不到 → 立即停下送 Decision Gate**。
  4. **開工前先落盤 SSOT**（DECISIONS／BACKLOG／HANDOFF／PROJECT_STATE），並更正 main verification 文件落差。
  5. **登記不施工**：A. Risk Cap visibility（`RC-VISIBILITY`；PIT／C2 後再做 UI Decision Gate、目前不恢復顯示）；B. Proxy semantics（`PROXY-SEMANTICS`；BIAS240、PCR、台灣 PMI 在 C2 開工前一起研究與裁示；⛔ 不得先建立「一律不計分」或「一律可計分」通則）；C. 其他研究發現登記到正確 backlog、本輪不順手修。
  6. **C1 施工程序**：先重做 Model／Effort Gate（客戶建議 Opus 5.5／Medium；跨入 PIT／Risk Cap／投資語意 → 升級並停下詢問）→ 針對性測試 → 完整 CI／QA → before／after 零投資輸出變更驗證 → 獨立 QA → 依既有治理處理 PR → 合併後驗證 main → 同步五 SSOT；⛔ C1′／C2 不得混入同一 PR。
  7. **C1 完成後停下回報**（實際完成內容、PR／main SHA、CI／QA、是否確認零投資輸出變更、新發現、C2 前仍需裁示事項）；⛔ 不自動進 C2。維持 Silent Autonomous Cruise。
- **不是什麼**（⛔）：
  - ⛔ **不是 C1′／C2／VN1-PG 施工授權**（三者皆暫不施工；C1′ 等 DEC-076 ①、C2／VN1-PG 另開 Gate）。
  - ⛔ **不改 `PRODUCTION_WRITE_APPROVED`**：仍為 `False`（`shared/risk_cap_history_policy.py`，撰寫組 2026-10-24 grep 實查）；⛔ 不開排程、不做任何 production write（DEC-066 F 不變）。
  - ⛔ **不建立 proxy 通則**：本條**沒有**裁示 proxy／estimated 能否計分；BIAS240、PCR、台灣 PMI 留待 `PROXY-SEMANTICS` 一次研究、一次裁示。
  - ⛔ **不恢復 Risk Cap 顯示**：新 UI 主卡看不到 Risk Cap 的現況**維持**，等 PIT／C2 後的 UI Decision Gate（`RC-VISIBILITY`）。
  - ⛔ **Freeze 只對 C1 解除「新 Batch」**：其餘 Freeze 禁止項（VN1-PG、大型研究、改投資公式／權重／門檻、刪舊 UI、刪 branch、不可逆清理、新資料來源、開 production write／Daily Schedule）**不變**。
  - ⛔ **不是「改 `inputs_as_of` 語意」或修 `fetch_adl` 差一日的授權**：C1 只**加欄**；`DH-MACRO-FWD-ASOF` 的「改既有日期語意」半維持未授權。
- **範圍**：治理（指派／Freeze 部分解除）＋資料語意（C1 邊界）｜**日期**：2026-10-24｜**決策者**：客戶｜**狀態**：生效（裁示登記＋**動工授權：僅 C1**）。
- **來源**：D 客戶訊息 2026-10-24（本 session；本檔首次入庫；經總管轉交；確切 UTC 時戳未記錄，只保留日期）。
- **與其他 DEC 的關係**（append-only；撰寫組讀法，單組，⚠️ 待第二組 evidence audit，`CLAUDE.md` §-2 規則 6；舊 DEC 一字不改）：
  - **DEC-075 第 4 點**（批 2 暫不與 VN1-PG 一起指派、重評後另送裁示）：**本條即其重評結果**。DEC-075 範圍邊界「批 2（`DH-BIAS240-EST`／`DH-PCR-PROXY`／`DH-MACRO-FWD-ASOF`／`DH-REFRESH-STALE`）…皆未授權」對 **C1 三類自本條起不再成立**；對 C1′、C2 及其餘批 2 內容**續有效**。取代關係登第 5 節。
  - **DEC-076**（Freeze 指示）：(1) Freeze「新 Batch」禁止**部分解除**（僅 C1）；(2) **C1′ 等待其「待客戶確認」第 1 點（①指標危險度口徑 worst-of vs 觸發計數）**；(3) DEC-076 第 10 節「Risk Cap 保持自己的既有語意、不過度擴張」與 `RC-VISIBILITY`（#910 後新 UI 看不到 Risk Cap）有張力 —— 本條**不解決**，登記待決。
  - **DEC-062 Q5**（代理值只顯示、不計分；同樣適用總經彙總燈）：**不改、不擴張**。台灣 PMI 的 `is_proxy=True` 旗標若照字面套 Q5 會剔除 Required Core（研究發現 2）—— 本條明令**不得先建立通則**，Q5 對 BIAS240／PCR／台灣 PMI 的射程留給 `PROXY-SEMANTICS` 裁示（撰寫組讀法；Q5 原文不變）。
  - **`PROJECT_RULES.md` 16.1／DEC-062 Q5 與本條第 3 點 B 的張力（未調和衝突，依 `PROJECT_RULES.md` 第 14 節登記；`docs/BACKLOG.md` 第 4 節 `CV1-DR-11`）**：16.1「代理值不得以正式資料的身分顯示或計分」、Q5「代理值只顯示、不計分」vs 本條 3B「不得先建立『proxy 一律不能計分』或『proxy 一律可以計分』的通則」。**裁示前 16.1／Q5 原文照舊有效**。本條 3B 的讀法（⚠️ 撰寫組／總管讀法，待客戶確認）＝對 BIAS240 估算、PCR 法人估算、台灣 PMI 標記值，在「它們算不算代理值」本身未裁示前，不得以 16.1 直接套用、也不得反向排除；此題列入 C2 前 `PROXY-SEMANTICS` 一併請客戶裁示。
  - **DEC-070**（盤後版、Q1 同一錨定交易日、Q2 ^TWII 缺棒 Fail-Stop）：**不變**。研究實跑顯示跨日配對（MA5 10-23 配外資期貨 10-21）現判 FRESH 並記 VALID，與 DEC-070 Q1 不符 —— 屬 `VN1-PG-PIT-CONSISTENCY`，歸 C2，本條不施工。C1 的 dropna 筆數 log 是 DEC-070 Q2 證據累積（`VN1-PG-TWII-MISS-FREQ`）的前置，⛔ 不得因此改 Fail-Stop 行為。
  - **DEC-074**（代理廣度不得計分）：不變。
  - **DEC-073**（Model／Effort Gate）：**適用**。C1 開工前須重做 Gate；客戶建議 Opus 5.5／Medium 只是建議，仍須依實際工作判斷；跨入 PIT／Risk Cap／投資語意 → 升級並停手。
  - **DEC-066**（production Gate）、**DEC-048**（Required Core）、**DEC-044**（沿用 7 天）：不變。
  - **DEC-002／DEC-015**（沒指派不動工／Audit 不得順手施工）：對 C1 三類已由本條指派；對研究發現各列（本條第 3 點 C 項「本輪不要順手修」）**續有效**。
  - **DEC-003**（線框 gate）：不變；C1 不涉畫面結構。
- **執行紀錄**（2026-10-24 追加，append-only；本條上文一字未改；**不是新 DEC** —— C1 屬 DEC-077 的執行，不是新裁示；事實部分決策者＝AI 總管（事實更新），「偏離規格」部分＝AI 總管內部技術拍板（`CLAUDE.md` §-1.5.D v3 §03-1），**非客戶裁示**）：
  - 📌 **2026-10-24 C1 已完成並合併**（DEC-077 第 2 點三類，全部 done）：PR #913（https://github.com/linchen-20200325/my-stock-dashboard/pull/913），squash merge `37cf87e6`（完整 `37cf87e6103a72cac45d812fc633ab641f9a6b7b`），PR head `29cd7f3e`。⇒ DEC-077「動工授權：僅 C1」**已執行完畢**；C1′／C2／VN1-PG 仍未授權（DEC-077 第 1 點不變）。
  - **完成內容**（明細見 `docs/BACKLOG.md` 5.1.10 三列）：
    - `DH-C1-NA-DROP-LOG`：11 處 production ^TWII／VIX `dropna` 開始記錄清理筆數，清掉 >0 筆時印一行（筆數算不出來時也會印一行說明；stdout 寫不出去時改寫 stderr）；共用 helper 為新 L0 檔 `shared/na_drop_log.py`。8 處＝`daily_data_fetchers._fetch_single_cached`／`fetch_adl`、`macro_core.fetch_yf_ohlcv`／`_fetch_yf_close_base`、`macro_snapshot.compute_twii_bias`／`fetch_vix_block`、`scripts/update_macro_forward_test._twii_close_and_asof`、`scripts/update_macro_history.fetch_twii_ohlcv`；另 3 處＝`macro_cache_reader.load_twii_close`、`weekly_review_service._macro_lite_lines`、`risk_radar._fetch_cboe_csv`。⚠️「11 處即全部 production 的 ^TWII／VIX `dropna`」的驗證方式＝**兩組盤點交叉（實作組＋QA-A），非形式化窮舉**。
    - `DH-C1-PCR-SRC`：先行指標 df 新增 `_pcr_src` 欄（TAIFEX＝`official`、FinMind-TXO-inst-est＝`proxy_estimate`）；只描述來源、**不是計分資格**，下游不讀。
    - `DH-C1-FWD-LEG-ASOF`：帳本附加四欄 `score_index_as_of`／`inst_as_of`／`adl_as_of`／`li_as_of`；schema 維持 3、`ruleset_hash` 不變（`6c716f5411fb`）；`shared/macro_forward_test_schema.py` 內「per-leg as_of 會再 bump」的預告已加刪除線並註明理由。`date`／`inputs_as_of` 語意不變。
  - **CI**：PR CI＝PR head 29cd7f3e：Fast checks（job 120785311814）success、Slow tests AppTest（job 120788338331）success；run 40064619133。main CI＝main push run 40066433398（PR Check）conclusion=success；Fast job 120790571734 success（05:29:19→05:41:31Z）、Slow job 120792951874 success（05:41:34→05:59:31Z）。⚠️ 依 `PROJECT_RULES.md` 第 7 節，~~**main verification（main SHA＋main CI conclusion）在 main CI 結論回填前不成立**~~ main verification **已成立**（main SHA `37cf87e6`＋main CI success）（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管，事實回填）。
  - **零投資輸出驗證摘要**：before／after 測試（還原鏈到 `1c8c1415`）＋四輪、共五組獨立 QA（A／B／C／D／E）驗證（最終 head 29cd7f3e（只改測試與 docstring）由總管讀 diff＋PR CI 驗證，未再派獨立 QA）：下游 `extract_leading`／`build_engine_inputs`→`calculate_system_state`／`calc_traffic_light`／`compute_five_bucket_summary`／`render_leading_table`／CSV **全部相同**。已知、接受的唯一差異：`src/ui/tabs/tab_macro.py` 約 :463 的 stdout log「有效欄=N」會多 1，**只影響 log**（登記 `docs/BACKLOG.md` `DH-TAB-MACRO-LOG-COUNT`）。
  - **Production**：既有帳本 cron 合併後預期會（程式路徑讀碼成立；GH Actions cron 未實機驗證）把四欄寫進 `signals.parquet` —— 這是**既有寫入多了四欄，不是新的 production write**；`PRODUCTION_WRITE_APPROVED=False` 未動；未新增排程。
  - **限制（未實測）**：Streamlit Cloud、GitHub Actions cron、Windows cp950 都沒有實機跑；外部 API 用 mock。
  - **偏離規格紀錄（AI 總管內部技術拍板，v3 §03-1，非客戶裁示）**：
    - (a) PCR 來源欄名用 `_pcr_src`，不是修復計畫寫的 `選PCR_src` —— 底線開頭會被既有 CSV 匯出排除規則擋掉，避免使用者 CSV 多一欄。
    - (b) 新增 L0 helper `shared/na_drop_log.py` —— 11 處共用一份（SSOT），不在各檔各寫一份。
    - (c) cron（`scripts/update_macro_forward_test.py`）計算四欄處外層再包一層 try：失敗時四欄寫 None、照常寫列 —— 觀測欄不得擋下帳本寫列。
    - (d) 缺值清理位置由 BACKLOG 盤點結果的 8 處補為 11 處（QA-A 盤點補上 `macro_cache_reader.load_twii_close`、`weekly_review_service._macro_lite_lines`、`risk_radar._fetch_cboe_csv`）—— 依客戶原文「先完整盤點實際位置，不要只照原 BACKLOG 寫的兩處」；納入範圍為總管判斷。
  - **新發現（只登記、未施工）**：`docs/BACKLOG.md` 5.1.10 新增 `DH-RS-PREP-DROPNA`、`DH-NONUTF8-PRINT`、`DH-LI-ASOF-SEMANTICS`、`DH-TAB-MACRO-LOG-COUNT`；`src/compute/macro/macro_forward_test.py::leg_as_of_from_inputs`／`scripts/update_macro_forward_test.py::main` 另有 C1 新增的一般中文 print 未走安全列印，見 BACKLOG `DH-NONUTF8-PRINT`（文件 QA 2026-10-24 讀碼發現，總管確認；未實測）。
  - **C1 完成後停下**（DEC-077 第 5 點）：下一步**不是**自動做 C2。C2 前仍需客戶裁示：`DEC076-CONFIRM` ①（指標危險度口徑；C1′ 等它）②（⚡ 行動例示射程）、`PROXY-SEMANTICS`（BIAS240／PCR／台灣 PMI 一起）、`CV1-DR-11`、C2 Decision Gate、`RC-VISIBILITY`（C2 後）—— 見 `docs/BACKLOG.md` §1.1、第 4 節、5.1.10。
  - ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：C1 內容、CI、QA 結論為**總管查證後轉述**；撰寫組只以 `git show --stat 37cf87e6`、`gh api repos/:owner/:repo/pulls/913`（`merged=true`、`merge_commit_sha`、`head.sha`）與 `git grep`（`shared/na_drop_log.py`、`PCR_SRC_COL = "_pcr_src"`、四欄常數）確認，**未重跑測試、未重做 before／after**。

---

### DEC-078｜Minimum Sufficient Effort／Test Scope 規則化；CI Fast／Slow 平行化（客戶 2026-10-24）
> 2026-10-24 追加（第 8 節「收到當輪追加」；ID 取下一個未用號，DEC-077 為前一號）。
- **背景**（總管轉交客戶裁示，兩項）：(A) 小批次常被形式上的嚴謹一律升為 High＋全庫重跑，成本高於風險；(B) CI 的 `slow-tests` 原 `needs: fast-checks`，Fast 跑完才啟動 Slow，整體等待時間被串長。
- **要點**：
  - **A. Minimum Sufficient Effort／Test Scope**：
    1. 安全小批次、純文件、metadata／provenance、純 UI、小型低風險修正，原則上採 Minimum Sufficient Effort，可用 Low／Medium，**優先 targeted tests**，不得因形式上的嚴謹一律升為 High＋全庫重跑。
    2. 下列工作**仍須 High＋完整 QA**：Risk Cap、投資語意、資料有效性、proxy／estimated eligibility、freshness／PIT、投資公式／門檻／權重、L3／跨模組高風險改動。
    3. targeted tests 足以證明低風險修改正確時，不應機械性要求每個小批次都跑最重流程；**但既有 GitHub required checks 不得取消**。
  - **B. CI 平行化**：Fast 與 Slow **同時開始**（`.github/workflows/pr-check.yml` 的 `slow-tests` 移除 `needs: fast-checks`）；Fast 仍 blocking、Slow 仍 informational（`continue-on-error: true` 不變）；目的＝降低不必要的等待；代價＝Fast 早早失敗時 Slow 可能白跑一次 Actions minutes，**客戶接受此 trade-off**。
- **不是什麼**（⛔）：
  - ⛔ 不是「小批次可以不跑 CI」：required checks（Fast）照跑、照 blocking；A 只放寬**本地與 QA 的深度**。
  - ⛔ 不是降低 High 清單的門檻：A 第 2 點所列工作不得援引本條降級。
  - ⛔ 不是把 Slow 改成 blocking，也不是新增／刪除任何 job、改 schedule、改 pytest 指令或 env。
  - ⛔ 不免除 `CLAUDE.md` §-2 派工、獨立稽核與揭露義務（Effort／測試範圍只決定深度，不決定要不要驗）。
  - ⛔ 不改 `PRODUCTION_WRITE_APPROVED`（仍 `False`）。
- **範圍**：治理（工作流程）＋CI 結構｜**日期**：2026-10-24｜**決策者**：客戶｜**狀態**：生效。
- **來源**：客戶訊息 2026-10-24（經總管轉交；撰寫組未見原件，依轉交文字整理，非逐字；確切 UTC 時戳未記錄）。
- **與其他 DEC／條文的關係**（撰寫組讀法，單組，⚠️ 待第二組驗，`CLAUDE.md` §-2 規則 6）：
  - **DEC-059（Minimum Sufficient Effort）／`PROJECT_RULES.md` 9.1**：同向，本條把「小批次不得一律 High」與「targeted tests 優先」明文化；9.1 的 Low／Medium／High 清單**不變**。
  - **DEC-073（Model／Effort Gate）**：不變；本條只補充測試範圍，Gate 照跑。
  - **張力點**：(1) `PROJECT_RULES.md` 第 7 節 DoD 寫「relevant tests」，**未**規定全庫重跑，與本條不衝突；(2) DEC-077 第 6 點 C1 施工程序「完整 CI／QA」是**針對 C1（涉 provenance、需證零投資輸出變更）的個案要求**，不因本條改變；(3) 實務上「小批次」與「第 2 點 High 清單」的邊界須逐批判斷，判斷錯誤方向取嚴（歸 High）。未發現需登記第 14 節的硬衝突。
  - **測試釘住**：`tests/test_batch_z59.py` 以 `wf.split("slow-tests:")[0]` 取 Fast 區段，不依賴 `needs`，不受影響；`tests/test_vn1_prehardening.py` 的 `needs` 僅針對 production_write 類 job（另一份 workflow），無關。

### DEC-079｜預判性 Quota／Context Loss Safe Checkpoint：額度或 context 預判不足時，先落盤 GitHub 再換對話（客戶 2026-10-24）
> 2026-10-24 追加（第 8 節「收到當輪追加」；ID 取下一個未用號，DEC-078 為前一號；落盤前 `grep DEC-079` 全 repo 0 命中）。
- **背景**：既有第 6 節 Safe Checkpoint、第 11 節 Context Lifecycle、第 15 節 Handoff Save Check／Context Loss Check 都以「對話準備結束」為時點；客戶要求把時點前移到「預判不足」，不等額度歸零或 context 被截斷。
- **要點**：
  1. 觸發＝AI 判斷剩餘額度、context、session 壽命或對話容量可能不足以安全完成「下一個完整工作階段」；不得等到歸零／截斷／強制結束。
  2. 動作＝先到最近 Safe Checkpoint，優先把已形成的重要資訊落盤 GitHub：新客戶裁示、已確認研究結論、新發現、風險、未完成事項、main SHA、Open PR、CI 狀態、working tree、未提交內容、worktree、stash、current active work、blocker、下一個唯一 safe point、下一階段建議模型與 Effort。
  3. GitHub 紀錄完成後才換對話／換額度。
  4. 聊天摘要、AI 記憶、handoff prompt 只能作導引，不得成為唯一事實來源。
  5. 目標＝原對話突然不可用時，新 AI 仍可只靠 GitHub 重建正確狀態並繼續。
  6. 客戶另指示：與第 6／11／15 節整合，不另造重複章節；不新增總結檔或 `PROJECT_CONTEXT.md`；不重做 DEC-078／第 17 節。
- **不是什麼**（⛔）：
  - ⛔ 不是新的章節或平行清單：落點為 `PROJECT_RULES.md` 第 11 節一條，第 6、15 節各一行 pointer，清單沿用既有。
  - ⛔ 不是授權把完整聊天紀錄或未裁示想法大量寫入 GitHub（第 15 節第 4 點仍有效）；也不是授權新增總結檔。
  - ⛔ 不改 DEC-078／第 17 節，不改 code／tests／workflow／data。
- **範圍**：治理（交接流程）｜**日期**：2026-10-24｜**決策者**：客戶｜**狀態**：生效。
- **來源**：客戶 2026-10-24 正式裁示（逐字）：「當專案 AI 判斷目前剩餘額度、context、session 壽命或對話容量可能不足以安全完成『下一個完整工作階段』時，不得等到額度歸零、context 被截斷或 session 強制結束才處理交接。應先到最近的 Safe Checkpoint，優先把目前已形成的重要資訊落盤到 GitHub，包括：新的客戶裁示／已確認研究結論／新發現／風險／未完成事項／main SHA／Open PR／CI 狀態／working tree／未提交內容／worktree／stash／current active work／blocker／下一個唯一 safe point／下一階段建議模型／Effort。GitHub 紀錄完成後才換對話／換額度。聊天摘要、AI 記憶、handoff prompt 只能作導引，不得成為唯一事實來源。目標：即使原對話突然不可用，新 AI 仍可只靠 GitHub 重新建立正確狀態並繼續。」
- **與其他 DEC／條文的關係**（撰寫組讀法，單組，⚠️ 待第二組驗，`CLAUDE.md` §-2 規則 6）：
  - **DEC-016（Safe Checkpoint／Context Lifecycle）、DEC-067／DEC-068（第 15 節）**：同向，本條只把觸發時點前移並補差額；清單不變。
  - **DEC-073**：下一階段建議模型／Effort 仍依第 15 節 F 項與第 6 點，建議只是參考。
  - **DEC-078／第 17 節**：不受影響。
  - 未發現需登記第 14 節的衝突。唯一實務張力：「預判」為 AI 自判、無法客觀查證，故規則寫明邊界不清取嚴。

### DEC-080｜C2 Decision Gate 裁示：資料身分／計分契約採方案 2（provenance 與 freshness 分開）；BIAS240 估算、PCR 法人估算不參與 Risk Cap 計分（可顯示＋標示）；台灣 PMI 不套 blanket rule；7 天沿用須揭露（`RC-VISIBILITY` 線框先行）；先 C2a（observability／contract，零投資輸出變更）再 C2b（客戶 2026-10-24）
> 2026-10-24 追加（第 8 節「收到當輪追加」；ID 取下一個未用號，DEC-079 為前一號；落盤前撰寫組 `git grep -n "DEC-080"` 全 repo 0 命中）。BACKLOG 登記：§1 `DR-2026-10-24-2`；§1.1 `PROXY-SEMANTICS`／C2 Gate 列、`DEC076-CONFIRM` 列；第 4 節 `CV1-DR-11`；5.1.10 C2 列（拆 C2a／C2b）、`RC-VISIBILITY`、`PROXY-SEMANTICS`；5.1.7 `DH-BIAS240-EST`／`DH-PCR-PROXY`；5.1.11 `DH-PMI-ISPROXY-INVERTED`、新列 `DH-PMI-PUBLICATION-WINDOW-SPEC`；§F Decision Gates 列。Gate 全文：`docs/vnext/VNEXT_1_0_DECISION_GATES.md` §7（研究證據原文未改，各題加「已裁示」標記）。
- **背景**：DEC-077 第 3 點 B／第 5 點要求 C2 開工前一起研究並裁示 BIAS240、PCR、台灣 PMI 的 proxy／estimated 資料契約與計分資格。總管派三組獨立唯讀研究（A 程式路徑、B 治理文件、C 紅隊行為實證；基準 main `f48b30bf`），整理成 Gate §7（7.1 現行真實契約、7.2 Q1～Q6、7.3 三套方案、7.4 六題），以「總管推薦，待客戶裁示」送題（#916 `e813c5f0` 落盤）。研究要點（⚠️ AI 研究結論，非客戶裁示）：proxy／estimated 對 Risk Cap 的正式契約不存在；BIAS240 <240 日估算值照樣進 Risk Cap 計分；PCR 同欄逐日混源（FinMind TXO 法人估算／TAIFEX）；台灣 PMI `is_proxy` 語意倒置且無讀者；7 天沿用以快照寫入時間計、卡面不揭露。
  - 對映（撰寫組讀法）：客戶第 1～6 點依序答 Gate §7.4 第 1～6 題；結論與總管推薦**同向**，但客戶補了推薦沒有的約束 —— (a) 第 1 點「不得把 data exists、fresh、displayable、scoring eligible、Risk Cap eligible 壓成同一 boolean」；(b) 第 4 點「同一正式序列」限定、「不得自行發明發布期長度」；(c) 第 6 點把 C2a 定義為 observability／contract implementation（推薦稿稱「shadow」），並逐項列出 C2a ⛔ 清單；(d) 額外邊界：DEC-076 ①② 不併入本批。
- **內容**：見下方「來源」逐字原文。
- **要點**（撰寫組摘要；以「來源」原文為準）：
  1. **資料身分／計分契約＝方案 2**（Gate §7.3）：provenance 與 freshness **分開表示**；provenance 至少區分 `official`／`secondary`／`estimated`／`proxy`／`unavailable`；freshness 至少區分 `fresh`／`stale`／`carried_forward`；同時保留 `as_of` 與 `source_id`；⛔ 不得把「資料存在」「新鮮」「可顯示」「可計分」「可用於 Risk Cap」壓成同一個 boolean。（列舉值的實際字串／欄名屬 C2a 技術設計；客戶原文只要求「至少能區分」上列類別 —— 撰寫組讀法。）
  2. **BIAS240 歷史不足時的估算值**：⛔ 不參與 Risk Cap 計分；可顯示；明確標示 estimated／歷史不足；對 Risk Cap 視為 Optional 未評估；⛔ 不得因此阻斷整個 Risk Cap。
  3. **FinMind TXO 法人估算 PCR**：⛔ 不參與 Risk Cap 計分；可顯示；明確標示 `proxy_estimate`；只有符合正式 PCR 契約的資料才可用原 PCR 門檻計分；⛔ 不得把不同量直接套用官方 PCR 的既有 threshold。
  4. **台灣 PMI**：⛔ 不可套用 blanket「proxy 不計分」規則。data.gov.tw／國發會等正式來源應修正為正確 provenance；同一正式序列的 secondary／republished value 可在契約允許下滿足 Required Core，但必須揭露來源；`carried_forward` 舊快照只允許在**正式定義**的發布期／freshness window 內暫時滿足 Core，並顯示「沿用」；超過允許期間 → `unavailable` → Required Core 無效 → 不產生新的 Risk Cap。⛔ 不得自行發明發布期長度；repo 若尚無正式定義，先提出具證據的規格／Decision Gate，不自行定數字（BACKLOG `DH-PMI-PUBLICATION-WINDOW-SPEC`）。**本條不寫任何發布期天數。**
  5. **7 天沿用資訊要揭露**：未來卡面應能看見「沿用的是 N 天前的 Risk Cap」「本次判斷中最舊一筆有效資料日期」「必要的 freshness／carried-forward 狀態」。屬 `RC-VISIBILITY` UI 規格：先出線框／文字草稿；⛔ 未經客戶確認不得直接改正式畫面。
  6. **執行順序：先 C2a，再 C2b**。C2a＝observability／contract implementation：記 provenance、記 freshness、記 as_of、記 eligibility、建立 policy table／schema；⛔ 不得改任何 Risk Cap 分數、門檻、權重或投資輸出。C2a 完成並取得實際觀測結果後，再送 **C2b Decision Gate**；C2b 未經客戶另行裁示，⛔ 不得開始 scoring 行為修改。
  7. **額外邊界**：本次不裁定、不實作 DEC-076 ①（16 燈危險度 worst-of vs 觸發盞數）與 ②（⚡ 行動例示射程），兩題維持 pending、分開處理。
  8. **C2a 屬高風險資料契約批**：建議高能力模型；Effort High；完整相關 QA；必須證明零投資輸出變更。C2a ⛔：改 Risk Cap scoring；改 threshold／weight；改公式；改 Required Core 數量；啟用 production write；開 Daily Schedule；改 `RC-VISIBILITY` 正式 UI；開始 C2b；開始 C1′；順手處理 DEC-076 ①②。
- **不是什麼**（⛔）：
  - ⛔ **不是計分變更授權**：第 2、3 點定的是**目標 policy**（C2a 的 policy table 依此記錄 eligibility）；Risk Cap 計分實際改變屬 **C2b**，未經客戶另行裁示不得開始。C2a 期間 Risk Cap 計分行為**維持現行**（含 BIAS240 估算值、PCR 法人估算值仍照現行程式計分）（撰寫組讀法，依第 6 點「不得改任何 Risk Cap 分數…或投資輸出」＋「C2b 未經我另行裁示，不得開始 scoring 行為修改」）。
  - ⛔ **不是 PMI 發布期長度的裁示**：第 4 點明令不得自行發明；repo 現有的月頻新鮮度規則**總管判定（2026-10-24）：現有規則不構成 DEC-080 第 4 點所稱的「正式定義」**（DEC-029 明文不得自創天數；lag 1 天／緩衝 7 天皆 AI 依程式填寫，非客戶核定）；C2a 對 PMI carried_forward 的 Risk Cap eligibility 記為 `undetermined_pending_spec`、不自定數字；規格提案於 C2a 觀測後與 C2b Gate 一併送客戶（見 BACKLOG `DH-PMI-PUBLICATION-WINDOW-SPEC`）。
  - ⛔ **不是 16 燈／指標危險度的裁示**：第 2 點「不參與 Risk Cap 計分」只管 Risk Cap；16 燈 `bias_240` 燈估算值怎麼處理仍屬 C1′、等 DEC-076 ①。
  - ⛔ **不是 UI 改動授權**：第 5 點只確認揭露需求，正式畫面須先出線框／文字草稿並經客戶確認（DEC-003 ①；`PROJECT_RULES.md` 第 4 節 #7）。
  - ⛔ **不是 production write／Daily Schedule 授權**：`PRODUCTION_WRITE_APPROVED=False` 不變；DEC-066 F 不變；VN1-PG production write 仍禁止。
  - ⛔ **不是 C1′ 授權**，也不處理 DEC-076 ①②。
  - ⛔ **不改 Required Core 數量**（DEC-048 不變）。
  - ⛔ **不授權修改 `CLAUDE.md` §2.1**（上位文件；PMI 來源分級文字若要同步，須另案授權）。
- **範圍**：資料語意（provenance／freshness／eligibility 契約）＋治理（批次指派與順序）｜**日期**：2026-10-24｜**決策者**：客戶｜**狀態**：生效（裁示登記＋**動工授權：僅 C2a**；C2b＝新的待裁示 Decision Gate）。
- **來源**：客戶 2026-10-24 正式裁示（經總管轉交；撰寫組未見原件，依總管轉交文字**逐字收錄，未改寫**；確切 UTC 時戳未記錄，只保留日期）：

```
1. 資料身分／計分契約：採方案 2。
   - provenance 與 freshness 分開表示。
   - 至少能區分 official／secondary／estimated／proxy／unavailable。
   - freshness 至少能區分 fresh／stale／carried_forward。
   - 同時保留 "as_of" 與 "source_id"。
   - 不得把 data exists、fresh、displayable、scoring eligible、Risk Cap eligible 壓成同一 boolean。
2. BIAS240 歷史不足時的估算值：不參與 Risk Cap 計分。
   - 可顯示。
   - 明確標示 estimated／歷史不足。
   - 對 Risk Cap 視為 optional 未評估。
   - 不得因此阻斷整個 Risk Cap。
3. FinMind TXO 法人估算 PCR：不參與 Risk Cap 計分。
   - 可顯示。
   - 明確標示 proxy_estimate。
   - 只有符合正式 PCR 契約的資料才可用原 PCR 門檻計分。
   - 不得把不同量直接套用官方 PCR 的既有 threshold。
4. 台灣 PMI：不可套用 blanket「proxy 不計分」規則。
   - data.gov.tw／國發會等正式來源應修正為正確 provenance。
   - 同一正式序列的 secondary / republished value 可在契約允許下滿足 Required Core，但必須揭露來源。
   - carried_forward 舊快照只允許在正式定義的發布期／freshness window 內暫時滿足 Core，並顯示「沿用」。
   - 超過允許期間 → unavailable → Required Core 無效 → 不產生新的 Risk Cap。
   - 不得自行發明發布期長度；若 repo 尚無正式定義，先提出具證據的規格／Decision Gate，不自行定數字。
5. 7 天沿用資訊：要揭露。
   未來卡面應能看見：
   - 沿用的是 N 天前的 Risk Cap
   - 本次判斷中最舊一筆有效資料日期
   - 必要的 freshness / carried-forward 狀態
   但這屬 RC-VISIBILITY UI 規格：
   - 先出線框／文字草稿
   - 未經我確認不得直接改正式畫面
6. 執行順序：先 C2a，再 C2b。
   - C2a = observability / contract implementation：
     - 記 provenance
     - 記 freshness
     - 記 as_of
     - 記 eligibility
     - 建立 policy table / schema
     - 不得改任何 Risk Cap 分數、門檻、權重或投資輸出
   - C2a 完成並取得實際觀測結果後，再送 C2b Decision Gate。
   - C2b 未經我另行裁示，不得開始 scoring 行為修改。
額外邊界：這次先不要順便裁定／實作：DEC-076 ①：16 燈危險度 worst-of vs 觸發盞數；DEC-076 ②：⚡ 行動例示射程。兩題維持 pending，分開處理，避免和 C2 資料有效性契約混在同一批。
C2a 屬高風險資料契約批：建議高能力模型；Effort：High；完整相關 QA；必須證明零投資輸出變更。
⛔ C2a 不得：改 Risk Cap scoring；改 threshold／weight；改公式；改 Required Core 數量；啟用 production write；開 Daily Schedule；改 RC-VISIBILITY 正式 UI；開始 C2b；開始 C1′；順手處理 DEC-076 ①②。
下一步
先把以上裁示正式落盤：
- "docs/DECISIONS.md"
- "docs/BACKLOG.md"
- "docs/PROJECT_STATE.md"
- "docs/HANDOFF.md"
- "docs/vnext/VNEXT_1_0_DECISION_GATES.md" 將相應 Gate 標示為已裁示，但保留原研究證據
完成 GitHub Verification Gate 後，再開始 C2a。
```

- **與其他 DEC／條文的關係**（append-only；撰寫組讀法，單組，⚠️ 待第二組 evidence audit，`CLAUDE.md` §-2 規則 6；舊 DEC 一字不改）：
  - **DEC-048（Required Core）**：Core 成員與數量**不變**（C2a ⛔ 改 Required Core 數量）。第 4 點「超過允許期間 → unavailable → Required Core 無效 → 不產生新的 Risk Cap」與 DEC-048 既有「Core 任一無效 → 不產生新 cap、讀端沿用 7 天」同向；本條新增的是「PMI 的 secondary／carried_forward 在什麼條件下仍算有效」。
  - **DEC-046／DEC-051（Optional 不阻斷＋卡面揭露）**：第 2、3 點「視為 Optional 未評估」「不得因此阻斷整個 Risk Cap」與兩條同向；BIAS240 估算／PCR 法人估算將來（C2b 後）落入 DEC-051 的「未評估」揭露，且須寫明 estimated／歷史不足、`proxy_estimate` 的原因（BACKLOG `DH-PLAN-22-DRIFT` (c) 指出現行揭露只會寫「未取得」，屬 C2a／C2b 設計須處理的缺口）。
  - **DEC-062 Q5（代理值只顯示、不計分；同樣適用總經彙總燈）**：原文**不改**。本條逐指標裁定其射程：PCR 法人估算（不同量）＝不計分、可顯示，與 Q5 同向；BIAS240 估算（同量近似）另立 `estimated` 類，對 Risk Cap 同樣不計分；台灣 PMI 正式來源與同一正式序列的 secondary **不是**代理值，Q5 不據以剔除其計分（第 4 點）。Q5 對**總經彙總燈**（16 燈）的套用仍依 DEC-076 ①／C1′，本條不涉。
  - **DEC-077**：本條即 DEC-077 方案 C 之下「C2／VN1-PG 另開 Decision Gate」與第 5 點「C2 必須正式處理 proxy／estimated 的資料契約與計分資格」的裁示結果。**3B「不得先建立通則」被遵守**：本條逐指標裁示（BIAS240、PCR、PMI 各自結論），且第 4 點明令 PMI 不得套 blanket rule。DEC-077 第 1 點「C2 暫不施工」自本條起對 **C2a** 不再成立（C2a 已指派）；對 C2b 與 VN1-PG production write **續有效**。Freeze「新 Batch」：DEC-077 只對 C1 解除；本條依客戶「完成 GitHub Verification Gate 後，再開始 C2a」指派；總管確認 Freeze「新 Batch」對 C2a 解除（客戶原文見 DEC-080 來源欄；『Freeze 解除』為總管讀法）；其餘 Freeze 禁止項不變。取代關係登第 5 節。
  - **`CV1-DR-11`（`PROJECT_RULES.md` 16.1／DEC-062 Q5 vs DEC-077 3B）**：**由本條裁示**。暫行讀法（「在算不算代理值未裁示前，不得以 16.1 直接套用、也不得反向排除」）自本條起退場；裁示內容＝BIAS240 估算、PCR 法人估算不參與 Risk Cap 計分但可顯示並標示（與 16.1「不得以正式資料的身分顯示或計分」同向）；台灣 PMI 依正式 provenance 處理、不套 blanket rule。16.1 與 Q5 原文不改。
  - **DEC-029（freshness：月頻最多落後一個正常發布期、不得自創 freshness 天數）／DEC-030（PMI 前月用官方值）**：與第 4 點同向；第 4 點「正式定義的發布期」：**總管判定（2026-10-24）：現有規則不構成 DEC-080 第 4 點所稱的「正式定義」**（DEC-029 明文不得自創天數；lag 1 天／緩衝 7 天皆 AI 依程式填寫，非客戶核定）；規格待 C2a 觀測後隨 C2b Gate 送客戶（`DH-PMI-PUBLICATION-WINDOW-SPEC`）。
  - **DEC-044（沿用 7 天）**：天數不變；第 5 點只要求揭露。改以輸入 as-of 起算仍屬另題（Gate §7.2 Q4），本條未裁示。
  - **DEC-076 ①②**：**維持 pending**、分開處理（客戶額外邊界）；C1′ 仍等 ①。
  - **DEC-003（線框 gate）**：第 5 點適用（`RC-VISIBILITY` 先線框）。
  - **DEC-066／DEC-070**：不變；C2a ⛔ production write、Daily Schedule。
  - **DEC-073／DEC-078 A-2**：C2a 屬「資料有效性、proxy／estimated eligibility、freshness／PIT」→ High＋完整 QA，與客戶建議一致；新對話仍須依 `PROJECT_RULES.md` 第 9.0 節重新判斷。
  - 未發現需登記 `PROJECT_RULES.md` 第 14 節的新衝突。
- **執行紀錄**（2026-10-24 Safe Checkpoint 追加，append-only；本條上文一字未改；**不是新 DEC**；事實部分決策者＝AI 總管（事實更新））：
  - 本條裁示已落盤合併：PR #917（squash `f9c76087`）。
  - **C2a-1 已完成**：PR #918（squash `74dc891d`；main CI run 40085401541 success；撰寫組 `git fetch`＋`gh api` 實查）—— 兩軸契約層（`shared/input_provenance_policy.py`、`src/compute/macro/input_provenance.py`），只新增、**未接線**、零投資輸出變更。C2a-1／C2a-2 切分出自 PR #918 描述，屬總管技術切分（`CLAUDE.md` §-1.5.D v3 §03-1），**非客戶裁示**。
  - ~~**C2a-2 未開始**~~（Safe Checkpoint 時點事實；已過時，見下一點（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）））（接線觀測：`src/services/risk_cap_apply.py` 寫檔分支附加觀測欄）；前一對話本機草稿未提交、已遺失，須重新實作；要求與稽核發現見 `docs/BACKLOG.md` 5.1.10 C2a-2 列。C2b 仍待 C2a-2 觀測後送題；`PRODUCTION_WRITE_APPROVED=False` 未動。
  - **C2a-2 實作完成、待合併**（2026-10-24 追加，append-only；事實部分決策者＝AI 總管（事實更新））：客戶 2026-10-24 指示（經總管轉交）：「同意，請切換到 Effort High 後開始 C2a-2…完成 C2a-2 後停手，不自動進 C2b。」—— 屬本條 C2a 授權的執行指示，**不是新裁示**。PR #920（branch `claude/determined-euler-32xqjn`；首個 commit `981e2f69`，另有 QA 修正 commit~~，SHA 見 PR #920~~ `dc2fa365`（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）））：`src/services/risk_cap_apply.py::compute_and_lock_risk_cap` 只在**三道閘門後的寫檔分支**，於本機 `risk_cap_state.json` 與 `macro_state.json` 附加純觀測欄 `input_provenance_shadow`（`shadow_policy_version`＝`c2a-shadow-1`）；未寫檔輪次不記錄；失敗只記 `{"_error", "_stage"}`、不改寫檔成敗。狀態（撰寫組 2026-10-24 21:47 台北 `gh api` 實查）：獨立 QA 兩組判可合併（總管轉述）、`981e2f69` CI Fast＋Slow success、PR open／未合併；**合併與 main CI 以 GitHub 為準，由總管合併後另行驗證**（撰寫時未合併）。⛔ 未變：Risk Cap 數值、計分資格、Required Core、門檻／公式／權重、`RISK_CAP_RULESET_VERSION`、`ENGINE_SOURCE`、`is_proxy`、`PRODUCTION_WRITE_APPROVED=False`、Google Sheet 寫入、UI。**C2b 未開始**（客戶：C2a-2 後停手）；細節與新發現見 `docs/BACKLOG.md` 5.1.10 C2a-2 列、5.1.12。

### DEC-081｜📊 大盤頁 Decision Gate 裁示（Q1＝C 接替今天頁、Q2-1 放／Q2-2 放（卡面措辭客戶自訂）／Q2-3 移除、Q3＝A、Q4＝C 分流）＋新增正式產品要求「互動控制完整性」（新版不能只「看」，必須能「操作」）（客戶 2026-10-25）
> 2026-10-25 追加（第 8 節「收到當輪追加」；ID 取下一個未用號，DEC-080 為前一號；落盤前撰寫組 `git grep -n "DEC-081"` 全 repo 0 命中）。BACKLOG 登記：§1 `DR-2026-10-25-1`；5.1.6 `VN1-MT-HOME`／`VN1-MT-IA`／`VN1-MT-TREND-DEF` 補註；新增 5.1.13（`UIX-INTERACTION-COVERAGE`、`UIX-ME-SHEET-SSOT`、`UIX-HOLD-DEADEND`、`UIX-FIND-INPUTS`、`UIX-DATACENTER-CONTROLS`、`UIX-ACTION-PAGE`；寫入前 `git grep` 0 命中）。PROJECT_STATE：§35。Gate 全文：`docs/vnext/MARKET_PAGE_DECISION_GATE_2026-10-24.md`（只改狀態頭，研究／線框原文未改）。
- **背景**：總管以 `docs/vnext/MARKET_PAGE_DECISION_GATE_2026-10-24.md`（v4）§6 送 Q1～Q4（Q2 含三個可組合小題），總管推薦 Q1＝C、2-1 放、2-2 放、2-3 移除、Q3＝A、Q4＝C。客戶同輪另提一條**總管未送題**的正式產品要求（互動控制完整性）。
  - 對映（撰寫組讀法）：Q1～Q4 結論與總管推薦**同向**，但客戶補了推薦沒有的約束 —— (a) Q1「在新版大盤頁正式驗收完成前，舊今天頁不得刪除」；(b) Q2-1 明寫「missing／unavailable／未評估必須明寫；不得把 missing 當中性」；(c) **Q2-2 卡面措辭由客戶自訂**（「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」），**取代** Gate 檔 §5.1／Q2-2 的卡面措辭（「獨立顯示待 RC-VISIBILITY；上限有效時，數字會出現在『能不能出手』卡；每次更新的報告也會列出本次寫入值」）；(d) Q2-3「移除的是新版 UI 元件，不代表刪除其底層舊能力或歷史程式」；(e) Q4 分流清單由客戶逐頁列出（與 Gate Q4 方案 C 文字不完全相同，**以客戶清單為準**）；(f) 互動控制完整性為新增要求（非送題）。
- **內容**：見下方「來源」逐字原文（摘錄）。
- **要點**（撰寫組摘要；以「來源」原文為準）：
  1. **Q1＝C**：新版「📊 大盤」接替目前主頁的大盤功能；今天頁現有的大盤相關能力搬入新版大盤；「作戰室／今天要做什麼」移往未來的 ⚡ 行動。📊 大盤回答「現在市場環境如何？目前適合承擔多少風險？」；⚡ 行動回答「今天有哪些事情值得我採取行動？」。⛔ 新版大盤頁正式驗收完成前，舊今天頁不得刪除。
  2. **Q2-1 結論句＝放**：維持首屏先給結論；每個判斷保持獨立語意；⛔ 不得用「但／因此」硬做因果；可用「；」並列；missing／unavailable／未評估必須明寫；⛔ 不得把 missing 當中性。
  3. **Q2-2 Risk Cap 卡位＝放（先保留位置）**：⛔ 不顯示尚未核准的 Risk Cap 獨立數字；卡片顯示「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」；⛔ 不要為了填滿卡片而自行推導值；未來通過後再接正式值，不需重改整頁 layout。
  4. **Q2-3 三欄摘要＝移除**（理由：位階重複、風險與危險度／Risk Cap 語意重複、動能未接線）。「移除的是新版 UI 元件，不代表刪除其底層舊能力或歷史程式。」
  5. **Q3＝A**：台股／國際趨勢卡只顯示「尚未定義」；⛔ 不要自行挑年線／均線／漲跌幅／外資／國際指數代替趨勢結論（「因為『挑哪些指標』本身就是趨勢模型的一部分」）；原始客觀資料可放第 3 層；正式定義另走 `VN1-MT-TREND-DEF`。
  6. **Q4＝C 分流**：📊 大盤（市場位階、指標危險度、台股原始市場資訊、國際市場、總經／景氣、籌碼、Risk Cap 未來入口、判斷依據／來源）；🩺 資料中心（資料健康、freshness、provenance、更新狀態、API／來源狀態、缺值與抓取異常、資料維護工具）；⚡ 行動（作戰室、今天值得處理的事項、可行動訊號）；🎯 標的（選股、個股搜尋、板塊、候選標的、個股健康檢查）；🛡️ 持股（我的持股、曝險、集中度、組合健康、資產配置／壓力測試）；舊 UI 歷史綜合結論句**暫不搬、也不刪**。
  7. **新增正式產品要求「新版不能只『看』，必須能『操作』」**：新版 UI 完工條件**必須包含「互動控制完整性」**——不能缺按鈕、輸入框、搜尋、Sheet 選擇、持股綁定、更新操作。各頁互動承接：
     - **👤 我的**：Google 登入／登出、登入狀態、Sheet 連線狀態、Sheet URL/ID 輸入＋貼完整 URL 自動解析 ID、可用 Sheet 清單、選擇／綁定／切換 Sheet、重新讀取；優先沿用既有 backend／service。
     - **🛡️ 持股**：顯示目前綁定 Sheet、明確入口去「我的」設定、重新載入、資料狀態、缺 Sheet 引導；⛔ 禁止 dead-end（「請選 Sheet 但此頁無處可選」）。
     - **🎯 標的**：名稱／代號搜尋、執行按鈕、帶入我的持股、批次分析入口、舊 UI 未映射的輸入。
     - **📊 大盤**：更新／重新整理、資料中心入口、展開理由、問 AI／查看依據；⛔ 不得塞 Sheet CRUD。
     - **🩺 資料中心**：資料更新、來源／健康、必要資料維護；Sheet 建立／刪除若屬資料維護可評估放此，但不與日常「選哪個持股 Sheet」混在一起。
  8. **Sheet CRUD 不可照搬三套**：先確認既有 backend／service 能否共用、設計單一 SSOT 流程；⛔「本批不得因整理 UI 而刪除舊 Sheet CRUD」；須 Old capability → New coverage → regression → customer verification → removal Decision Gate 後才可刪舊 UI。
  9. **Effort**：本批 Opus 5.5／Medium；遇 Risk Cap 正式顯示、投資語意、eligibility、formula／threshold／weight、Google OAuth security、credential、Sheet 寫入、權限模型、L3、新外部來源、不可逆刪除 → 停在安全點、告知升 High。
  10. **本批禁止（⛔）**：開始 C2b；顯示未核准 Risk Cap 獨立數字；改 Risk Cap 計算／scoring eligibility／Required Core／公式／權重／門檻；自行定義趨勢；新增 EPS 來源；刪舊 UI；大規模刪 code；改 production write／`PRODUCTION_WRITE_APPROVED=False`。
- **不是什麼**（⛔）：
  - ⛔ **不是 Risk Cap 顯示授權**：Q2-2 只核准「先保留卡位」與卡面措辭；獨立數字、7 天沿用揭露等仍屬 C2b＋`RC-VISIBILITY` Gate（DEC-077 3A、DEC-080 第 5、6 點不變）。
  - ⛔ **不是趨勢定義**：Q3 只定「尚未定義」的顯示；`VN1-MT-TREND-DEF` 仍 blocked-on-customer。
  - ⛔ **不是舊 UI 刪除授權**：舊今天頁、舊 Sheet CRUD、舊 UI 歷史綜合結論句一律不刪（DEC-019／020、`UIM-REMOVAL-GATE` 前提不變）。
  - ⛔ **不是 DEC-076 ①② 的裁示**（16 燈危險度口徑、⚡ 行動例示射程維持 pending）；⚡ 行動頁承接作戰室屬方向，實作仍待指派（`UIX-ACTION-PAGE`）。
  - ⛔ **不是 Sheet 寫入／OAuth／權限模型變更授權**：第 7、8 點的互動承接屬「完工條件」；涉及 Sheet 寫入、Google OAuth security、credential、權限模型者依第 9 點升 High、停在安全點（撰寫組讀法）。
  - ⛔ **不是 production write／Daily Schedule 授權**：`PRODUCTION_WRITE_APPROVED=False` 不變；DEC-066 F 不變。
- **範圍**：UI／IA（大盤頁線框裁示、頁面分流）＋產品完工條件（互動控制完整性）＋治理（本批 Effort 與禁止清單）｜**日期**：2026-10-25｜**決策者**：客戶｜**狀態**：生效（Q1～Q4 裁示登記＝大盤頁線框 DEC-003 ① gate 對 Q1～Q4 所及範圍通過；**大盤頁實作批進行中**（總管轉述，撰寫組未查 PR）；互動控制完整性自本條起為每個新 UI 頁的完工條件）。
- **來源**：客戶 2026-10-25 正式裁示（經總管轉交；撰寫組未見原件，**只收到總管轉交的關鍵句**，依轉交文字**逐字收錄，未改寫**；非全文；確切 UTC 時戳未記錄，只保留日期）：

```
Q1 裁示 C：
「新版『📊 大盤』接替目前主頁的大盤功能。今天頁現有的大盤相關能力搬入新版大盤；『作戰室／今天要做什麼』移往未來的 ⚡ 行動」
大盤頁回答「現在市場環境如何？目前適合承擔多少風險？」
⚡ 行動回答「今天有哪些事情值得我採取行動？」
「在新版大盤頁正式驗收完成前，舊今天頁不得刪除。」

Q2-1 放：維持首屏先給結論；每個判斷保持獨立語意；不得用「但／因此」硬做因果；可用「；」並列；missing／unavailable／未評估必須明寫；不得把 missing 當中性。

Q2-2 放：先保留位置，不顯示尚未核准的 Risk Cap 獨立數字；卡片顯示「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」；不要為了填滿卡片而自行推導值；未來通過後再接正式值，不需重改整頁 layout。

Q2-3 移除三欄摘要（位階重複、風險與危險度／Risk Cap 語意重複、動能未接線）；「移除的是新版 UI 元件，不代表刪除其底層舊能力或歷史程式。」

Q3 A：卡片只顯示「尚未定義」；不要自行挑年線／均線／漲跌幅／外資／國際指數代替趨勢結論，「因為『挑哪些指標』本身就是趨勢模型的一部分」；原始客觀資料可放第 3 層；正式定義另走 VN1-MT-TREND-DEF。

Q4 C 分流：
📊 大盤（市場位階、指標危險度、台股原始市場資訊、國際市場、總經／景氣、籌碼、Risk Cap 未來入口、判斷依據／來源）
🩺 資料中心（資料健康、freshness、provenance、更新狀態、API／來源狀態、缺值與抓取異常、資料維護工具）
⚡ 行動（作戰室、今天值得處理的事項、可行動訊號）
🎯 標的（選股、個股搜尋、板塊、候選標的、個股健康檢查）
🛡️ 持股（我的持股、曝險、集中度、組合健康、資產配置／壓力測試）
舊 UI 歷史綜合結論句暫不搬、也不刪。

新增正式產品要求「新版不能只『看』，必須能『操作』」：
新版 UI 完工條件必須包含「互動控制完整性」——不能缺按鈕、輸入框、搜尋、Sheet 選擇、持股綁定、更新操作。
👤 我的：Google 登入／登出、登入狀態、Sheet 連線狀態、Sheet URL/ID 輸入＋貼完整 URL 自動解析 ID、可用 Sheet 清單、選擇／綁定／切換 Sheet、重新讀取；優先沿用既有 backend/service。
🛡️ 持股：顯示目前綁定 Sheet、明確入口去「我的」設定、重新載入、資料狀態、缺 Sheet 引導；禁止 dead-end「請選 Sheet 但此頁無處可選」。
🎯 標的：名稱／代號搜尋、執行按鈕、帶入我的持股、批次分析入口、舊 UI 未映射的輸入。
📊 大盤：更新／重新整理、資料中心入口、展開理由、問 AI／查看依據；不得塞 Sheet CRUD。
🩺 資料中心：資料更新、來源／健康、必要資料維護；Sheet 建立／刪除若屬資料維護可評估放此，但不與日常「選哪個持股 Sheet」混在一起。

Sheet CRUD 不可照搬三套：先確認既有 backend/service 能否共用、設計單一 SSOT 流程；「本批不得因整理 UI 而刪除舊 Sheet CRUD」；須 Old capability → New coverage → regression → customer verification → removal Decision Gate 後才可刪舊 UI。

Effort：本批 Opus 5.5／Medium；遇 Risk Cap 正式顯示、投資語意、eligibility、formula/threshold/weight、Google OAuth security、credential、Sheet 寫入、權限模型、L3、新外部來源、不可逆刪除 → 停在安全點、告知升 High。

本批禁止：開始 C2b、顯示未核准 Risk Cap 獨立數字、改 Risk Cap 計算／scoring eligibility／Required Core／公式／權重／門檻、自行定義趨勢、新增 EPS 來源、刪舊 UI、大規模刪 code、改 production write／PRODUCTION_WRITE_APPROVED=False。
```
（⚠️ 上方為總管轉交的關鍵句，部分條目由總管以條列轉述；若日後取得客戶原件，以原件為準、本段以刪除線更正。）

- **與其他 DEC／條文的關係**（append-only；撰寫組讀法，單組，⚠️ 待第二組 evidence audit，`CLAUDE.md` §-2 規則 6；舊 DEC 一字不改）：
  - **DEC-003 ①（線框 gate）／`CLAUDE.md` §-1.5.D v3 §03-2 ①**：本條為大盤頁文字線框（Gate 檔 §1）在 Q1～Q4 所及範圍的客戶拍板；Gate 檔未經裁示的部分（§5 被卡住清單 G*）仍各自另開 Gate。
  - **DEC-057（首頁不是 Dashboard）／DEC-062 Q1（今天頁）／DEC-072（📊 大盤首屏先給結論）**：Q1＝C 裁定「接替」：今天頁的大盤能力併入 📊 大盤、作戰室移 ⚡ 行動；撰寫組讀為與 DEC-057 同向（作戰室不留在大盤首屏）。`VN1-MT-HOME` 的 Gate 題由本條裁示。
  - **DEC-020（先並存、驗收後才切換）／DEC-019（舊 UI 凍結）**：Q1「舊今天頁不得刪除」與第 8 點「不得刪除舊 Sheet CRUD」同向；`UIM-REMOVAL-GATE` 前提不變。
  - **DEC-074 B／DEC-075 (a)（不得補結論、不得靜默 fallback）**：Q2-1「missing／unavailable／未評估必須明寫；不得把 missing 當中性」同向；結論句不因保持「先給結論」而補位階結論（撰寫組讀法；Gate 附錄 B2 的讀法維持）。
  - **DEC-077 3A／DEC-080 第 5、6 點（RC-VISIBILITY、C2b）**：Q2-2 只保留卡位、不顯示數字，同向；卡面措辭點名「C2b＋RC-VISIBILITY Gate」。
  - **2026-09-05 客戶核准今天頁線框的三欄摘要「位階／動能／風險」**：由 Q2-3 移除（新版 UI 元件）；底層能力與歷史程式不刪。見第 5 節取代鏈新增列。
  - **`VN1-MT-TREND-DEF`**：維持 blocked-on-customer；Q3 與其 next action「未定義前不得在畫面或程式宣稱『台股趨勢』結論」同向。
  - **DEC-076 ①②**：維持 pending（本條未裁）。
  - **DEC-073／DEC-078（Minimum Sufficient Effort）**：第 9 點為本批具體 Effort 指定與升級觸發；新對話仍須依 `PROJECT_RULES.md` 第 9.0 節重新判斷。
  - **EX-OAUTH-1（`CLAUDE.md` §8.2.A.1；`src/data/portfolio/oauth_state.py`、`gsheet_portfolio.py`）**：第 7、8 點「優先沿用既有 backend／service」「單一 SSOT 流程」與既有 L1 OAuth／Sheet 模組相關；是否可共用屬 `UIX-ME-SHEET-SSOT` 盤點，撰寫組未查證。
  - 未發現需登記 `PROJECT_RULES.md` 第 14 節的新衝突（撰寫組單組 grep，未經第二組驗證）。

### DEC-082｜所有下一頁先草稿、後施工：新主要頁面／重大互動流程一律 Stage A 唯讀盤點 → Stage B 新版設計草稿 → Stage C 客戶裁示 Gate → 核准後才 Stage D 正式實作（客戶 2026-10-25）
> 2026-10-25 追加（第 8 節「收到當輪追加」；ID 取下一個未用號，DEC-081 為前一號；落盤前撰寫組 `git grep -n "DEC-082"` 全 repo 0 命中）。摘要見 `docs/PROJECT_STATE.md` §36 末段；交接見 `docs/HANDOFF.md`「📌 2026-10-25 #922 合併後」。
- **背景**：#922（📊 大盤頁實作，DEC-081）合併後，客戶對**之後所有**新主要頁面與重大互動流程立下永久流程規則。
- **要點**（撰寫組摘要；以「來源」原文為準）：
  1. 適用範圍：任何新的主要頁面或重大互動流程 —— 🎯 標的、⚡ 行動、🛡️ 持股、👤 我的、🩺 資料中心、contextual explainability、Sheet 管理／綁定流程、Google 登入／連線流程、跨頁互動控制。
  2. **Stage A｜唯讀盤點**：⛔ Stage A 不得寫正式 UI code。
  3. **Stage B｜提出新版設計草稿**。
  4. **Stage C｜客戶裁示 Gate**：草稿完成後必須停手，等客戶裁示。
  5. **Stage D｜正式實作**：客戶核准草稿後才開始。
  6. 客戶核准草稿前 ⛔ 不得：寫正式頁面、改 navigation、刪舊 UI、替換既有操作流程、開始 OAuth／Sheet write wiring、新增新的正式投資判斷。
- **不是什麼**（⛔）：不是任何一頁的實作授權；不是舊 UI 刪除授權（DEC-019／020、DEC-081 不變）；不是 Sheet 寫入／OAuth／production write 授權（`PRODUCTION_WRITE_APPROVED=False`、DEC-066 F 不變）。
- **範圍**：治理／UI 流程（永久規則）｜**日期**：2026-10-25｜**決策者**：客戶｜**狀態**：生效
- **來源**：客戶 2026-10-25 指示（經總管轉交；撰寫組未見原件，只收到總管轉交的關鍵句，**逐字收錄，未改寫**；「…」為轉交時的省略）：

```
從現在開始：對任何新的主要頁面或重大互動流程…必須遵守：Stage A｜唯讀盤點…⛔ Stage A 不得寫正式 UI code。Stage B｜提出新版設計草稿…Stage C｜客戶裁示 Gate 草稿完成後必須停手…客戶核准草稿後，才進 Stage D 正式實作。
```
（適用範圍與核准前禁止清單為總管轉述：🎯 標的、⚡ 行動、🛡️ 持股、👤 我的、🩺 資料中心、contextual explainability、Sheet 管理／綁定流程、Google 登入／連線流程、跨頁互動控制；核准前不得寫正式頁面、改 navigation、刪舊 UI、替換既有操作流程、開始 OAuth／Sheet write wiring、新增新的正式投資判斷。若日後取得客戶原件，以原件為準、本段以刪除線更正。）

- **與其他 DEC／條文的關係**（撰寫組讀法，單組，⚠️ 未經第二組驗證，`CLAUDE.md` §-2 規則 6）：與 DEC-003 ①／`CLAUDE.md` §-1.5.D v3 §03-2 ①（UI 草稿先行）同向且加嚴（明定四階段與 Stage A 禁寫 UI code）；與 DEC-081 第 7、8 點（互動控制完整性、Sheet CRUD 單一 SSOT）同向，👤 我的等頁的承接須先過本條 Stage C。

### DEC-083｜👤 我的 Stage C 裁示：Q1～Q7 全採 A；Sheet Safety 修復批（B1～B5，High）先於 👤 我的 P1；P1 範圍／P2 排除項；取消唯一本自動綁；dead-end 導向規則；舊 UI Removal Gate；禁止事項（客戶 2026-10-25）
> 2026-10-25 追加（第 8 節「收到當輪追加」；ID 取下一個未用號，DEC-082 為前一號；落盤前撰寫組 `git grep -n "DEC-083"` 全 repo 0 命中）。BACKLOG：5.1.13 `BUG-SHEET-PUBLINK`／`BUG-SHEET-READWRITE`／`UIX-ME-DEADENDS`／`BUG-SHEET-TITLE-SWALLOW`／`UIX-ME-SHEET-SSOT` 狀態補註；新增 `SHEET-SAFETY-B4-SINGLE-WRITER`、`SHEET-SAFETY-B5-CACHE`、`ME-P1`、`ME-P2`（寫入前 `git grep` 0 命中）。PROJECT_STATE：§37。交接：`docs/HANDOFF.md`「📌 2026-10-25 👤 我的 Stage C 已裁示（DEC-083）」。草稿：`docs/vnext/ME_PAGE_DRAFT_2026-10-25.md`（只改狀態行、§0「是否已核准」、§2 F8／§4 M08／§6 S5 加註、§7 逐題加註；盤點／線框原文未改）。
- **背景**：總管依 DEC-082 以 `docs/vnext/ME_PAGE_DRAFT_2026-10-25.md`（Stage A 盤點＋Stage B 草稿）§7 送 Q1～Q7，總管推薦**全部 A**。客戶 Stage C **Q1～Q7 全採 A**，並同輪另給 B～H 段技術與流程指示（**非送題**）。
  - 對映（撰寫組讀法，單組）：Q1～Q7 結論與總管推薦**同向**；客戶另補了推薦沒有、或比推薦更精確的約束 —— (a) Q3 之外，客戶把 Sheet Safety 修復批的範圍**明定為 B1～B5**：草稿 §6 原列為「技術實作，屬內部拍板」的 S1（單一 parser）、S2（單一寫入者）與「只清本人」快取（H8），自本條起是**客戶指定的修復批範圍**；(b) B2 明定 `forward_test_picks` 等不可重建歷史讀取路徑零寫入，「若現有設計無法安全分離：停手送 Decision Gate」；(c) B5 明定「如果 Streamlit 目前架構做不到安全 per-user invalidation：先研究並送 Gate，不得用全域 `.clear()` 假裝完成」；(d) Q5 清除範圍比草稿 A 多明列「會造成登出後重新自動綁回舊 Sheet 的 silent marker」；(e) Q6 legacy 不一致時「不偷偷選 ETF 通道／個股通道、不自動覆寫其中一個、讓使用者在 👤 我的明確重新選定」；(f) C 段**取消唯一本 Sheet 自動綁**（草稿 §6 S5 原寫「移除（或改為『預選但要按 ✅』）」）：「就算 Drive 只有一本：仍要使用者明確按『使用這本』」；(g) D 段 dead-end 指路字樣由客戶自訂；(h) E～H 段（舊 UI Removal Gate、大盤頁、禁止事項、施工順序）為新增流程約束。
- **內容**：見下方「來源」逐字全文（A～H 段）。
- **要點**（撰寫組摘要；以「來源」原文為準）：
  1. **Q1＝A**：側欄新增獨立「👤 我的」，作為 Google 帳號、Sheet 綁定與新版 Sheet SSOT 的**唯一**設定入口。
  2. **Q2＝A（P1 範圍）**：P1 只做 Google 登入／登出／重新登入、Sheet URL／ID、Drive Sheet 清單、明確選擇／切換、重新讀取、active Sheet、active portfolio、active watchlist。**P1 不搬（留 P2，另開 Stage A/B/C Gate）**：建立 Sheet、rename Sheet、刪 Sheet、組合 CRUD、觀察清單 CRUD、持股列 CRUD。P2 完成前保留舊「📁 組合管理」。
  3. **Q3＝A**：正式實作 👤 我的前，先獨立完成 **Sheet Safety 修復批**。
  4. **Q4＝A**：一般 UI 顯示「Sheet 名稱＋ID 末 6 碼」。
  5. **Q5＝A**：登出時同步清除 Google 登入 session、active Sheet binding、URL 上 `sheet` 參數、OAuth state／登入流程攜帶的舊 Sheet ID、會造成登出後自動綁回舊 Sheet 的 silent marker；⛔ 不得登出後自動恢復上一個 Sheet。
  6. **Q6＝A**：組合與觀察清單使用**同一本** active Sheet；legacy 兩者不一致時顯示白話警示、⛔ 不偷偷選 ETF／個股通道、⛔ 不自動覆寫其中一個，讓使用者在 👤 我的明確重新選定。
  7. **Q7＝A**：👤 我的提供新版全站共用 active portfolio／active watchlist；🛡️ 持股／🎯 標的／⚡ 行動等頁只能讀這個共同選擇；⛔ 不得再以「名稱排序第一本」作為不可見的業務決策。
  8. **Sheet Safety 修復批（B 段；優先於 👤 我的 UI；Effort High）**：
     - **B1 Read 真正唯讀**：⛔ read → worksheet 不存在 → create；⛔ read → header／schema 不符 → rewrite 第一列。正確行為：worksheet missing → 明確 `UNAVAILABLE／NOT_CONFIGURED`；schema mismatch → `SCHEMA_MISMATCH`；permission error → 明確 error；empty sheet → `EMPTY`；真正空值維持空值。任何初始化／migration／repair 必須拆成明確 write action，不得藏在 read helper。
     - **B2 Forward-test 歷史**：`forward_test_picks` 等不可重建歷史 read path 零寫入；reconcile／read 不得 create、不得重建 header、不得 rewrite、不得因 schema 不符自行修復；**若現有設計無法安全分離 → 停手送 Decision Gate**。
     - **B3 `/d/e/` 發布連結 BUG（必修）**：建立**單一** Sheet ID parser，不得再保留多份互相不同的 parser 行為；正常編輯網址解析真正 spreadsheet ID；`/spreadsheets/d/e/...` 不得解析成 `e`；若發布網址不能安全轉成可操作 ID → 明確拒絕＋白話錯誤，不得猜測。
     - **B4 Sheet 綁定單一寫入契約**：不得新增第五套綁定邏輯；收斂為一套 parse／sanitize／apply active sheet／clear binding／OAuth restore；legacy key 可暫作 compatibility adapter，新版 consumer 逐步只讀同一 SSOT。
     - **B5 Cache**：重新讀取不得默認清除所有使用者的全域 cache；P1「重新讀取」只失效目前使用者／active Sheet／相關 read cache；**若 Streamlit 架構做不到安全 per-user invalidation → 先研究並送 Gate**，⛔ 不得用全域 `.clear()` 假裝完成。
  9. **👤 我的 P1 Stage D 開工條件（C 段）**：Sheet Safety 批 QA、CI、merge、main verification **全部完成後**才可開始。首屏維持核准草稿方向（① Google 帳號 ② 目前 Sheet ③ 這本 Sheet 內目前分析的組合／觀察清單與哪些頁正在使用）；控制項：登入、登出、重新登入、貼 Sheet URL／ID、Drive 清單、選擇 Sheet、明確「使用這本」、重新讀取、active portfolio selector、active watchlist selector。**唯一本 Sheet 自動綁：取消**（就算 Drive 只有一本，仍要使用者明確按「使用這本」；不要替使用者做綁定決策）。
  10. **Dead-end 修正（D 段；P1 完成後）**：Sheet／登入／切換相關提示 → 統一導向「👤 我的」；需要修改持股／組合／觀察清單內容時（P1 無 CRUD）必須誠實指路：「目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。」⛔ 不得再出現：新版模式看不到的頁面卻叫使用者直接去點、指回自己的唯讀頁、寫著有控制項但實際沒有。
  11. **舊 UI Removal Gate（E 段）**：🚦 今天、📁 組合管理、Google 側欄、Sheet CRUD、legacy controls **全部暫時保留**；刪除條件：capability inventory → Old→New mapping → implementation → interaction coverage → regression → customer verification → Removal Decision Gate，未全部成立不得刪。
  12. **大盤頁（F 段）**：📊 大盤頁仍等待客戶實際 UI 驗收；不阻止本次落盤與 Sheet Safety 批；大盤頁驗收前 ⛔ 不得刪 🚦 今天頁。
  13. **禁止事項（G 段）**：不開始 C2b；不改 Risk Cap；不顯示 Risk Cap 正式數字；不翻 `PRODUCTION_WRITE_APPROVED`；不新增 production source；不修改投資公式／門檻／權重；不動不可重建歷史；不因 read 自動 write；不因 missing 自動建立資料；不因 schema mismatch 自動修資料。
  14. **執行（H 段）**：高能力模型；Silent Autonomous Cruise；Effort High；施工順序：① 落盤本次完整 Stage C 裁示 → ② Sheet Safety 修復批 → ③ 獨立 QA → ④ CI／merge／main verification → ⑤ 👤 我的 P1 → ⑥ P1 獨立 QA → ⑦ CI／merge／main verification → ⑧ 停手回報 → ⑨ 不自行進 P2。
- **不是什麼**（⛔）：
  - ⛔ **不是 P2 授權**：建立／rename／刪 Sheet、組合／觀察清單／持股列 CRUD 須另開 Stage A/B/C Gate（DEC-082）。
  - ⛔ **不是舊 UI 刪除授權**：E 段 Removal Gate 七步未全部成立前一律不刪（DEC-019／020、DEC-081 第 8 點不變）；大盤頁驗收前不刪 🚦 今天（DEC-081 Q1、F 段）。
  - ⛔ **不是新的 Sheet 內容寫入授權**（撰寫組讀法，單組）：B1 要求把初始化／migration／repair「拆成明確 write action」，是把既有藏在 read helper 裡的寫入**移出讀取路徑**；P1 不寫 Sheet 內容，新版 UI 不因此新增寫入控制項（屬 P2）。拆出的 write action 掛在哪個既有寫入路徑，屬 Sheet Safety 批內部技術拍板，須在交付報告揭露。
  - ⛔ **不是不可重建歷史的修復授權**：B2 只要求讀取零寫入；若無法安全分離 → 停手送 Decision Gate，不得自行修資料。
  - ⛔ **不是大盤頁驗收**（F 段）；**不是 C2b／Risk Cap／`RC-VISIBILITY` 授權**；**不是 production write／Daily Schedule 授權**（`PRODUCTION_WRITE_APPROVED=False`、DEC-066 F 不變）；**不是投資公式／門檻／權重變更授權**。
- **範圍**：UI／IA（👤 我的 Stage C 裁示）＋資料層安全修復（Sheet Safety 批 B1～B5）＋治理（施工順序、Removal Gate、禁止事項）｜**日期**：2026-10-25｜**決策者**：客戶｜**狀態**：生效（Q1～Q7 裁示登記＝👤 我的草稿 DEC-082 Stage C 對 P1 範圍通過；**Sheet Safety 批已指派、未開工**；**👤 我的 P1 待 Sheet Safety 批 QA／CI／merge／main verification 完成後才可開始**；P2 未授權）。
- **來源**：客戶 2026-10-25 👤 我的 Stage C 完整裁示（類別 D；經總管轉交為完整文字檔，撰寫組讀取該檔**全文**，**逐字收錄，未改寫、未刪節**；確切 UTC 時戳未記錄，只保留日期）：

```text
客戶 2026-10-25 👤 我的 Stage C 完整裁示（逐字）

A. Q1～Q7 正式裁示

Q1 = A
側欄新增獨立「👤 我的」，作為 Google 帳號、Sheet 綁定與新版 Sheet SSOT 的唯一設定入口。

Q2 = A
P1 只做：
- Google 登入／登出／重新登入
- Sheet URL／ID
- Drive Sheet 清單
- 明確選擇／切換
- 重新讀取
- active Sheet
- active portfolio
- active watchlist
P1 不搬：
- 建立 Sheet
- rename Sheet
- 刪 Sheet
- 組合 CRUD
- 觀察清單 CRUD
- 持股列 CRUD
以上留 P2，另開 Stage A/B/C Gate。P2 完成前保留舊「📁 組合管理」。

Q3 = A
正式實作 👤 我的前，先獨立完成 Sheet Safety 修復批。

Q4 = A
一般 UI 顯示：
「Sheet 名稱＋ID 末 6 碼」。

Q5 = A
登出時同步清除：
- Google 登入 session
- active Sheet binding
- URL 上 "sheet" 參數
- OAuth state／登入流程攜帶的舊 Sheet ID
- 會造成登出後重新自動綁回舊 Sheet 的 silent marker
不得登出後自動恢復上一個 Sheet。

Q6 = A
組合與觀察清單使用同一本 active Sheet。
若 legacy 狀態兩者不一致：
- 顯示白話警示
- 不偷偷選 ETF 通道
- 不偷偷選個股通道
- 不自動覆寫其中一個
- 讓使用者在 👤 我的明確重新選定

Q7 = A
👤 我的提供新版全站共用：
- active portfolio
- active watchlist
🛡️ 持股／🎯 標的／⚡ 行動等頁只能讀這個共同選擇。
不得再以「名稱排序第一本」作為不可見的業務決策。

---

B. Sheet Safety 修復批
此批優先於 👤 我的 UI。
Effort：High。

B1. Read 必須真正唯讀
禁止：
read → worksheet 不存在 → create worksheet
禁止：
read → header/schema 不符 → rewrite 第一列
正確行為：
- worksheet missing → 明確 "UNAVAILABLE / NOT_CONFIGURED"
- schema mismatch → 明確 "SCHEMA_MISMATCH"
- permission error → 明確 error
- empty sheet → EMPTY
- 真正空值維持空值
不得為了「讓讀取成功」自動修改使用者資料。
任何初始化／migration／repair：
必須拆成明確 write action，不得藏在 read helper。

B2. Forward-test 歷史
"forward_test_picks" 等不可重建歷史：
- read path 零寫入
- reconcile/read 不得 create
- 不得重建 header
- 不得 rewrite
- 不得因 schema 不符自行修復
若現有設計無法安全分離：
停手送 Decision Gate。

B3. "/d/e/" 發布連結 BUG
目前發布連結可能解析成 "e"。
正式裁示：
必修。
建立單一 Sheet ID parser。
不得再保留多份互相不同的 parser 行為。
Google Sheets 正常編輯網址：
解析真正 spreadsheet ID。
"/spreadsheets/d/e/..." 發布網址：
不得解析成 "e"。
若發布網址不能安全轉成可操作 spreadsheet ID：
明確拒絕並顯示白話錯誤。
不得猜測。

B4. Sheet 綁定單一寫入契約
新版不得再新增第五套綁定邏輯。
收斂為一套：
- parse
- sanitize
- apply active sheet
- clear binding
- OAuth restore
legacy key 可暫時作 compatibility adapter，但新版 consumer 應逐步只讀同一 SSOT。

B5. Cache
重新讀取不得默認清除所有使用者的全域 cache。
P1 的「重新讀取」目標：
只失效目前使用者／active Sheet／相關 read cache。
如果 Streamlit 目前架構做不到安全 per-user invalidation：
先研究並送 Gate，不得用全域 ".clear()" 假裝完成。

---

C. 👤 我的 P1 Stage D
只有 Sheet Safety 批：
- QA
- CI
- merge
- main verification
全部完成後才可開始。
首屏維持核准草稿方向：
1. Google 帳號
2. 目前 Sheet
3. 這本 Sheet 內目前分析的組合／觀察清單與哪些頁正在使用
控制項包括：
- 登入
- 登出
- 重新登入
- 貼 Sheet URL／ID
- Drive 清單
- 選擇 Sheet
- 明確「使用這本」
- 重新讀取
- active portfolio selector
- active watchlist selector
唯一本 Sheet 自動綁
取消。
就算 Drive 只有一本：
仍要使用者明確按「使用這本」。
不要替使用者做綁定決策。

---

D. Dead-end 修正
P1 完成後：
Sheet／登入／切換相關提示：
→ 統一導向「👤 我的」。
需要修改持股／組合／觀察清單內容：
P1 尚未提供 CRUD，因此必須誠實指路：
「目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。」
不得再出現：
- 新版模式看不到的頁面卻叫使用者直接去點
- 指回自己的唯讀頁
- 寫著有控制項但實際沒有

---

E. 舊 UI Removal Gate
舊：
- 🚦 今天
- 📁 組合管理
- Google 側欄
- Sheet CRUD
- legacy controls
全部暫時保留。
刪除條件仍是：
capability inventory
→ Old→New mapping
→ implementation
→ interaction coverage
→ regression
→ customer verification
→ Removal Decision Gate
未全部成立不得刪。

---

F. 大盤頁
📊 大盤頁仍等待客戶實際 UI 驗收。
但這不阻止：
- 本次 Q1～Q7 裁示落盤
- Sheet Safety 修復批
在大盤頁尚未驗收前：
不得刪 🚦 今天頁。

---

G. 禁止事項
- 不開始 C2b
- 不改 Risk Cap
- 不顯示 Risk Cap 正式數字
- 不翻 "PRODUCTION_WRITE_APPROVED"
- 不新增 production source
- 不修改投資公式／門檻／權重
- 不動不可重建歷史
- 不因 read 自動 write
- 不因 missing 自動建立資料
- 不因 schema mismatch 自動修資料

---

H. 執行與回報
Model：高能力模型
Mode：Silent Autonomous Cruise
Effort：High
施工順序：
1. 落盤本次完整 Stage C 裁示
2. Sheet Safety 修復批
3. 獨立 QA
4. CI / merge / main verification
5. 再做 👤 我的 P1
6. P1 獨立 QA
7. CI / merge / main verification
8. 停手回報
9. 不自行進 P2
```

- **與其他 DEC／條文的關係**（append-only；撰寫組讀法，單組，⚠️ 待第二組 evidence audit，`CLAUDE.md` §-2 規則 6；舊 DEC 一字不改）：
  - **DEC-082（先草稿、後施工）**：本條為 👤 我的草稿的 Stage C 客戶裁示；P1 範圍內的 Stage D 自本條起有授權，但**開工條件**另受 C 段（Sheet Safety 批先完成）拘束；P2 須重走 Stage A/B/C。
  - **DEC-081 第 7、8、9 點**：Q1／Q2 為 👤 我的互動承接的具體範圍；「Sheet CRUD 不可照搬三套」由 B4（單一寫入契約）與 B3（單一 parser）落實；Effort 依 H 段為 High（與第 9 點升 High 觸發同向）。
  - **DEC-081 Q1／DEC-019／DEC-020**：F 段「大盤頁驗收前不得刪 🚦 今天」與 E 段 Removal Gate 同向且加嚴（明列七步）。
  - **`CLAUDE.md` §1（Fail Loud）／v3 §02**：B1 的明確狀態碼（`UNAVAILABLE／NOT_CONFIGURED`、`SCHEMA_MISMATCH`、`EMPTY`）與「真正空值維持空值」同向；`BUG-SHEET-TITLE-SWALLOW`（`get_sheet_title` 吞例外）客戶未逐字點名，撰寫組依 Q4（要顯示 Sheet 名稱）讀為 P1 前置，排程見 BACKLOG 該列。
  - **`CLAUDE.md` §-1.5.F 判定 3(5)**：`forward_test_picks` 屬不可重建歷史；B2 與「刪生產資料須請示」同向，且把「讀取時改寫」也納入禁止。
  - **EX-OAUTH-1（`CLAUDE.md` §8.2.A.1）**：B4 的 OAuth restore、Q5 的 OAuth state／silent marker 清除會觸及 `src/data/portfolio/oauth_state.py`；是否需調整例外登記屬 Sheet Safety 批內部判斷，撰寫組未查證。
  - **DEC-003 ①（線框 gate）**：P1 首屏「維持核准草稿方向」＝草稿 §3 線框在 P1 範圍內通過；P1 實作若偏離線框結構，仍須先出線框。
  - **DEC-066 F／`PRODUCTION_WRITE_APPROVED=False`**：G 段同向，不變。
  - 未發現需登記 `PROJECT_RULES.md` 第 14 節的新衝突（撰寫組單組 grep，未經第二組驗證）。
- 📌 **實作指標：PR #927（👤 我的 P1，~~待合併~~ 已合併 `ab705fbf`（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）））**（append-only；**不是新 Decision**；上文一字未改（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）））：本條 P1 範圍（Q1、Q2、Q4～Q7、C、D 段）的實作在 PR #927（分支 `claude/determined-euler-32xqjn`，撰寫組讀碼基準 `4e8c0876`）；Sheet Safety 批（B1～B5）為 #926，已合併 main `55601f42`。狀態摘要 `docs/PROJECT_STATE.md` §38；殘留 `docs/BACKLOG.md` 5.1.13。
  - **AI 總管實作選擇（依 `CLAUDE.md` §-1.5 內部自決授權所做；⚠️ 是 AI 總管選擇、可由客戶覆核或推翻，⛔ 不是客戶裁示）**（FACT 出處為 `4e8c0876` 程式碼與其註解）：
    1. 「👤 我的」排在導覽**最後**（第 7 頁；`shared/ia_nav.PAGE_LABELS`）—— Q1 只說「側欄新增獨立」，沒說位置。
    2. **沒選定就不分析**，即使這本 Sheet 只有一本組合也一樣（`holdings_service._pick`）—— C 段「只有一本也要明確按『使用這本』」原文講的是 Sheet，延伸到組合／觀察清單是 AI 總管讀法。
    3. active 組合／觀察清單選定**只活在 session**（不寫 Sheet、不寫網址）⇒ 重新整理或重新登入後要重選（`BACKLOG` `NAV-PERSIST`）。
    4. secrets **部署預設 Sheet 在新版 UI 不當 active**（`ACTIVE_DEPLOY_DEFAULT_ONLY`；要使用者按「✅ 使用這本」）—— 與 `SHEET-LOGOUT-SECRETS-DEFAULT`（仍待客戶判斷，舊 UI 行為未變）是兩件事。
    5. 只有部署預設時，🚦「Sheet 綁定」那一格顯示「**尚未綁定 Sheet**」（第 4 點的直接結果）。
    6. 🔍 板塊資金的**持股標示來源改為 👤 我的選定**的組合＋觀察清單（不再讀本 session 的 ETF 組合列與個股通道整本觀察清單）—— Q7 原文列「🛡️ 持股／🎯 標的／⚡ 行動等頁」（草稿 §0「頁名讀法」把 🎯 標的對到現行 🔍 找標的＋🔬 查一檔）；把板塊資金持股標示這一格算進來、並捨棄舊來源，是 AI 總管的實作讀法。
    7. **新版模式側欄**：「✅ Sheet ID」只顯示末 6 碼、貼 ID 框不預填也留不住完整 ID（Q4 延伸到側欄屬 AI 總管讀法）；~~「不使用」模式一字不變。~~ 「不使用」模式畫面行為不變（只在從新版切回時把框重設為目前綁定 ID）（`075e8da7` 起以 Session State API 明確指定框值）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。
  - ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本註由單一撰寫組產出，**沒有第二組驗過**；上列「選擇」清單是撰寫組依 commit 與程式碼註解整理，**不保證窮舉**。

---

## 5. 取代鏈總表

| 舊 | 新 | 關係 | 判讀者 |
|---|---|---|---|
| 2026-10-09〈HANDOFF 維護：A〉「HANDOFF 維持單一 SSOT」（`H:2499`） | DEC-011（DR-2026-10-15-4） | 取代 | 客戶 MSG 3 明示「formal Backlog 與 HANDOFF 分離」 |
| Q-z30「舊 UI 只允許 4 類修正」（HO `d836a2f2`） | DEC-019（2026-10-13 第三則＋第四則更正 A） | 取代 | HANDOFF 編修組（`H:1336`，單組） |
| 第三則「ui_v2/** 唯一」路徑寫法 | DEC-019 第四則〈UI 邊界更正 A〉 | 更正 | 客戶第四則自述「衝突處以此為準」（`H:1334`） |
| DEC-041 Q-z14「部分資料有效時不改模型」 | DEC-048 | 部分取代（新 UI 路徑） | 撰寫組，單組 |
| DEC-043 Q-z35「缺項不計分」 | DEC-048 | 部分取代（Required Core） | 撰寫組，單組 |
| DEC-043 Q-z35 文案「上限可能偏寬」 | DEC-051 | 取代 | 客戶 MSG 6 明示 |
| DEC-008 §五「可以直接進行」最小整合 | DEC-009 | 暫行取嚴 | 撰寫組依 MSG 10 指示取嚴；待 `CV1-DR-08` |
| DEC-010 C 級「文件自驗」 | DEC-016 | 本批覆寫 | 客戶 MSG 10 第 9 點 |
| `CLAUDE.md` §-1.5 v1 | v3 | 封存（v1 未刪） | `CLAUDE.md` 自述 |
| DEC-022「全站不產生任何直接買賣建議」作為全面禁止規則（含 `H:4668` 2026-09-29 三條硬禁令 ① 之同義重申） | DEC-054 | **部分取代**（僅「全面禁止方向性 Action」部分；DEC-022 其餘護欄的逐項效力見 DEC-054 承接表） | 客戶 2026-10-16T16:26Z 明示取代範圍；逐項承接判讀為撰寫組單組 |
| DEC-059／DEC-061「高於所需時主動提醒降級」 | DEC-073 | 部分修訂（改為不需為形式要求降級） | 客戶 2026-10-23 原文明示；範圍為撰寫組判讀，單組 |
| `DH-GATE-BREADTH` 總管推薦 (A) 重新歸一 | DEC-074 | 不採用（客戶裁 B） | 客戶 2026-10-23 原文明示 |
| `DH-GATE-REGIME-FALLBACK` (b)「健康分 ⬜ 但位階退 `macro_state.json` 規則引擎位階」（現況；新 UI 卡③ degraded 照印） | DEC-075 | 不採用（客戶裁 (a)） | 客戶 2026-10-23 原文明示（「不允許…靜默 fallback 到另一套規則引擎產生位階結論」） |
| DEC-074「⛔ 本裁示不是實作授權…仍待客戶指派」 | DEC-075 | 部分取代（批 A＋批 1' 已指派＝動工授權；DEC-074 原文不改；其餘 `DH-*` 仍待指派） | 客戶 2026-10-23 原文明示（「指派批 A」「同意加掛批 1'」） |
| `docs/vnext/DATA_HEALTH_REPAIR_PLAN_2026-10-23.md` 第 3 節總管推薦「批 2 併 `VN1-PG-*` 實作批」 | DEC-075 | 暫不採用（延後重評，邊界待定） | 客戶 2026-10-23 原文明示（「批 2 暫時不要與 VN1-PG 一起指派」） |
| AUD-C22「位階第 3 順位來源本批不動」 | DEC-075 (a) 技術落點 | 語意改寫（health 缺席不再退檔案位階） | 撰寫組，單組；AUD-C22 原文未對照 |
| DEC-075 第 4 點「批 2 暫時不要與 VN1-PG 一起指派…再重新評估批 2／VN1-PG 的最佳邊界」（2026-10-24 新增列） | DEC-077 | 重評結果（採方案 C：C1 指派；C1′ 等 DEC-076 ①；C2 併 VN1-PG 另開 Decision Gate；DEC-075 原文不改） | 客戶 2026-10-24 原文明示（「採方案 C」「同意總管推薦的拆分方式」） |
| DEC-075 效力邊界「批 2…皆未授權」（2026-10-24 新增列） | DEC-077 | 部分取代（僅 C1 三類已指派＝動工授權；C1′／C2／其餘批 2 內容仍未授權） | 客戶 2026-10-24 原文明示（「本輪只允許三類…」） |
| DEC-076／客戶 2026-10-23 Freeze 禁止清單「新 Batch」（2026-10-24 新增列） | DEC-077 | 部分解除（僅對 C1；其餘禁止項不變） | 客戶 2026-10-24 原文明示（「目前只解除 Freeze 中「新 Batch」對 C1 的限制。」） |
| `docs/vnext/DATA_HEALTH_REPAIR_PLAN_2026-10-23.md` 第 3 節總管推薦「批 2 併 `VN1-PG-*` 實作批」（2026-10-24 新增列） | DEC-077 | 改為拆分（批 2 拆 C1／C1′／C2，僅 C2 併 VN1-PG）；計畫檔原文不改 | 客戶 2026-10-24 原文明示＋撰寫組判讀，單組 |
| `CV1-DR-11` 暫行讀法「在 BIAS240 估算／PCR 法人估算／台灣 PMI 標記值算不算代理值未裁示前，不得以 `PROJECT_RULES.md` 16.1 直接套用、也不得反向排除」（2026-10-24 新增列） | DEC-080 | 裁示（暫行讀法退場；16.1／DEC-062 Q5 原文不改；BIAS240 估算、PCR 法人估算不參與 Risk Cap 計分、可顯示＋標示；台灣 PMI 不套 blanket rule） | 客戶 2026-10-24 原文明示（第 1～4 點）；對映 `CV1-DR-11` 為撰寫組判讀，單組 |
| DEC-077 第 1 點「C2／VN1-PG 暫不施工，後續另開 Decision Gate」（2026-10-24 新增列） | DEC-080 | 部分取代（**C2a 已指派＝動工授權**；C2b 未經另行裁示不得開始；VN1-PG production write、Daily Schedule 仍禁止；DEC-077 原文不改） | 客戶 2026-10-24 原文明示（「先 C2a，再 C2b」「C2b 未經我另行裁示，不得開始 scoring 行為修改」） |
| DEC-077／DEC-076 Freeze「新 Batch」只對 C1 解除（2026-10-24 新增列） | DEC-080 | 延伸至 C2a（其餘 Freeze 禁止項不變） | 依客戶「完成 GitHub Verification Gate 後，再開始 C2a」指派；總管確認 Freeze「新 Batch」對 C2a 解除（客戶原文見 DEC-080 來源欄；『Freeze 解除』為總管讀法） |
| Gate §7.2 Q5 總管推薦「需客戶確認『第三方轉載可否滿足 Required Core』」（2026-10-24 新增列） | DEC-080 第 4 點 | 裁示（同一正式序列的 secondary／republished value 可在契約允許下滿足 Required Core，須揭露來源） | 客戶 2026-10-24 原文明示 |
| 今天頁三欄摘要「位階／動能／風險」（客戶 2026-09-05 核准線框；「風險←危險度」為後續裁示）（2026-10-25 新增列） | DEC-081 Q2-3 | 取代（新版 UI 元件移除；底層舊能力與歷史程式不刪） | 客戶 2026-10-25 原文明示（「移除的是新版 UI 元件，不代表刪除其底層舊能力或歷史程式。」） |
| DEC-062 Q1「今天頁」作為主頁（2026-10-25 新增列） | DEC-081 Q1 | 部分取代（主頁大盤功能由新版 📊 大盤接替；作戰室移 ⚡ 行動；新版大盤頁正式驗收完成前舊今天頁不得刪除；DEC-062 原文不改） | 客戶 2026-10-25 原文明示；「部分取代」範圍為撰寫組判讀，單組 |
| `docs/vnext/MARKET_PAGE_DECISION_GATE_2026-10-24.md` §5.1／Q2-2 Risk Cap 卡位卡面措辭「獨立顯示待 RC-VISIBILITY；上限有效時，數字會出現在『能不能出手』卡；每次更新的報告也會列出本次寫入值」（2026-10-25 新增列） | DEC-081 Q2-2 | 取代（卡面改為客戶措辭「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」；Gate 檔原文不改，只改狀態頭） | 客戶 2026-10-25 原文明示 |
| `docs/vnext/ME_PAGE_DRAFT_2026-10-25.md` §7 Q1～Q7 總管推薦（全部 A）＋§0「⛔ 未核准」（2026-10-25 新增列） | DEC-083 | 裁示確認（Q1～Q7 全採 A；草稿狀態改「已裁示 DEC-083」；草稿原文不改，只改狀態頭與 §7 逐題加註） | 客戶 2026-10-25 原文明示（「Q1 = A」～「Q7 = A」） |
| 草稿 §6 S5「單本不自動綁：移除自動綁（或改為『預選但要按 ✅』）」與 §2 F8／§4 M08（2026-10-25 新增列） | DEC-083 C 段 | 裁示（**取消唯一本自動綁**；不論是否預選，綁定都必須由使用者明確按「使用這本」） | 客戶 2026-10-25 原文明示（「唯一本 Sheet 自動綁 取消。就算 Drive 只有一本：仍要使用者明確按「使用這本」。」）；「不論是否預選」為撰寫組讀法，單組 |
| 草稿 §6「Sheet SSOT 提案（技術實作，屬內部拍板）」S1 單一解析器、S2 單一寫入者，及 H8「只清本人」快取（2026-10-25 新增列） | DEC-083 B3／B4／B5 | 升格（內部技術提案 → 客戶指定的 Sheet Safety 修復批範圍，先於 👤 我的 P1；B5 做不到安全 per-user invalidation 須送 Gate） | 客戶 2026-10-25 原文明示（B 段）；對映 S1／S2／H8 為撰寫組判讀，單組 |
| 草稿 Q5 A（登出清三件）與 Q6 A（不一致時「白話警示＋一鍵統一」）（2026-10-25 新增列） | DEC-083 Q5／Q6 | 同向精確化（Q5 另明列 silent marker、⛔ 登出後不得自動恢復；Q6 ⛔ 不偷偷選 ETF／個股通道、⛔ 不自動覆寫，使用者在 👤 我的明確重新選定） | 客戶 2026-10-25 原文明示 |
| DEC-091「待客戶 Design Gate 裁示」狀態（D2.5 設計文件未核准；2026-10-27 新增列） | DEC-092 | 解除（設計方向核准＋Q1～Q6 裁示；DEC-091 原文不改） | 客戶 2026-10-27 原文明示（見 DEC-092 fence） |
| DEC-089 G1＝C 六向導覽；DEC-090 形式 (b) 與 ⚡／🩺 佔位頁文案（2026-10-27 新增列） | DEC-092 Q6 | 部分取代（固定四主導航；D2 殼過渡版保留至四頁替代；DEC-089 其餘項與 HI-1～HI-6 未核准狀態不變；原文不改） | 客戶 2026-10-27 原文明示＋撰寫組判讀範圍，單組 |
| 設計文件 A／C 對 Q1 的總管推薦「以代號（ticker）為準、全站一致」；Q2 圖 B「沿用現有五條」中隱含的結論位；Q3「五桶各取最差一項」；Q5 以營收 YoY 中位數＋覆蓋率定義產業趨勢（2026-10-27 新增列） | DEC-092 Q1／Q3／Q5 | 修改（Q1 改 portfolio_id+symbol；Q3 加「資料不足不得硬選最差」；Q5 僅為候選維度／baseline research，不得定義為正式產業趨勢）；Q2、Q4 大致照推薦 | 客戶 2026-10-27 原文明示 |
| 批 Z51（#838）／Z52（#839）測試語意「缺值／部分失敗時 AI prompt 與修前逐字相同、仍帶『續抱』指示」（DEC-031 同期實作；DEC-100(a) 註明不在範圍）（2026-10-28 新增列） | DEC-101(2) | 部分取代（missing ≠ HOLD；不得以續抱代替缺資料結論；DEC-031 原則與原文不改） | 客戶 2026-10-28（經總管轉交要點）；Z51／Z52↔DEC-031 對應為撰寫組判讀，單組 |
| DEC-100 三項客戶 Gate（`XV-H3`／`XV-H1-EXT`／`XV-ASOF`）「open（待客戶裁示）」（2026-10-28 新增列） | DEC-101(1)～(3) | 裁示（三項皆 A；DEC-100 原文不改） | 客戶 2026-10-28（經總管轉交要點） |

## 6. 未升格項目（證據不足或題意不明 → 見 `docs/BACKLOG.md` 第 4 節）

| BACKLOG ID | 議題 | 為何不升格 |
|---|---|---|
| ~~`CV1-DR-01` ⭐~~ | ~~「全站不產生任何直接買賣建議」（DEC-022）vs MSG 1 §7 Action Layer~~ | ~~字面衝突；客戶從未裁示何者在何範圍優先~~ → **2026-10-16 已裁示、升格為 DEC-054**（客戶訊息 2026-10-16T16:26Z）；本列以刪除線保留 |
| ~~`CV1-FU-01`~~ | ~~`S1-6_COMPLIANCE_COPY_GUIDE.md` 仍以已被部分取代的母法為一切判準的上位~~ | ~~DEC-054 後續；文件未同步（本批不改該檔）~~ → **2026-10-16 已改版結案**（DEC-055；客戶訊息 2026-10-16T22:15Z）；本列以刪除線保留 |
| `CV1-FU-02` | DEC-054 是否延伸至再平衡 Action（DEC-022 再平衡硬禁令：只做偏離提示／客觀對照／情境試算、禁一鍵再平衡按鈕、禁預設最佳配置推薦） | 再平衡為投組層級功能、不在七種 Action 內；暫由 DEC-022 保留（「總管判讀（依 MSG 11 第 1、7 點）」）；禁用語詞表**不在本題**（已判被取代，見 DEC-054 承接表第 4 列）；⚠️ 另含未裁示邊界：DEC-054 允許的**部位層級**「減碼」（可能由 Risk Cap 驅動）與**投組層級**再平衡（承接表第 5 列「只做偏離提示」）的界線未裁示，屬本題 |
| `CV1-FU-03` | DEC-054 七種 Action 是否為封閉清單；與現行 `suggest_action` 語彙（DEC-045：汰弱／停利／巡航…）的關係 | 未裁示 |
| `CV1-FU-04` | DEC-054 第 4、6 點所稱 Thesis、Core Decision／Context Overlay 在本 repo 無正式 DEC／規格 | 只有 `CV1-RC-01` 候選方向 |
| `CV1-FU-05` | AI 層／通用免責「不給任何買賣動作」未區分「模型自己說」與「轉述正式 Action」（S1-6 §3.3、§3.4；舊 UI 通用免責） | 今日無正式 Action，不構成衝突；Action Layer 設計批檢視（2026-10-16 新增） |
| `CV1-FU-06` | `src/config/persona.py` 人設仍要求模型「請給出明確的動作」（既有，產品 code） | 與 DEC-054 第 2、6 點衝突；本批依 DEC-055 第 9 點不改產品 code（2026-10-16 新增） |
| `CV1-DR-02` | QA C 級自驗 vs 獨立稽核 | MSG 10 只覆寫本批 |
| ~~`CV1-DR-11`（2026-10-24 新增，append-only）~~ → **2026-10-24 已裁示（DEC-080）**（有意識的更新，不是漏刪，決策者 客戶；DEC-080）；本列以下原文保留 | `PROJECT_RULES.md` 16.1「代理值不得以正式資料的身分顯示或計分」／DEC-062 Q5「代理值只顯示、不計分」vs DEC-077 第 3 點 B「不得先建立『proxy 一律不能計分』或『proxy 一律可以計分』的通則」 | 未調和衝突（`PROJECT_RULES.md` 第 14 節）；裁示前 16.1／Q5 原文照舊有效；BIAS240 估算、PCR 法人估算、台灣 PMI 標記值「算不算代理值」未裁示，列入 C2 前 `PROXY-SEMANTICS` 一併請客戶裁示 |
| `CV1-DR-03` | 2026-10-01 舊 UI 退場三關是否被 DEC-020 取代 | 未明示 |
| `CV1-DR-04` | PR-f1：`PROCESS.md` §4「存檔 STATE.md」vs 登記本 | 從未裁示 |
| `CV1-DR-05` | handoff 分支在 `docs/HANDOFF.md` 建立後是否算「已安全遷移」 | 未裁示；分支刪除不得自主 |
| `CV1-DR-06` | Q-z39～Q-z41 是否已被 DR-2026-10-16-4／5 吸收 | DR 未逐題宣告 |
| `CV1-DR-07` | S1-6 §6 待客戶確認清單、S2-PRD §7 待拍板清單 | 文件自標待拍板，撰寫組未逐題追答 |
| `CV1-DR-08` | DEC-008 §五「可直接最小整合」vs DEC-009 一律停 | 寬嚴差異未經客戶明示 |
| `CV1-DR-09` | DEC-038「限三類」vs DEC-008 Level 1 可修 | 範圍關係未明示 |
| `CV1-RC-01` | MSG 1 §1～§17 產品方向（Core＋Context、Track A／B、Per-decision Core、Thesis 結構化條件、Decision Log、Storage、Live／Historical 分離、Safe Effective Cutoff、Event Level 1～4、產業雷達、Mobile Read Latest Valid Snapshot、Signal Families） | 客戶自陳為 Audit 方向與「候選策略，不是現在直接寫死的 production rule」；無規格落地 |
| `CV1-RC-02` | 以 `CLAUDE.md` §-1.2、§-1.5.H 為依據的規則 | 該兩節不在 main 的 `CLAUDE.md`；未查 `v2` 分支 |
| `CV1-RC-03` | D-1～D-5（v2 五頁爭點，2026-09-23） | 落地 commit `17998e9`／`aaa8fcf`／`3e91739`／`f6fe758` 只在 `v2`／handoff 分支、**不在 main**（撰寫組 `git merge-base --is-ancestor` 實測） |
| `CV1-RC-04` | 「路線 A：UI 全新重寫」（#663、#665） | 只見 AI 撰寫的 commit 與 `CLAUDE.md` 轉述，無客戶原文 |
| `CV1-RC-05` | Q-z30＝B（開發線 9/21 五個合規 commit 不帶入 main） | 原文只有「B」，題意靠編修組對映 |
| `CV1-RC-06` | 台股資料 MCP server「暫擱」（#574 `ff964410`） | 「暫擱」語意不明、核准者未寫 |
| `CV1-HX-01` | 2026-10-12〈接手自主巡航＋超嚴格靜默〉（`H:934`） | 非逐字，且已被 2026-10-13 版覆蓋；僅歷史 |
| `CV1-HX-02` | 2026-10-15「安全收尾模式」（`H:100`） | 一次性 session 指示；僅歷史 |
| `CV1-HX-03` | `86aa6f01`「風險等級 MEDIUM」（2026-09-23） | 單一 PR 風險評級，非 repo 層 Decision |
| `CV1-HX-04` | v19.112「失敗不進快取」（`d432ca2f`「user 核准提案①+②」） | 技術提案層，已被 `CLAUDE.md` v3 §02 第 3 點涵蓋；只作佐證 |
| （既有 BACKLOG 列） | AUD-C10、C12、C15、C16(a)、C18、C20、C22、C27、C28、AUD-L1～L11、PQ-C4-2、PQ-C3-1 | 已在 BACKLOG 原列，customer decision 欄＝需要／待判；本檔不另立 |
| （handoff 分支） | HANDOFF §6「等你答」25 題等舊待辦 | 尚未遷入；見 BACKLOG `BL-MIGRATE-1` 📌 註 |

## 7. Fact（事實紀錄，不是 Decision）

- **Streamlit floor 1.36 → 1.56**（`fa8e90b7`，2026-08-27）：AI 技術修正，commit 未記客戶裁示；現行宣告以 `requirements.txt` 為準（`CLAUDE.md` §-1.5.D 判定 5）。
- **CBC M1B／M2 發布延遲 ~27 天**（#736 `2a68b558`）：依 EF15M01 實測的事實更正；`CLAUDE.md` §2.3 自註「決策者：AI 總管（事實更正）」。
- **`70416a6a` 是 #852／Z65（2026-10-15）的 commit，不是目前 main**（撰寫組 `git log` 實測；目前 main 見 `docs/HANDOFF.md`）。

## 8. 新增條目規則

- 新客戶裁示：收到當輪追加為下一個 `DEC-NNN`，標來源類別；同時在 `docs/BACKLOG.md` 受影響列的 customer decision 欄引用（沿用該檔 0.3 第 4 條既有慣例：DR 列仍登在 BACKLOG §1，本檔另起 DEC 並互指）。
- 總管技術判斷不得寫成客戶裁示；需要記錄時標「決策者：AI 總管內部」。
- 改動既有條目：舊值以刪除線保留並註明日期與理由。
