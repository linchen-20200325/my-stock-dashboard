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
| **E** | 程式碼註解轉述（2026-10-29 append-only 新增類別；決策者 AI 總管（事實分類，非政策）） | 裁示只存在於 `src/**` 註解或測試 docstring、`docs/**` 0 命中時用；引文為註解字句，**非客戶原訊息**；可信度低於 A～D，與其衝突時以 A～D 為準 |

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
> 📌 **部分取代 BY DEC-084**（2026-10-29 補標記；正文 DEC-084「與其他 DEC 的關係」與 `PROJECT_RULES.md` 第 18.4 節早已載明，本條條頭與第 5 節此前未標；有意識的更新，不是漏刪；決策者 AI 總管（事實更新））：「如果現有能力高於工作所需，不需要為了形式要求客戶降級」一句由 DEC-084 收斂為「只要建議配置不同，升級或降級都必須停手」；其餘（每階段必判、不足時強制停手、不得假設已切換）續有效。
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
> 📌 **G6=A 逐檔戰情表的 L1 欄位集部分取代 BY DEC-122**（2026-11-02 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-122）；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S12）：💼 持股 L1 Holdings Table 欄改為客戶 2026-11-02 §22「代碼、名稱、持股比例、成本、現價、報酬、策略、System Action」；Stage B 草稿欄位集中的張數、市值、健檢等第、235 燈等**下沉 L2**（資訊保留）。**仍有效**：G6「補逐檔戰情表＋展開明細」本身、「欄位僅限已存在事實」、缺值不當 0；G2／G5／G7、7 項補充執行條件、HI-1～HI-6 未核准狀態。兩邊理由：舊欄位集貼近既有燈號事實、最少新語意（仍成立）；新欄位集依客戶明示把持股比例／策略／System Action 拉到第一眼，細節下沉 L2。「策略」欄在 AB-4w（HI-5）前一律 `⬜ 未分類`；~~System Action 詞彙待 DEC-122 Q2。~~ System Action 詞彙依 DEC-122 Q2=A（沿用既有分支原名）（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留）。
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

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S22：§一 Level 3「查看依據」頁內展開；§二「📖憑什麼」頁內展開；「資料健康」本體→MIGRATE 至 👤 資料健康度）** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。
> 📌 **§四「市場狀態：🟢偏多／🟡中性／🔴偏空」部分取代 BY DEC-105 2A；(d)／§九「固定五段輸出」的呈現格式部分取代 BY DEC-109；§一「禁止三要素文字卡同層」與 DEC-111／DEC-112 的張力由 DEC-109 調和**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-105／DEC-109）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：(1) DEC-105 2A「市場位階」五態＋「市場位階，不是台股趨勢」，**不得映射成偏多／中性／偏空**——同一取代也適用 A 規格 `NEWUI_D25_A_FOUR_PAGE_SPEC_2026-10-27.md` §4.1.1 表格（已加註）與 `docs/vnext/d25_wireframes/index.html` 圖例與 `market.html` 首屏圖例（HTML 不改，登記於 supersede map）。(2) AI 投資總結輸出格式改為 DEC-109 二十一（市場一句／持股一句／標的機會一句／主要風險 1～3／本期行動 ≤3，每項附查看依據）；出處鏈＝本條(d)／§九＋A 規格 §5（已加註）＋`ai_summary.html`，經 DEC-092 設計核准承接；分類資料（存股／資本利得／未分類）保留、AI 不得推論分類。(3) §一 客戶原文禁令與 2026-09-24／09-25 只在程式碼註解的「三要素上卡面」裁示此前從未調和，DEC-109「資訊保留、預設下沉」同時滿足兩者。其餘各節仍有效（§一 三層、§二 四主導航、§三 One AI Brain 入口不是第五頁）。
> 📌 **§四「第一列只放 3～4 個核心狀態：…更新：主 CTA」在 📊 市場頁部分取代 BY DEC-117 Q1；§四 圖C 圖上方說明句位置部分取代 BY DEC-117 Q8a**（2026-10-30 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-117）；append-only，本條原文一字未改）：📊 市場頁第一列取 **3** 個核心狀態 tile（市場位階／建議總持股水位／今日主要風險）；**更新改為頁首主 CTA，不再占一張 KPI tile**；手機 2＋1。「3～4」上限語意與「更新＝主 CTA」角色保留（只換位置）；CTA 字樣（§四「🚀 更新市場資料」vs 現行「🚀 更新今日戰情」）不在 DEC-117 範圍（BACKLOG `UIM-UPDATE-BUTTON-WORDING`）。**另：§四 圖C「圖上方『用企業獲利 EPS 搭配不同合理本益比情境…』」在 📊 市場頁由 DEC-117 Q8a 部分取代**——該句移到圖 C 摺疊「為什麼」（逐字保留、只下沉）。§四 其餘不變。
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

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S42：Q3 等「第一層最多 3–5 項；完整燈號與細節留在『查看全部指標／查看依據』」的頁內展開落點；僅限 New UI2）** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。
> 📌 **設計方向核准「每張圖上方有白話說明」在 📊 市場頁圖 C 部分取代 BY DEC-117 Q8a**（2026-10-30 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-117）；append-only，本條原文一字未改）：圖 C（大盤合理區間，Research Framework、零數值）的白話說明句 `CHART_C_SAY` 不再外露於圖上方，移到圖 C 摺疊「為什麼」（逐字保留、只下沉，客戶原文「資訊只能下沉，不得刪除」）；圖 A、國際組、圖 D 的圖上方說明句照舊；本條 Q1～Q6 與其餘設計方向不變。
> 📌 **設計核准中承接之「AI 投資總結五段」呈現格式部分取代 BY DEC-109（R12）**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-109）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：本條 Q1～Q6 裁示**全部仍有效**；本條本文無「五段」字樣，但其「設計方向核准」承接了 DEC-091(d)／A 規格 §5／`ai_summary.html` 的五段格式——該呈現格式由 DEC-109 二十一取代。`docs/vnext/d25_wireframes/*.html` 自 DEC-109 起定為 **Visual SSOT／visual acceptance baseline**（Presentation Contract §14）。
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
> 📌 **已執行完畢**（2026-10-29 補標記；不是 superseded；決策者 AI 總管（事實更新））：本條要求的「UI-T 時整合回單一 🎯 標的頁並移除過渡切換」已由 DEC-107／PR #968（main `9ec555e7`）執行完畢。
> 📌 **第 3 點的「終態不得有任何模式切換」讀法部分取代 BY DEC-122**（2026-11-02 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-122）；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S3）：客戶 2026-11-02 §10／§12 指定 🎯 標的頁最終設計為頁內雙模式「[ 市場精選 ][ 即時查一檔 ]」、不得同時完整展開。**仍有效**：第 1 點（NAV-1 過渡切換不是最終設計）、第 2 點（不視為新增正式 IA）、第 4、5 點、「已執行完畢」歷史紀錄（PR #968）。**⛔ 新雙模式不得回到 NAV-1 葉選擇器（`NAV4_TARGET_LEAF_KEY`、`render_target_leaf_selector`）**——它是頁內元件、不是 IA 層。兩邊理由：舊條防止過渡控制變成永久 IA（仍成立）；新條是客戶對最終設計的明確指定。⚠️「DEC-099 否決的是過渡葉選擇器、不是最終頁內模式」為撰寫組讀法（INFERENCE）。

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

- 📌 **2026-10-29 補註（UI-T；決策者 AI 總管（事實更新）；上文原文保留）**：本條裁示的「過渡切換」已由 UI-T 分支 `uit-impl` 移除（`NAV4_TARGET_LEAF_KEY`／`NAV4_WIDGET_LEAF_KEY`／`render_target_leaf_selector` 等；標的頁成為單一頁）；~~PR #968，見 DEC-107~~ 已合併（PR #968，main `9ec555e7`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）），見 DEC-107。

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

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S42：「完整 methodology 可留在『查看依據』」的頁內落點（外幣不得直接與 TWD 加總之 XV-H3 裁示本身維持）；僅限 New UI2）** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。

> 2026-10-28 補登（ID 取下一個未用號；落盤前 `grep -o 'DEC-[0-9]*' docs/*.md docs/vnext/*.md` 最大為 DEC-100、DEC-101 0 命中）。要點經總管轉交，**非客戶逐字全文**。

- **決策者**：**客戶**（2026-10-28；經總管轉交之要點）。
- **日期／效力日期**：2026-10-28 起生效。｜**狀態**：生效；~~(1)(2) 實作中~~ ~~(1)(2) implementation complete／waiting CI（**未合併**，PR 待開；見下方「實作紀錄」）~~（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）） (1)(2) **已合併 PR #961（squash，main `2e97482c`，CI 綠：Fast checks／Slow tests 皆 success，head `5783a59e`）**（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））、(3) 線框草稿待客戶確認（`docs/vnext/NEWUI_D25_XVIEW_ASOF_WIREFRAME_2026-10-28.md`）。
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
- 📌 **實作紀錄（2026-10-28 補；加法式，上文一字未改；決策者 AI 總管（事實更新））**：~~**狀態＝implementation complete／waiting CI，未合併**（PR 待開；~~ **狀態＝已合併 PR #961（squash，main `2e97482c`，CI 綠：Fast checks／Slow tests 皆 success，head `5783a59e`）**（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（分支 `ccr-fa5b6ded-9rhvoj`；基準 `f3d77703`，`git log f3d77703..HEAD`）。
  - **commit**：`bf622ead`（XV-V1）／`af560a45`（XV-C05）／`fe618e6a`（DEC-101 落盤＋ASOF 線框，docs）／`216faccf`・`b6bb466f`・`b51168d5`（XV-H2-EXT／XV-M1）／`bf4621ef`・`38c821bb`・`485347c6`・`66249bdf`・`27081c96`・`07673760`・`41d6f839`・`9901cd0c`・`8e6958af`・`c882a299`（XV-H1-EXT）／`2bead6ad`・`82889239`・`d21d08a1`・`68233550`・`3c077ee7`・`72f87802`（XV-H3）。
  - **`XV-H1-EXT`（本條 (2)）**：新增 L0 單一判定 `shared/holdings_data_short.py`（`row_data_short`／`total_judged`／`digest_data_short`），收斂 ① 該做什麼 gate、③「未判 N」、⑦ prompt 續抱句、LINE 正文續抱／無需動作句、週報正文與 AI prompt —— 原本各自實作、各漏不同的洞（複驗組 C MAJOR-1/2）。缺資料標的顯示「⬜ 資料不足／無法判定」；**可證明結論（🔴 汰弱／加碼／停利／🟡）保留**，缺現價者另列「缺現價（結論不受影響）」，衛星缺現價寫「停利無法判定」；契約漂移（`MISS_CONTRACT_DRIFT`）**保留原診斷句**（不換 ⬜），但計入資料不足。組合層資料不足時 ⑦／LINE／週報不給「續抱」「今日無需動作」「均無連續落後（續抱觀察）」類 blanket 句。Z51／Z52 測試同步改為新語意（`tests/test_batch_z51.py`、`tests/test_batch_z52.py`、`tests/test_dividend_station_service.py` 等）；新測試 `tests/test_xv_h1ext_missing_not_hold.py`、`tests/test_xv_complete_data_parity.py`。
  - **`XV-H3`（本條 (1)）**：新增 L0 `shared/asset_currency_gate.py`＝**暫行 fail-safe 判定，不是 canonical currency 定義**（正式定義另開 `FX-CANONICAL-GATE`，屆時應被取代而非擴充）。只認 `.TW`／`.TWO` 後綴或純 ASCII 數字 4–6 碼＋可選一個大寫字母為 TWD；排除原因兩種：「外幣資產，匯率與成本幣別未定義」（明確外幣）與「幣別未確認」（其餘）。有排除時所有總額／比例為 `None` 並顯示逐字客戶句「⬜ 部分外幣資產未納入，總市值／配置比例無法完整判定」＋未納入清單；壓測／VaR 以「僅已納入台股部分」標示涵蓋範圍並標失準（全外幣時給 `FX_ONLY_REASON`）；⑤⑥ 外幣排除用既有徽章「不適用 · 重跑無效」；外幣衛星計為停利判不了；外幣列損益% 顯示「—」。新測試 `tests/test_xv_h3_fx_not_summed.py`。
  - **`XV-C05`（本條 (5) 末項）**：`shared/strategy_class_schema.normalize_holding_ticker`＝`strip().upper()`，與 L3 `holdings_service.get_holdings` 逐字一致；不加減後綴、不補前導零、不做 NFKC；非 str → `TypeError`。
  - **`XV-H2-EXT`／`XV-M1`（AI 總管決定，DEC-101(5) 邊界內）**：側欄「🔄 強制刷新數據」除 `st.cache_data.clear()` 外，經 L3 `src/services/force_refresh_service.py` 另清 L1 `macro_core` 的 VIX／Yahoo 收盤（`_YF_CLOSE_CACHE`）與 FRED（`_FRED_CACHE`）**成功**快取；**不清失敗退避表**（v3 §02）；help 據實列出不清的暫存（匯率／台灣總經等仍沿用暫存）。新測試 `tests/test_xv_h2ext_force_refresh_module_caches.py`。
  - **`XV-V1`**：`src/data/etf/etf_fetch.py` 後綴正規化改大小寫不敏感（`.two`→`.TWO`）。新測試 `tests/test_xv_v1_etf_fetch_suffix_case.py`。突變／回退鏈：`tests/test_xvext_revert_chain.py`。
  - **QA**：三組獨立 QA —— A（對抗）、B（語意）、C（複驗，兩輪）；A／B 所報 QA#1～#11 與 C 所報 MAJOR-1～3／MINOR-1～3 皆已回修（見上列 commit 訊息）（總管轉述，撰寫組未重跑測試）。
  - **連動舊 UI（揭露）**：L3 列動作文字（缺資料 → ⬜）與外幣排除也會影響舊 UI 存股戰情室的顯示（**舊 UI 檔未改**）；舊 UI 在外幣持股時顯示錯誤原因句（「持股沒有張數／均價…」類）→ 待客戶裁示 BACKLOG `XV-OLDUI-FX-REASON`（DEC-019）。
  - **未驗**：Streamlit Cloud 實機；真 LINE 推播與真 AI 回覆；客戶 Sheet 實際有無外幣持股。
  - **已知未改**：外幣個股**列層**建議動作文字未改（可能仍顯示「🟢 續抱」；**組合層已不給續抱**）→ BACKLOG `XV-FX-ROW-ACTION`；資料不足單一判定只看持有列，觀察清單不擋組合層 → `XV-WATCHLIST-SCOPE`（已揭露）；LINE VIX 分級行動句在資料不足時是否收 → 待客戶 `XV-LINE-VIX-LINE`。
  - ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本段由 docs-only 撰寫組依 `git log`／`git diff --stat`／docstring 撰寫，未重跑測試、未經第二組驗。
  - 📌 **第四輪回修＋QA 最終結果（2026-10-28 補；加法式，上文一字未改；決策者 AI 總管（事實更新））**（`git log 4014a77f..HEAD`）：
    - `9c26106d`（複驗 C 第二輪 MAJOR-N1）：觀察清單列**判不出**（資料不足、燈或輸入資料異常、契約漂移）**也計入組合層資料不足**；缺現價／外幣仍只看持有列（觀察清單無持倉金額）。**AI 總管決定**，理由：同一則 LINE／⑦ 不得同時列出 ⬜ 清單又說「續抱、定期定額即可」「今日無需動作」；且與 `errors` 及 ① `cruise_or_gap` gate 本來就含觀察清單的口徑一致。L0 新增 `row_short_kind`（判不出／缺現價保留結論／外幣）。
    - `e4742494`（MINOR-A）：契約漂移列**不計入有效判斷檔數**，並在 ⑦ prompt 與 LINE 另列「資料異常未判（契約漂移）：代號」點名；0 檔有效判斷且原因為契約漂移時，LINE 不寫「資料抓取全失敗」。
    - `303c9703`（MINOR-B）：① 替代句依實際原因組成（判不出／只有外幣／只有缺現價三種句型）；燈全判得出、只有外幣核心 ETF 時不再說「沒東西可以判」。
    - **QA 最終結果**：獨立複驗組 C 共三輪；**第三輪：0 BLOCKER／0 MAJOR／3 MINOR**（3 項 MINOR 登記為 BACKLOG `XV-SHORT-TEXT-CORE-SAT`／`XV-UNJUDGED-COUNT-FX`／`XV-VALID-COUNT-INSUFFICIENT`，LOW）。測試：fast lane 全套 **32325 passed／1 環境失敗**（z59，`markdown_it` 缺套件，環境因素）。上方「QA」小點「C（複驗，兩輪）」之敘述截至第三輪前，現行以本小點為準。
    - 已知未改（更新）：`XV-WATCHLIST-SCOPE` 已部分處理（觀察清單判不出計入，見 `9c26106d`）；`XV-FX-ROW-ACTION` 升為客戶 Gate；`XV-LINE-VIX-LINE` 經複驗 C 確認為目前唯一仍讓 ⬜ 與「定期定額正常扣款即可」同則並存處。
    - ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本小點測試數與 QA 結果為總管轉述，docs-only 撰寫組未重跑測試、未經第二組驗。

### DEC-102｜DEC-101 後續四項客戶裁示：XV-ASOF 線框 Q1＝A／Q2＝A／Q3＝A（已核准、可實作）／XV-OLDUI-FX-REASON＝B（legacy 舊 UI 最小必要例外）／XV-LINE-VIX-LINE＝同意／XV-FX-ROW-ACTION＝同意（客戶 2026-10-28）

> 2026-10-28 補登（ID 取下一個未用號；落盤前 `grep -o 'DEC-[0-9]*' docs/*.md docs/vnext/*.md PROJECT_RULES.md` 最大為 DEC-101、DEC-102 0 命中）。要點經總管轉交，**非客戶逐字全文**；下列引號內關鍵句照總管轉交原句。

- **決策者**：**客戶**（2026-10-28；經總管轉交之要點）。
- **日期／效力日期**：2026-10-28 起生效。｜**狀態**：生效；~~四項**實作中**（ASOF＋三項小修）。~~ ~~四項**已實作（PR #963，待合併；見下方「實作紀錄」）**（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））~~ 四項**已實作並已合併（PR #963，main `6bdd9af6`；見下方「實作紀錄」）**（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。
- **背景**：DEC-101(3) 要求 XV-ASOF 先出線框（`docs/vnext/NEWUI_D25_XVIEW_ASOF_WIREFRAME_2026-10-28.md` §8 三題，附總管推薦）；DEC-101 實作紀錄另登記三項客戶 Gate（BACKLOG `XV-OLDUI-FX-REASON`／`XV-LINE-VIX-LINE`／`XV-FX-ROW-ACTION`，各附總管推薦）。客戶本次逐項裁示。
- **內容**：
  1. **XV-ASOF 線框（§8）：Q1＝A、Q2＝A、Q3＝A** —— 線框**已核准、可實作**。原則：
     - 批次表共同時間放**表頭下一行**，只有**例外列**另外標示；
     - 無法確認盤中價或收盤價時明確寫「**盤中或收盤未確認**」，**不得猜成收盤**；
     - 💼 持股頁**沿用總市值下方既有「價格資料日」位置**（線框 E17）；
     - source／as_of／stale **不得只靠顏色**表達；
     - **依已核准線框實作，不自行擴張版面**。
     - ⚠️ 「**過期價是否計入市值／損益／停利**」**未在本次裁示**，仍 open（稽核報告 G4；DEC-101 效力邊界）。
  2. **XV-OLDUI-FX-REASON＝B**：
     - 允許對 legacy 舊 UI 做**最小必要例外修正**；**只修「外幣持股時顯示錯誤原因」這一處**；
     - 改成與新版一致、據實的**外幣未納入／無法完整判定**說明；
     - **不得藉此整理、重構或擴張其他 legacy UI**；
     - Old UI Removal Gate 與既有凍結原則（DEC-019／DEC-020）**其餘部分維持不變**。
  3. **XV-LINE-VIX-LINE＝同意**：
     - 持股資料不足時，LINE **可以陳述 VIX 分級事實**；
     - **不得再附**「照原計畫走，定期定額正常扣款即可」等行動建議；
     - **missing ≠ HOLD**；VIX 狀態**不得代替持股資料完整性判斷**。
  4. **XV-FX-ROW-ACTION＝同意**：
     - 若財報／技術面資料完整，原本可證明的「🟢 續抱」**可保留**；
     - 同列**必須加註「停利未判：外幣」**或等義明確文字；
     - **不要**因單一停利子模組缺少成本幣別就把整列改成「⬜ 資料不足／無法判定」；
     - 原則：**可判定的部分照實呈現，不可判定的部分局部降級**。
- **效力邊界**：本條**不**決定過期價是否計入市值／損益／停利（仍 open）；**不**核准外幣換算（`FX-CANONICAL-GATE` 照舊另開）；**不**通過舊 UI Removal Gate、**不**放寬 DEC-019／DEC-020 除第 2 點那一處以外的任何凍結；XV-ASOF 只授權**依已核准線框**實作，版面擴張仍須另出線框（DEC-082）；不新增資料來源／schema／公式／投資語意；不降低任何 Gate。
- **與其他 DEC 的關係**：**回答** DEC-101(3)「先出線框，確認後再實作」之確認步驟與 DEC-101 實作紀錄所列三項待客戶 Gate；DEC-101(1)(2) 原文不改，本條第 3、4 點與 DEC-101(2)「missing ≠ HOLD」同向、精確化列層與推播層讀法。DEC-019／DEC-020 原文不改，本條第 2 點為**一處**有範圍的例外。DEC-082（草稿先行）呼叫。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：docs-only 撰寫組只落盤裁示，不改任何程式碼、未重跑測試；本條要點為總管轉交、非客戶逐字全文；「本條與 DEC-101／019／020 的關係」為撰寫組讀法，單組。
- 📌 **實作紀錄（2026-10-29 補；加法式，上文一字未改；決策者 AI 總管（事實更新））**：~~**狀態＝已實作，PR #963 待合併**~~ **狀態＝已合併（PR #963，main `6bdd9af6`）**（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（分支 `ccr-6eace3b6-0gglrs`；基準 `1e603094`，`git log 1e603094..HEAD`）。
  - **commit**：`afe5ec42`（DEC-102／DEC-103 落盤，docs）／`61d81d45`（XV-OLDUI-FX-REASON）／`c3874a12`（XV-LINE-VIX-LINE）／`7cb05bab`（XV-FX-ROW-ACTION）／`d3a50f27`・`f6f536f2`・`8d84ef7d`・`600916f5`・`34f56a0c`・本批收尾 commit（XV-ASOF 實作與 QA 回修）／`8b794c04`（AI 總結 prompt 同步禁止 VIX 行動建議＋docstring＋BACKLOG 登記）／`f6d61468`・`81ed94dc`（兩組整合 merge）。（`27de9c61` 為 DEC-104 治理 docs，非本條實作。）
  - **改動檔**：`shared/price_asof_label.py`（新，L0）／`src/services/dividend_station_service.py`（L3 加性非顯示鍵 `price_as_of`／`price_src`／`is_stale`／`is_fallback`／`ffilled_last` 等；AI 總結 prompt）／`src/ui/views/page_inspect.py`（🔬 P1／P2／P4 與查看依據）／`src/ui/views/page_hold.py`（💼 ① E17 位置、⑤ 指回一行）／`src/compute/notify/holdings_digest_message.py`（LINE VIX 句）／`shared/asset_currency_gate.py`（列層加註句）／`src/ui/etf/etf_tab_dividend_station.py`（舊 UI 最小例外）；測試 `tests/test_xv_asof.py`、`tests/test_dec102_*.py`、還原鏈頭節 `tests/test_asof_revert_chain.py`／`tests/test_dec102_revert_chain.py`。
  - **決定（AI 總管，DEC-102 授權邊界內）**：
    - **stale 判定**：只用既有 `shared/staleness.expected_latest_trading_day()`＋freshness SSOT `assess_daily(calendar_kind="weekday")`＋`DAILY_MAX_LAG_TRADING_DAYS`（DEC-029），⛔ 不自創天數；只扣週末、不扣國定假日（偏嚴，長假後可能多標 ⚠）→ BACKLOG `XV-ASOF-HOLIDAY`。ETF 最後一根為補值時以實際資料日判。
    - **卡面字樣**：日期 M/D、年份 ≠ 判定日年份時寫 YYYY/M/D；「盤中或收盤未確認」只在句尾寫一次（⛔ 不猜收盤）；每種 production 可達狀態 ≤ 卡面上限 46 字；完整 ISO 日期只在既有「查看依據」摺疊區。拿不到時間寫「資料時間：⬜ 未提供」（💼「價格資料時間：⬜ 未提供」），⛔ 不用今天代替。過期價**照樣**計入市值／損益（是否排除仍 open，只標示）。
    - **舊 UI 兩句同一缺陷**：舊 UI 卡①與 80/20「算不出來」兩句在有外幣持股時都講成「持股沒有張數／均價…」，屬同一缺陷，依 DEC-102(2) 一併改用新 UI 同一客戶句；舊 UI 其餘凍結不變。
    - **列層加註只限 🟢**：外幣列只有在原結論為「🟢 續抱」時保留並加註「停利未判：外幣／幣別未確認」；🔴／⚪ 等非續抱結論逐字不變。
    - **AI 總結 prompt 同步**：持股資料不足（同一謂詞 `digest_data_short`）時 prompt 追加「VIX 只可陳述分級事實，不得據以給任何行動建議（如照原計畫、定期定額）」，與 LINE 正文同原則；資料齊全時 prompt 與 `1e603094` 逐字相同。
    - **XV-X1 不修**：新四頁顯示價格的位置都走 L3 `fetch_metrics` → 同一快取鍵（個股 360 日），P2 沿用 P1 同一份；判定經 QA 複驗在其查到範圍內成立（非窮舉保證）。
  - **QA**：ASOF 獨立 QA 兩輪（第一輪 1 MAJOR＋6 MINOR 已回修；第二輪 0 BLOCKER／0 MAJOR，所報兩項亦已回修）（總管轉述）。測試數見本批 commit 訊息與 PR 描述。
  - **已知未改（登記）**：`XV-ASOF-HOLIDAY`／`XV-ASOF-FOLD-GAPS`／`XV-ASOF-TTL-2ND-SSOT`／`XV-ASOF-LEN-UNREACHABLE`／`XV-OLDUI-AI-CARD-HOLD`（客戶 Gate）／`XV-FX-ROW-NOKD`（皆 P2）；過期價是否計入仍 open。
  - **未驗**：盤中行為、部署時區、Streamlit Cloud 快取下 `attrs["price_src"]` 是否保留、手機排版 → 待客戶實機點驗（HANDOFF）。
  - ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本段由實作組撰寫；「XV-X1 不修」等判定為實作組讀碼結論經 QA 複驗，仍非窮舉保證。

### DEC-103｜Scope Inflation Guard（範圍膨脹防護）正式入治理（客戶 2026-10-28）

> 2026-10-28 補登（ID 取下一個未用號；落盤前同上 grep，DEC-103 0 命中）。**客戶原文逐字收錄於 `PROJECT_RULES.md` 第 23 節，原文以該節為準**；本條只作摘要與指向。

- **決策者**：**客戶**（2026-10-28）。
- **日期／效力日期**：2026-10-28 起生效（永久治理規則）。｜**狀態**：生效。
- **規則落點**：`PROJECT_RULES.md` **第 23 節**「Scope Inflation Guard（範圍膨脹防護；客戶 2026-10-28，DEC-103）」。
- **摘要（非逐字；以第 23 節原文為準）**：
  1. 目標：避免 Audit／QA／技術發現持續長出大量待辦，使專案從「完成新版投資決策 OS」漂移成「修完所有歷史技術債」。
  2. 所有新發現先分 **P0 主線阻擋／P1 新版必要／P2 技術債**；P0 可插隊、P1 依主線順序排程、**P2 只能登記，不得自動插隊**。
  3. 不阻擋 D2.5 四頁、Decision Digest、資料正確性或安全性的新發現**只能進 BACKLOG，不得因此開新 Stage**；不得因「順手修」把一次批次擴張成歷史技術債清理。
  4. 主線優先序維持「四頁完成 → One AI Brain / Decision Digest 接線 → 資料一致與必要護欄 → 實機驗收」。
  5. **不取代既有安全 Gate**（第 9 條自陳）。
- **落地方式**：`docs/BACKLOG.md` 0.3 新增「新增列須標 P0／P1／P2；既有列不回溯重標」一條；`docs/HANDOFF.md`、`docs/PROJECT_STATE.md` §21 各加一行指向第 23 節。**未建立任何新 Stage。**
- **與其他 DEC／條文的關係**：與 `PROJECT_RULES.md` 第 5 節 Minimum Necessary Change／Scope Control、`CLAUDE.md` §-1、§-1.5.F 判定 3 **同向（加嚴）**；不取代任何安全 Gate。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：「同向（加嚴）」為撰寫組讀法，單組；docs-only，未改程式碼。

### DEC-104｜Hard Output Gate（送出前硬閘）正式入治理（客戶 2026-10-29）

> 📌 2026-10-29 第二次復發（Phase 1 SSOT Reset 批次），紀錄見 `docs/BACKLOG.md` `GOV-CHATTER-2026-10-29`；澄清落點 `PROJECT_RULES.md` 第 3 節「小節：Hard Output Gate」末尾。append-only，本條內文未改。

> 2026-10-29 補登（ID 取下一個未用號；落盤前 `grep -rn "DEC-104" --include=*.md .` 0 命中）。**客戶原文逐字收錄於 `PROJECT_RULES.md` 第 3 節（Silent Autonomous Cruise）「小節：Hard Output Gate（客戶 2026-10-29，DEC-104）」，原文以該處為準**；本條只作摘要與指向。

- **決策者**：**客戶**（2026-10-29）。
- **日期／效力日期**：2026-10-29 起生效（永久治理規則）。｜**狀態**：生效。
- **規則落點**：`PROJECT_RULES.md` **第 3 節**，緊接「零過程訊息／Process chatter = governance violation」條之後。
- **摘要（非逐字；以第 3 節原文為準）**：
  1. 任何 user-visible 訊息送出前先判斷：只有 5 類可輸出（🔴 需客戶裁示／🟡 Model×Effort 需切換且尚未通知／🟡 需客戶手動操作／🟢 整個 Stage 完整完成／🟡 context／token 不安全需換新對話交接）；其餘一律不輸出。
  2. 明列禁句（進行中／已 push／PR 已開／review·QA·mutation 正在跑／還沒完成／之後完成再回報／local·remote 已同步／下一步正在做什麼等）；「我會保持安靜」本身也是 process chatter。
  3. Pre-send self-check：五問全否即 SILENT；不得以簡短進度、英文進度句或重複通知取代靜默。
- **觸發背景**：AI 總管於 DEC-102 實作批次期間多次輸出過程訊息，見 `docs/BACKLOG.md` `GOV-CHATTER-2026-10-29`。
- **與其他 DEC／條文的關係**：與 `PROJECT_RULES.md` 第 3 節「禁止事件回音」「零過程訊息」（2026-10-28）**同向（加嚴）**，5 類出聲情況一致；不取代任何安全 Gate，不減少第 3 節上方限定第 4 條揭露義務。`docs/HANDOFF.md` 必讀規則處加一行指向。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：「同向（加嚴）」「5 類一致」為撰寫組讀法，單組；docs-only，未改程式碼。

## 2. 產品／UI

### DEC-017｜IA v2 五頁線框為台股前端實作依據
> 📌 **SUPERSEDED BY DEC-097（IA）；部分取代 BY DEC-109（鐵律 4 呈現位置）；葉1 ②「兩套刻度常駐非摺疊」維持有效（是否改為 chip＋可展開＝Phase 6 線框待客戶拍板點）**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-097／DEC-109）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：五頁 IA 已由 DEC-091 §二／DEC-092 Q6／DEC-097 四頁（📊 市場／🎯 標的／💼 持股／👤 我的）取代；鐵律 4「一律附三要素：現況一句話／為什麼沒有／去哪補」的**內容**仍必填（`tab_today.Note` 三段非空契約不變），**位置**自 DEC-109 起由「卡面常駐」改為「可取得、可追溯、可展開」（L3 摺疊）。兩邊理由：舊做法最不會讓三要素被省略（仍成立）；新做法依客戶 DEC-109 七「資訊必須存在、可取得、可追溯、可展開，但不要求全部外露」勝出（客戶原文明確點名「現在／為什麼／去哪補」）。**葉1 ②「兩套刻度…常駐揭露 · 非摺疊」是客戶核准線框的設計，DEC-109 原文未點名 → 維持有效**；在 Visual Budget 下是否改為「L1 一顆 chip＋完整雙表可展開」，列為 Phase 6（💼 持股）線框草稿的待客戶拍板點（BACKLOG `P1R-P6-WF-TWO-SCALES`；依草稿先行，本 phase 不另開 Gate、不改）。
- **內容**：7 頂層／14 葉 → 5 頂層／11 葉；版面架構、決策動線與四態模型確認。
- **範圍**：UI｜**日期**：2026-09-05｜**決策者**：客戶｜**狀態**：生效（後續逐頁修訂）
- **來源**：B `67affe8d`（直推）「客戶 2026-09-05 拍板：版面架構、決策動線與四態模型全數確認，13 項裁決與 v2 線框」；檔案 `docs/wireframes/stock_ia_v1.html`。

### DEC-018｜雙軌入口：舊 7 頁籤維持第一排、新版五頁由側邊欄進入（方案 A）
> 📌 **SUPERSEDED BY DEC-097**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-097）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：預設入口已翻轉為新四頁導覽（DEC-097(2)；實作 DEC-098，`?legacy=1` 為 rollback）；本條「舊 7 頁籤維持第一排、新版由側欄進入」不再是現行入口。DEC-020（切換路線與舊 UI 刪除前置）不變。
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
> 📌 **部分取代 BY DEC-083（只限「換一本／建新 Sheet」的位置）**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-083 Q1）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：DEC-083 Q1 明確把 Google 帳號、Sheet 綁定（換一本／建新 Sheet）定在「👤 我的」→ 本條「同處換一本／建新 Sheet」的**位置**改為 👤 我的。**本條其餘仍有效**：「💼 我的持股 › 組合設定」預覽表下方放編輯區、預設收合的 **CRUD 編輯區位置維持 DEC-021**（DEC-083 Q1 未明確點名；Sheet CRUD 實作待 `ME-P2` Gate）；寫入功能做進新 UI、逐筆、預覽、二次確認、同本重複阻擋原則仍有效。判準：客戶 DEC 的呈現裁示只有在新裁示明確點名處才被取代。
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
> 📌 **DEC-122 Q2=A：本條七種 Action 名稱繼續有效（不是取代）**（2026-11-02；決策者 **客戶**（DEC-122 裁示 Q2=A）＋AI 總管〔判讀，INFERENCE〕；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §2）：Final UI「今日需處理」第一版只顯示既有 deterministic 分支原名（Q2=A）；本條的「減碼」「全部退出」名稱只有在正式規則產生時才可出現，⛔ 由 UI／OneBrain 對既有分支映射而來；強 Action 不得只靠生成式 AI、不得繞過 Risk Cap 等護欄全部仍有效。
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
> 📌 **只限 Final UI 主線的「Stage 完成回報」部分取代 BY DEC-122**（2026-11-02 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-122）；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S17）：Stage 完成回報改用客戶 2026-11-02 §48 格式（`🟢 Stage X 完成`＋一張表：項目／結果／main SHA／PR #／Production behavior changed／Semantic change／QA／Visual Gate／Mobile／Remaining blocker／Next handoff），行數可超過 5。**本條其餘仍有效**：完整技術／稽核證據留在 PR、一般（非 Stage 完成）回報 ≤5 行、裁示題只留裁示所需資訊。兩邊理由：舊做法讓回報最短、客戶注意力成本最低（仍成立）；新做法依客戶明示 Stage 完成需一張可稽核的固定表（同句「不要施工日誌」與本條同向）。⚠️「表格行數 >5 即屬部分取代」為撰寫組讀法（INFERENCE），客戶可推翻。
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
> 📌 **第 4 點 SUPERSEDED BY DEC-092／DEC-097；第 6 點部分取代（導航標籤）**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-091／092／097）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：導航名稱已由 DEC-091 §二客戶指定版與 DEC-097 逐字定案為「📊 市場／🎯 標的／💼 持股／👤 我的」（「候選非 final」狀態結束）；第 6 點「『大盤』必須明確保留」在**導航標籤**層面被客戶後續指定「📊 市場」取代，頁內「大盤合理區間」等用語仍有效。⚠️ 第 6 點的取代範圍為撰寫組讀法（INFERENCE），客戶可推翻。第 1、2、3、5 點仍有效。
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

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S23：「資料中心」作為獨立責任面→改為 👤 我的·資料健康度（MIGRATE））** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。
> 📌 **SUPERSEDED BY DEC-092（頁面結構）**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-091／DEC-092）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：投資主流程四頁「📊 大盤／🎯 標的／⚡ 行動／🛡️ 持股」＋輔助「👤 我的／🩺 資料中心」已由 DEC-091 §二／DEC-092 四主導航取代（⚡、🩺、「憑什麼」改為各頁能力）。**「底層能力完整，前台流程極簡」原則仍有效**（DEC-076 §4.1 同向）。
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
> 📌 ~~**條件式，待 DEC-122 Q1（不是取代）**（2026-11-02 登記；決策者 客戶（DEC-122 指示）＋AI 總管〔判讀〕；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §2）：本條與 PQ-C6-3（DR-2026-10-16-4，客戶 2026-10-16 核准線框）使 💼 持股頁卡⑤外露建議持股區間 `range_text`＋資料完整性列；📊 市場頁則依 DEC-081 Q2-2／`RC-VISIBILITY` 隱藏數字。客戶 2026-11-02 §19 新增 Risk Cap 閘門後，兩頁顯示是否統一、持股頁區間是否保留，**併入 DEC-122 Q1 請客戶一併決定**。**裁示前本條照舊有效，持股頁區間外露不是違規**；本條的中性措辭與 Optional 完整性揭露在任何 Q1 結果下都仍有效（Final UI 契約 §8.1 第 5 點）。~~（裁示前登記，已由 DEC-122 Q1=A 結案；現行見下一則 📌（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留））
> 📌 **DEC-122 Q1=A 裁示：本條維持（不是取代）**（2026-11-02；決策者 **客戶**（DEC-122 裁示 Q1=A「持股頁既有已核准的建議持股區間先維持，不因本次 Freeze 擅自修改」）；append-only，本條與上一則 📌 原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §2）：上一則（裁示前登記）已由裁示結案——💼 持股頁卡⑤外露建議持股區間與 Optional 完整性揭露**維持**；📊 市場頁仍隱藏；兩頁是否統一、Risk Cap 數值正式啟用、曝險分母、現金／總資產來源另開正式 Decision Gate（BACKLOG `FUI-RC-NUMERIC-GATE`）。
- **內容**：今日頁與持股頁卡面直接列「未評估：PCR、BIAS240」等實際項；中性措辭「部分訊號未納入，本次上限資訊不完整」，不寫「上限可能偏寬」；全有效可顯示「必要與選用訊號皆已評估」（擁擠可省）；M1B−M2 不列未評估、可另列「已停用」；詳細摺疊可列資料日期；顏色不得是唯一載體。
- **範圍**：UI／公式呈現｜**日期**：2026-10-16｜**決策者**：客戶｜**狀態**：生效（已實作）
- **來源**：A `docs/BACKLOG.md@f0a6c474:60`。D 客戶訊息 2026-10-16T08:00Z（本 session；本檔首次入庫）「不要固定寫「上限可能偏寬」；改為中性且準確的「部分訊號未納入，本次上限資訊不完整」。」。B #862 `fa26914b`。
- **取代鏈**：取代 DEC-043 的文案。

### DEC-052｜新 UI 獨立 Risk Cap state／snapshot 檔；舊 UI 原檔不改（DR-2026-10-16-5）
- **內容**：新 UI 不得再讓舊 UI 寫入覆蓋其有效快照；只接受符合 Required Core、版本標記與 freshness 的 snapshot；舊 UI 凍結不為相容新 UI 修改；不改寫歷史 Decision／frozen validation；檢查所有新 UI read/write path、無 fallback 偷讀舊檔；AUD-C22 維持獨立 Backlog。
- **範圍**：資料／儲存｜**日期**：2026-10-16｜**決策者**：客戶｜**狀態**：生效（已實作）
- **來源**：A `docs/BACKLOG.md@f0a6c474:61`。D 客戶訊息 2026-10-16T08:00Z（本 session；本檔首次入庫）「新 UI 建立自己的獨立 Risk Cap state / snapshot 檔案；舊 UI 繼續使用原檔，不修改舊 UI。」。B #862 `fa26914b`。

### DEC-053｜正式加減碼比例須經「資料驗證 → 規則設計 → 回測／Shadow Mode → 客戶裁示」才能進 production
> 📌 **DEC-122 Q2=A 確認本條繼續有效（不是取代）**（2026-11-02；決策者 **客戶**（DEC-122 裁示 Q2=A）；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §2）：客戶「減碼 1/2」「全出」等比例 Action 目前不得自行映射或產生；未來只有在正式規則、驗證、必要回測／Shadow 與 Decision Gate 完成後才能啟用——與本條「資料驗證 → 規則設計 → 回測／Shadow → 客戶裁示」同向（BACKLOG `FUI-PROPORTIONAL-ACTION-RULES`）。
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

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S23：§6 資料中心責任方向→MIGRATE；§7 Progressive Disclosure 第三層「需要時才展開」＝頁內摺疊的讀法（S21／S26））** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。
> 📌 **§6 部分取代 BY DEC-092**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-091／DEC-092）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：§6 所列「⚡ 行動」「🩺 資料中心」「憑什麼」作為獨立頁的方向，已由 DEC-091 §二改為各頁能力（⚡ 融入各頁首屏「需要處理」、🩺 小型狀態入口、📖 憑什麼＝各判斷旁「查看依據」）。**§4.1、§7 Progressive Disclosure、§8 語意界線、§10、§12、§16、§17、§20 仍有效**；§7 三層與 DEC-109 同向。
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

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S23：第 7 點 📊 大盤「展開理由」頁內展開（SUPERSEDE）；Q4=C 🩺 資料中心分流→MIGRATE；互動控制完整性其餘維持）** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。
> 📌 **Q1／Q4 分流目的地部分取代 BY DEC-092；Q2-1 結論句位置依 DEC-109**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-092／DEC-109）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：Q1／Q4 的分流目的地（⚡ 行動、🩺 資料中心、🛡️ 持股）已隨四頁 IA 改變；Q2-1 結論句**內容與規則**（只並列、缺值明寫、⛔ 缺值當中性）仍有效，**位置**自 DEC-109 起須在第一屏（Presentation Contract §16）；**Q2-2 卡面措辭「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」逐字仍有效**；Q2-3、Q3、互動控制完整性仍有效。
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
> 📌 **Q1 措辭部分取代 BY DEC-097**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-097）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：Q1「側欄新增獨立『👤 我的』」的「側欄新增」形式已由 DEC-097 四頁導覽（桌機側欄＋手機底部列）取代；「👤 我的為 Google 帳號、Sheet 綁定與新版 Sheet SSOT 的**唯一**設定入口」**仍有效**；第 11 點（E 段 Removal Gate：Google 側欄暫時保留）**仍有效** → 現況兩入口並存（Presentation Contract §13.4；舊側欄隱藏與否＝未來客戶 Gate `P1R-GOOGLE-LOGIN-SIDEBAR-GATE`）。
> 📌 **第 11 點 E 段 Removal Gate 與 DEC-122 Stage J 六條件取聯集（不是取代）**（2026-11-02 登記；決策者 客戶（DEC-122 指示）＋AI 總管〔判讀〕；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §3）：客戶 2026-11-02 Stage J 規定提出 Old UI Removal Decision Gate 前須滿足六條件（四頁 coverage、mobile、real data、audit coverage、user final acceptance、capability map 無 critical gap）；本條 E 段七步刪除條件**繼續有效**，兩組條件**都成立**才可提出 Removal Gate。Q2「觀察清單 CRUD 留 P2」亦繼續有效——Final UI 契約 §3.3 據其較嚴讀法把新版「加入觀察」CTA 設為 disabled（INFERENCE）。
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
| `docs/vnext/NEWUI_D25_XVIEW_ASOF_WIREFRAME_2026-10-28.md` 狀態「只是草稿，尚未實作；待客戶確認」；BACKLOG `XV-OLDUI-FX-REASON`／`XV-LINE-VIX-LINE`／`XV-FX-ROW-ACTION`「open（待客戶裁示）」（2026-10-28 新增列） | DEC-102 | 裁示（線框 Q1～Q3 皆 A、已核准可實作；FX-REASON＝B；VIX-LINE、FX-ROW-ACTION 同意；過期價計入與否仍 open；線框原文不改，只改狀態頭） | 客戶 2026-10-28（經總管轉交要點） |
| DEC-019／DEC-020 舊 UI 凍結（2026-10-28 新增列） | DEC-102(2) | 一處例外（只修外幣持股時錯誤原因句；其餘凍結與 Removal Gate 不變；原文不改） | 客戶 2026-10-28（經總管轉交要點） |
| DEC-073「現有能力高於工作所需，不需要為了形式要求客戶降級」（2026-10-29 補列；正文已載） | DEC-084 | 部分取代（雙向停手） | 客戶 2026-10-25 原文（DEC-084「與其他 DEC 的關係」） |
| DEC-017 五頁 IA；DEC-018 舊 7 頁籤第一排（2026-10-29 新增列） | DEC-097 | 取代（預設四頁導覽；`?legacy=1` rollback；DEC-020 不變） | 客戶 2026-10-28＋撰寫組讀法，單組 |
| DEC-017 鐵律 4 三要素「卡面常駐」（2026-10-29 新增列） | DEC-109 | 部分取代（內容保留；位置改 L3 摺疊；原文不改）。葉1 ②「兩套刻度常駐非摺疊」**不取代**：維持有效，列 Phase 6 線框待拍板 | 客戶 2026-10-29 原文（DEC-109 七）＋撰寫組讀法，單組 |
| DEC-021「同處換一本／建新 Sheet」的位置（2026-10-29 新增列） | DEC-083 Q1 | 部分取代（換一本／建新 Sheet → 👤 我的，DEC-083 Q1 明確點名）；**CRUD 編輯區位置維持 DEC-021**，待 `ME-P2` Gate | 客戶 2026-10-25 原文（DEC-083 Q1）＋撰寫組讀法，單組 |
| DEC-081 Q2-1 今日結論句**位置**（2026-10-29 新增列） | DEC-109（＋同日前序指示 15:18Z「今日結論必須在第一屏可見」） | 部分取代（位置須在第一屏；結論句內容與規則、Q2-2 措辭逐字不變；原文不改） | 客戶 2026-10-29 原文＋撰寫組讀法，單組 |
| DEC-071 第 4 點（導航改名、候選非 final）、第 6 點（導航保留「大盤」字樣）（2026-10-29 新增列） | DEC-091 §二／DEC-092／DEC-097 | 第 4 點取代；第 6 點部分取代（導航標籤；INFERENCE） | 客戶 2026-10-27／28 原文＋撰寫組讀法，單組 |
| DEC-072 四頁＋輔助入口；DEC-076 §6 ⚡／🩺／憑什麼獨立頁；DEC-081 Q1／Q4 分流目的地（2026-10-29 新增列） | DEC-091 §二／DEC-092 | 取代／部分取代（「底層完整、前台極簡」、DEC-076 §7、DEC-081 Q2 仍有效） | 客戶 2026-10-27 原文＋撰寫組讀法，單組 |
| DEC-083 Q1「側欄新增獨立 👤 我的」措辭（2026-10-29 新增列） | DEC-097 | 部分取代（唯一設定入口與 E 段仍有效） | 撰寫組讀法，單組 |
| DEC-091 §四「市場狀態 🟢偏多／🟡中性／🔴偏空」＋A 規格 §4.1.1 表＋`d25_wireframes/index.html` 圖例與 `market.html` 首屏圖例（2026-10-29 新增列） | DEC-105 2A | 部分取代（五態字樣；HTML 不改、A 規格加註） | 客戶 2026-10-29 原文（DEC-105） |
| DEC-091(d)／§九「AI 投資總結固定五段」＋A 規格 §5＋`d25_wireframes/ai_summary.html`（經 DEC-092 設計核准承接）（2026-10-29 新增列） | DEC-109 二十一 | 呈現格式取代（R12；分類資料保留；AB-2a 程式五段 Phase 7 改） | 客戶 2026-10-29 原文 |
| DEC-091 §一「禁止三要素文字卡同層」vs DEC-111／DEC-112（只在程式碼註解）（2026-10-29 新增列） | DEC-109 | 調和（資訊保留、預設下沉） | 撰寫組讀法，單組 |
| DEC-111（補登，客戶 2026-09-24「三要素要在卡面上看得到」）；DEC-112（補登，客戶 2026-09-25「v2 卡面三列短句」）（2026-10-29 新增列） | DEC-109 | 部分取代（位置／列數）；K1、「⛔ 不得只剩 hover」維持並延伸到手機 | 客戶 2026-10-29 原文（DEC-109 七）＋DEC-110 R6 |
| DEC-099 過渡切換（2026-10-29 新增列） | DEC-107／PR #968 | 已執行完畢（非取代） | 事實更新 |
| DEC-105 1A 結論句位置；DEC-107 4A 候選表全表外露（2026-10-29 新增列） | DEC-109 | 呈現部分取代（結論句須進第一屏；候選 Top-N；內容與互動不變）。DEC-107 1A 頁面順序與 UIT 線框「選股條件預設展開」、DEC-105 第 4 點指路形式**不取代**：維持有效，列 Phase 4／5 線框待拍板 | 客戶 2026-10-29 原文（DEC-109 十二；同日前序指示「今日結論必須在第一屏可見」） |
| DEC-108 線框草稿「待客戶核准」、§客戶待確認 5 題、第 3 點凍結解除條件（2026-10-29 新增列） | DEC-109 | 部分取代（十項原則仍有效；5 題撤回；凍結改為各 UI phase 過 Visual Fidelity Gate） | 客戶 2026-10-29 原文（DEC-109 一） |
| PR #970 線框 A.4／Q2「大圖只在 L2」、Q2-B「首屏不放圖」、A.7 偏多／中性／偏空、B.3 ② 價格時間移頁首（2026-10-29 新增列） | DEC-109／DEC-110 R2／DEC-105 2A／DEC-102 Q3 | 取代／不採用（草稿已自分支移除，出處 PR #970 commit `06a7a3e5`） | 客戶原文＋DEC-110 |
| DEC-105 1A 結論句在 📊 市場頁的舊相對順序（結論在 Hero／tile 之後；含 DEC-109 部分取代後的「Hero／⚡ 相對順序可維持」）（2026-10-30 新增列） | DEC-117 Q5 | **取代（📊 市場頁）**：新順序 頁首 → 更新 CTA → 今日結論 → 3 個核心狀態 → ⚡需要處理 → AI／資料狀態 → Primary Visual；結論句內容逐字不變；DEC-105 原文不改 | 客戶 2026-10-30 原文明示（「我明確同意更新／取代 DEC-105 1A 在市場頁的舊相對順序」） |
| DEC-105 第 5 點「Hero 用 4 欄」；DEC-091 §四「第一列 3～4 個核心狀態（含更新：主 CTA）」；DEC-110 R4／BACKLOG `CV1-DR-12`（W9）待裁示（2026-10-30 新增列） | DEC-117 Q1 | 📊 市場頁取代／部分取代／裁示結案：桌機 3 個核心狀態 tile＋頁首主 CTA、手機 2＋1；客戶明示「固定 3 欄」是桌機核心狀態網格要求（`CLAUDE.md` 不改）；原文不改 | 客戶 2026-10-30 原文明示 |
| DEC-105 第 4 點指路形式（說明句 vs chip）待拍板（DEC-110 R5、`P1R-P4-WF-POINTS`／W2）（2026-10-30 新增列） | DEC-117 Q2 | 裁示結案（維持說明句、縮短、不新增 chip；三要素必須保留） | 客戶 2026-10-30 原文明示 |
| DEC-110 R7／`P1R-WF-FOLD-LABEL`（W3）在 📊 市場頁待拍板（2026-10-30 新增列） | DEC-117 Q3 | 裁示結案（📊 市場頁：圖用四段字樣、tile／⚡ 維持「查看依據」；Phase 5～6 仍待） | 客戶 2026-10-30 原文明示 |
| DEC-110 R2「1 Primary Visual 在第一屏」＋契約 §2 B1／§3 五問③（📊 市場頁手機）（2026-10-30 新增列） | DEC-117 Q7 | 部分取代（📊 市場頁手機 mobile exception，附條件：Primary 緊接 L1 決策區、不得被 L2／L3 插隊；桌機照舊）；DEC-109 四為例外登記、非取代 | 客戶 2026-10-30 原文明示（「接受手機 Primary Visual 位於第一屏下方，Visual Fidelity Gate 登記合理 mobile exception」） |
| DEC-091 §四 圖C「圖上方『用企業獲利 EPS…』」說明句位置；DEC-092 設計方向「每張圖上方有白話說明」（📊 市場頁圖 C）（2026-10-30 新增列） | DEC-117 Q8a | 部分取代（📊 市場頁圖 C：該句移到摺疊「為什麼」、逐字保留；其餘圖不變；原文不改） | 客戶 2026-10-30 原文明示（「圖 C 的完整原句移到『為什麼』」） |
| `docs/vnext/PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30.md` 狀態「草稿 rev1，待客戶拍板」＋§6 各題推薦／不裁示預設（含 Q5 重審後推薦 A）（2026-10-30 新增列） | DEC-117 | 裁示（Q1=B／Q2=A′／Q3=A／Q4=P-B／Q5=B／Q6=A／Q7=A／Q8 全 A；線框原文保留、加註；Q5 未採推薦 A 而採 B） | 客戶 2026-10-30 原文 |
| DEC-117 Q7（手機 mobile exception 只豁免 Primary）；線框 §10 C1-10／U4「手機第一屏必須含 ⚡ bar」（2026-10-30 新增列） | DEC-118 問題 1=A | 補充／取代：⚡ 列為手機 mobile exception，緊接 3 核心狀態之後、不得被 L2／L3 插隊；手機第一屏必含今日結論＋核心狀態 | 客戶 2026-10-30 原文明示 |
| DEC-117 Q4「保留正式原生圖、MA 參考線、y 軸、圖例」的「原生圖」字面（2026-10-31 新增列） | DEC-119 題 1=A（補充裁示） | **澄清（非取代）**：要求保留的是正式完整主圖的資料與視覺語意，implementation 不綁死 `st.line_chart`；允許為 mobile readability 改用 Streamlit 可承載的自訂圖表元件；Q4 其餘不變 | 客戶 2026-10-31 原文明示（「我在此澄清 DEC-117 Q4」） |
| 契約 Q3「Primary 主圖本體高 mobile ≤140px」（DEC-110 內部建議值）；P4-3 Gate A6（2026-10-31 新增列） | DEC-119 題 1=A | **例外（📊 市場頁）**：手機 Primary 維持約 220px，「不要再為了 140px 壓縮可讀性」；契約／DEC-110 原文不改，Gate §8 登記 | 客戶 2026-10-31 原文明示 |
| P4-3 Gate A5（桌機全頁高 ≤ blueprint 2×；實測 2.02×）（2026-10-31 新增列） | DEC-119 題 2=A | **接受為已知輕微偏差**（不重新設計 11 個已核准 L2／L3 摺疊列、不展開頁尾結構重構）；Gate §8 登記 | 客戶 2026-10-31 原文明示 |
| 線框 §10 C1-9 與 2026-09-24「真錯誤留在收合區外」的衝突（2026-10-30 新增列） | DEC-118 問題 2=D1 | 補充：更新部分失敗的真錯誤外露、放今日結論正下方；CTA→結論之間只剩收合標題列 | 客戶 2026-10-30 原文明示 |
| P4-3 Gate §2 合計規則「🟡 ≥4 視為 ❌」對 📊 市場頁 A2／A4／A10／A11 四項（2026-10-31 新增列） | DEC-120 | **例外（僅 📊 市場頁）**：四項接受為已知合理偏離，不因合計規則升格；Gate 判定 PASS（待 CI 綠＋獨立 QA 複驗）；其他頁面仍照規則，不繼承；Gate §8 登記 | 客戶 2026-10-31「選 A」（經總管轉交） |
| DEC-107 第 1 點（1A 整頁順序）；DEC-121 Q2「整頁已核准順序不變」一句；DEC-099 第 3 點終態讀法（2026-11-02 新增列） | DEC-122（S1～S3） | 部分取代：🎯 標的頁改為頁內雙模式 [市場精選][即時查一檔]；DEC-107 2A～5A／補充邊界、DEC-121 Q1／Q3／Q2 其餘、DEC-099 第 1、2、4、5 點仍有效；⛔ 回到 NAV-1 葉選擇器 | 客戶 2026-11-02 原文明示（DEC-122）；DEC-099 讀法＝撰寫組（INFERENCE） |
| Presentation Contract §6 R8-2／§8-3、Gate V8「🔴 只給系統真錯誤」；DEC-115 D3 末句；BACKLOG `P5-CHIP-KIND-NAMES`「或維持」（2026-11-02 新增列） | DEC-122（S4～S6） | 部分取代：Semantic Chip 四 tone；Danger＝確定性違規／Risk Cap，文字須與取得失敗不同；`guard_chip` 只限客戶逐字護欄句 | 客戶 2026-11-02 原文明示（DEC-122） |
| Presentation Contract §6 `unavailable` 列語意；§8 第 1 點／2026-09-23 D-3(a) 的 L1 外露字樣（2026-11-02 新增列） | DEC-122（S7、S8） | 部分取代：Unavailable＝來源目前不可用（舊義改稱功能尚未提供／未接線）；L1 Missing 字樣＝`⬜ 資料未取得／資料未備`；十態保留為 L0 | 客戶 2026-11-02 原文明示（DEC-122）；只限 L1＝撰寫組讀法 |
| `ONE_AI_BRAIN_BOUNDARY` §3「⛔ 把 Risk Cap 連到具體行動」（2026-11-02 新增列） | DEC-122（S9） | 部分取代（只限「超限 → 禁止新增曝險／不得出現 unrestricted Add」）~~；數值啟用待 DEC-122 Q1 |~~ ；數值啟用：DEC-122 Q1=A 已裁示，另開 `FUI-RC-NUMERIC-GATE` | 客戶 2026-11-02 原文明示（DEC-122） |
| DEC-118 問題 1=A（手機 ⚡ 例外）；DEC-120 A10／A11；DEC-117 Q1 手機 2＋1（2026-11-02 新增列） | DEC-122 Q3（S10、S11） | ~~**條件式，待 Q3**（Q3=A：手機「是否行動」進第一屏、改 DEC-117 Q1 手機排法、A10／A11 重量；Q3=B：照舊）；裁示前照舊有效~~ **正式取代（DEC-122 Q3=A，客戶 2026-11-02）**：只限 📊 市場頁手機——第一屏＝市場目前狀態＋Risk Cap＋是否需要行動＋主 Update CTA，今日主要風險緊接其後仍屬 L1；DEC-118 問題 2=D1、DEC-117 桌機與 Q2～Q8、DEC-120 A2 與 A4 桌機部分仍有效；DEC-120 A4 手機部分隨 S10 失去前提、Stage B 重量（總管內部判定）（2026-11-02 有意識的更新，不是漏刪；原文刪除線保留） | ~~客戶 2026-11-02 §40 vs 客戶 2026-10-30 知情選擇（總管轉述）；判讀＝撰寫組~~ 客戶 2026-11-02 §40＋Q3=A 裁示（「正式 supersede 與此衝突的 DEC-117／DEC-118／相關 DEC-120 mobile exception」）（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留） |
| DEC-089 G6=A 逐檔戰情表 L1 欄位集；Phase 5 線框單檔順序；d25 `target.html`／`holdings.html`（2026-11-02 新增列） | DEC-122（S12、S13、S18） | 部分取代：持股 L1 八欄、單檔 workspace §14 順序；其餘下沉 L2；HTML／線框檔不改 | 客戶 2026-11-02 原文明示（DEC-122） |
| Digest 契約 §4「市場事實刻意不帶 rule」；ONEBRAIN Arch §11 概念 schema（2026-11-02 新增列） | DEC-122（S14、S15） | 部分取代：市場事實可帶 Registry 產生、對映既有 SSOT 門檻的 rule id（⛔ 編造）；OneBrain 輸出最低集改為客戶 §35 欄位（confidence 不納入） | 客戶 2026-11-02 原文明示（DEC-122） |
| DEC-109 三十一 Phase 1～7；DEC-060（Stage 完成回報）；MODEL_EFFORT_POLICY Rule 2（本主線）（2026-11-02 新增列；以上各列皆隨 Freeze 待客戶拍板） | DEC-122（S16、S17、S19） | 部分取代：以 Stage A–J 為準（Digest 凍結前不寫 prompt／glue 仍有效）；Stage 完成回報改用客戶 §48 表；本主線文件同步依客戶 §0 表 | 客戶 2026-11-02 原文明示（DEC-122）；S17／S19 讀法＝撰寫組（INFERENCE） |
| DEC-051／PQ-C6-3（持股頁卡⑤建議持股區間）；DEC-081 Q2-2／`RC-VISIBILITY`；DEC-053；DEC-054 Action 名稱；DEC-109 十三「加／留／換／減」（2026-11-02 新增列） | DEC-122 Q1=A／Q2=A | **不取代、裁示確認**：持股頁區間維持；市場頁 Risk Cap 數值仍隱藏，數值啟用／曝險分母／現金總資產另開 Gate；比例 Action 待正式規則＋驗證＋回測／Shadow＋Gate；「加／留／換／減」僅呈現分組 | 客戶 2026-11-02 Q1／Q2 裁示原文 |
| DEC-122 狀態欄「Freeze 驗收 PASS 後開 Stage A-1」；Freeze §17.4 Stage A 範圍（優先 reuse `src/ui_v2`）；Freeze §17.1 Stage A～E「在現有 New UI 上施工」的路線（2026-11-02 新增列） | DEC-123 | **部分取代（施工路線）**：原 Stage A 暫停；四頁 Final UI 改由 New UI2 Greenfield Presentation Layer 承接（Architecture Gate 先行，送客戶四題 G1／G3′／線框／G2＋#996 合併確認 ~~PENDING~~ 已裁示 Q1～Q4（2026-11-02；Aggregator 屬新 runtime、只凍結契約））；**Freeze 全部 semantic contracts 保留為 New UI2 的 input**；Stage F～J 保留（F 與 UI2 先後依 G3′；J 對象擴為 Old UI 與 Legacy New UI）；#996 定位不變 | 客戶 2026-11-02 原文明示（DEC-123 (5)-0／(5)-2）；Stage 逐項對映＝撰寫組讀法（INFERENCE） |
| DEC-122 Freeze §5.1「Not evaluated 子原因含 `⬜ 未評估／資料不足`」與 Supersede 摘要「DEC-074／075 字樣保留為 Not evaluated 子原因」；Freeze §5.3 Batch 1 註記「第 6 態 `NOT_PROVIDED`」；Architecture Gate §4.6.6 O1 `unjudged→not_evaluated`；Batch 1 契約 Risk Cap `⬜ 無法判定`→Not evaluated（2026-11-02 新增列） | DEC-124 | **部分取代（語意歸類）**：`⬜ 未評估／資料不足` 與 Risk Cap `⬜ 無法判定` 歸 Unable to Determine（字樣不改）；`⬜ 尚未提供`＝capability state（Preview-only、⛔ 第 6 資料態）；`unjudged→undeterminable`；四態定義與「永遠」五條仍有效 | 客戶 2026-11-02 (8) 原文明示（Not Evaluated／Unable to Determine 定義、兩者禁止合併）；DEC-074／075 歸類＝撰寫組讀法（單組，待覆核） |

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

### DEC-105｜UI-M 📊 市場頁三項偏離裁示 1A／2A／3A＋附加指路要求＋其餘四項偏離維持 P2（客戶 2026-10-29）

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S24：第 4 點「指標危險度」指路必須指向「指標明細（16 項）」expander）** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。
> 📌 **1A（結論句位置）部分取代 BY DEC-109**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-109）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：Hero／⚡ 之間的相對順序可維持，但今日結論句**必須落在第一屏**——客戶原文出處：同日前序指示（DEC-109 附錄，客戶 2026-10-29T15:18Z）「今日結論必須在第一屏可見」、DEC-108 ①「結論先行」、DEC-109 四第一屏五問（Presentation Contract §16、Q11）。**2A（五態字樣、不映射偏多／中性／偏空）、3A（指標危險度降階）仍有效**；第 4 點指路**維持有效**（字面須含「指標危險度」、冷／熱 session 皆有、目標 expander「指標明細（16 項）」標題不改）；其**形式**由說明句改為 chip 與否，DEC-109 原文未點名 → 列為 Phase 4 線框待客戶拍板點（`P1R-P4-WF-POINTS`）；第 5 點「Hero 用 4 欄」＝**DEC-105 原意的 P2 偏離，維持**；它與 `CLAUDE.md` v3 §00「固定 3 欄自適應網格」的牴觸**不在本檔重新解釋**，登 BACKLOG `CV1-DR-12` 待客戶裁示（Phase 4 線框待拍板點 W9），裁示前維持現狀。
> 📌 **1A 在 📊 市場頁的相對順序取代 BY DEC-117 Q5；第 5 點「Hero 用 4 欄」在 📊 市場頁取代 BY DEC-117 Q1；第 4 點指路「形式」由 DEC-117 Q2 裁示結案**（2026-10-30 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-117）；append-only，本條原文與上一則 📌 一字未改）：(1) **DEC-117 Q5 在 📊 市場頁取代 DEC-105 1A 的相對順序（結論在 tile 之後）**——新順序＝頁首 → 更新 CTA → 今日結論 → 3 個核心狀態 → ⚡需要處理 → AI／資料狀態 → Primary Visual（客戶原文「我明確同意更新／取代 DEC-105 1A 在市場頁的舊相對順序」）；上一則 📌 的「Hero／⚡ 之間的相對順序可維持」在 📊 市場頁同步失效，「結論句必須落在第一屏」照舊；結論句內容與標題逐字不變（DEC-081 Q2-1）。(2) 第 5 點「Hero 用 4 欄（P2 偏離維持）」→ 📊 市場頁改為**桌機 3 個核心狀態 tile＋「🚀 更新今日戰情」為頁首主 CTA；手機 2＋1**（DEC-117 Q1；`CV1-DR-12` 結案）；第 5 點「AI 佔位＋資料狀態 chip 合併成一行」**維持**，其**位置**由 DEC-117 Q5 取代（⚡ 之後、Primary 之前）；「圖 D 文字指路」「更新鈕字樣未改」兩項 P2 不變。(3) 第 4 點指路：**維持說明句、縮短、不新增 chip**，須保留「指標危險度」「指標明細（16 項）」與指向最上方的關係（DEC-117 Q2）；第 4 點三條測試要求不變。**2A、3A 仍有效。**

> 2026-10-29 補登（ID 取下一個未用號；落盤前 `grep -o 'DEC-[0-9]*' docs/DECISIONS.md` 最大為 DEC-104、DEC-105 0 命中）。要點經總管轉交，**非客戶逐字全文**。

- **決策者**：**客戶**（2026-10-29；經總管轉交之要點）。｜**日期／效力日期**：2026-10-29 起生效。｜**狀態**：生效；UI-M 實作 ~~PR #965 待合併~~ 已合併（PR #965，main `3dad82e0`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（見下方「實作紀錄」）。
- **背景**：UI-M（📊 市場頁，依已核准線框與 A 規格 §4.1）實作後，三項實作層偏離需客戶看過後裁示（`docs/BACKLOG.md` `UIM-LAYOUT-DEVIATIONS` (g)(h)、`UIM-REGIME-WORDING`）。
- **內容**：
  1. **今日結論句＝A**：維持在 Hero 四卡與「⚡ 需要處理」之間。
  2. **市場狀態卡＝A**：維持「市場位階」五態「多頭／震盪／轉守／空頭／未評估」＋「市場位階，不是台股趨勢」；**不得映射成偏多／中性／偏空**。
  3. **指標危險度卡＝A**：降階到「指標明細（16 項）」展開區最上方。
  4. **附加硬要求**：首屏「今日主要風險」卡與圖 D 必須有**清楚指路**到指標危險度，不得因降階造成能力實質隱藏；指路字樣中須出現「指標危險度」四字；展開區最上方確實是該卡；測試釘住（指路句存在於冷／熱 session、指路目標 expander 標題字面存在、expander 內第一張卡含「指標危險度」）。
  5. **其餘四個小偏離維持 P2**（不擴張本批）：Hero 用 4 欄、圖 D「查看全部指標 ›」以文字指路、AI 佔位與資料狀態 chip 合併成 Hero 下一行、更新鈕字樣未改（`UIM-UPDATE-BUTTON-WORDING`）。
- **效力邊界**：不核准任何新資料源／schema／公式／投資語意；不核准 Risk Cap 顯示、正式趨勢定義、EPS×PE、「惡化」判定；不改 `PAGE_LABELS`／`ia_nav`／`app.py`／`page_today`；舊 UI Removal Gate 不變。
- **與其他 DEC 的關係**：落實 DEC-092（設計方向與 Q2／Q3）；與 DEC-081 Q2-1（結論句）同向；DEC-082／v3 §03-2 ①（版面異動須先草稿）— 本條即客戶對偏離的拍板。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本條要點為總管轉交；「與其他 DEC 的關係」為撰寫組讀法，單組。
- 📌 **實作紀錄（2026-10-29 補；加法式；決策者 AI 總管（事實更新））**：~~**狀態＝已實作，PR #965 待合併**~~ **狀態＝已實作並已合併（PR #965，main `3dad82e0`）**（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（分支 `ccr-6eace3b6-0gglrs`，基準 `d0482441`，`git log d0482441..HEAD`）。
  - **commit**（前綴 `feat(UI-M):`）：`ce99f220`（L2 `main_key`＋還原鏈頭節）／`bb2ab542`（薄 L3 圖 A 讀取）／`8b4f54ea`（市場頁落地）／`2a2d16f6`／`9009b786`／`08028336`／`855ab610`（QA-B 修正）／`afca2b22`（QA-A 修正）／`c1b871e0`（QA-C 小修）／`db1c6d2a`（本條 3A 指路句）；其後為本條文件落盤 commit。
  - **改動檔**：`src/compute/macro/macro_helpers.py`（每桶加性 `main_key`）／`src/services/market_twii_view_service.py`（新，L3）／`src/ui/views/_market_blocks.py`（新，L5）／`src/ui/views/page_market.py`；測試 `test_market_blocks.py`、`test_uim_market_page.py`、`test_uim_main_key.py`、`test_market_twii_view_service.py`、`test_uim_revert_chain.py`（還原鏈新頭節，`xvext_revert_for` 第一步呼叫），並修改 `test_page_market.py` 三處因重排而失敗的斷言（理由寫在測試內）。
  - **測試**：Fast lane 全套 32548 passed、1 failed、50 skipped（唯一失敗為已知環境失敗 `test_batch_z59` markdown_it）；mutation 約 27 個逐一拔守衛全數轉紅（首輪 M13、M15 的存活原因與補強見 PR 描述）。
  - **QA 摘要（總管轉述）**：QA-A 0 BLOCKER／1 MAJOR（圖 D 部分覆蓋寫「全綠」，已修）；QA-B（預設直接畫圖 A／B、說明句、佔位字等，已修）；QA-C 0 BLOCKER／0 MAJOR（小修已併）。
  - **已知限制**：手機版面、Streamlit Cloud 冷啟動、Streamlit 1.56 floor 實機行為沙箱驗不到（僅 1.59.2 驗）；圖 A／圖 B 預設直接畫（首屏載入後 1+3 張線圖），若實機偏重屬版面異動須先草稿；`HERO_RISK_MAX_ITEMS` 仍在 L5（`UIM-HERO-MAX-ITEMS-SSOT`，P2）；實作組各項「保留區塊逐字相同」「本頁沒有 AI 呼叫」等結論為單組＋機械 parity，非窮舉。

### DEC-106｜治理執行偏差更正：Stage 起點須比對「目前實際 Model×Effort」與「下一 Stage 最低需求」，已符合時不得停手要求客戶切換（重申 DEC-084）（客戶 2026-10-29）

> 2026-10-29 補登（ID 取下一個未用號；落盤前 `grep -rn "DEC-106" --include=*.md .` 0 命中、`docs/DECISIONS.md` 最大為 DEC-105）。要點經總管轉交，**非客戶逐字全文**。**本條不新增治理規則**，只更正一次執行偏差並重申 DEC-084（`PROJECT_RULES.md` 第 18 節）。

- **決策者**：**客戶**（2026-10-29；經總管轉交之要點）。｜**日期／效力日期**：2026-10-29 起生效。｜**狀態**：生效（偏差已矯正）。
- **事件**：UI-M 完成後，AI 總管回報「需客戶切換 Model×Effort」才開 UI-T；但當時目前設定已是 Sonnet 5.5／Medium，**已符合**下一 Stage（UI-T）的 Minimum Sufficient Effort。依 DEC-084「**一致 → 維持 Silent Autonomous Cruise，直接繼續，不回報檢查結果**」，設定已符合時**不得**停下要求客戶重複切換，或要求客戶回覆「改好了」；應靜默繼續。僅在**不符**時才停手。
- **根因（AI 總管自述）**：Stage 起點沒有先比對「目前實際 Model／Effort」與「下一 Stage 最低需求」，而沿用計畫表／`docs/HANDOFF.md` 既有的「需客戶切換」字樣。
- **矯正**：每個 Stage 起點先比對現況；符合 → 靜默繼續；不符 → 才停手並依 `PROJECT_RULES.md` 第 18.3 節固定格式回報。`docs/HANDOFF.md` Resume Checkpoint 中「等客戶切換才開 UI-T」舊字樣已更正；BACKLOG 登記 `GOV-DEC084-REDUNDANT-STOP-2026-10-29`（P2，已矯正）。
- **與其他 DEC 的關係**：重申並落實 DEC-084（雙向停手 Gate 的「一致則不停」半邊）；與 DEC-104（Hard Output Gate：Model×Effort 需切換且尚未通知才可出聲）同向；不降低任何 Security／Investment／Data／CI／Audit Gate。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：「與其他 DEC 的關係」為撰寫組讀法，單組；docs-only，未改程式碼。

### DEC-107｜UI-T 🎯 標的頁線框五題裁示 1A／2A／3A／4A／5A＋補充邊界（客戶 2026-10-29）
> 📌 **4A 候選表全表外露：部分取代 BY DEC-109（Top-N First，客戶原文明確點名）；1A 版面順序與 UIT 線框「▾ 選股條件（預設展開）」：維持有效、列為 Phase 5 線框待客戶拍板點**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-109）＋AI 總管（總管 2026-10-29 改判：AI 總管讀法不得推翻客戶核准線框）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：(1) **4A**：客戶 DEC-109 十二「Top-N First：產業、候選、風險、排名預設 Top 5～10，其餘收合」明確點名候選 → 候選表外露 Top-N、全表展開（`TOP_N_OPTIONS`／`DEFAULT_TOP_N` 不變）；4A 六欄、籌碼只取選取檔不變。(2) **選股條件「預設展開」維持有效**：這是客戶核准線框的裁示，DEC-108 亦記「改此點須客戶明確回覆」；DEC-109 原文未點名選股條件表單 → 在 Visual Budget 下是否改為「預設收合＋一行條件摘要 chip」，列為 **Phase 5（🎯 標的）線框草稿的待客戶拍板點**（BACKLOG `P1R-P5-WF-SCREEN-COND`；依草稿先行，本 phase 不另開 Gate、不改）。(3) **1A 頁面順序維持有效**；DEC-109 十二「候選標的應更早出現」在 1A 順序內如何落實（例 第二區 header 是否須進第一屏）同列 Phase 5 線框待拍板點（`P1R-P5-WF-POINTS`）。**2A（選一檔＋🔍 查看此檔）、3A（不放 ⚡）、5A 及資料／操作／語意邊界全部仍有效。**
> 📌 **第 1 點（1A 整頁單頁全展開順序）部分取代 BY DEC-122**（2026-11-02 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-122）；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S1）：客戶 2026-11-02 §10～§12：頂部 [ 市場精選 ][ 即時查一檔 ] 雙模式、不得同時完整展開、查詢後自動收合精選；單檔 workspace 順序改依 §14（Header→6 維 Snapshot→Primary Price Chart→Fundamental→Valuation→Institution／Chip→Industry→Risk→OneBrain）。**仍有效**：2A（選一檔＋🔍 查看此檔＝精選模式進入研究 workspace 的入口）、3A、4A 六欄、5A、補充邊界（不新增資料源／公式／投資語意／Risk Cap／AI 新規則；**不寫 Sheet**；缺維度一律 ⬜；手機第一屏不放工程字樣）、效力邊界。兩邊理由：舊順序讓兩個任務在一頁一次看完（仍成立）；新雙模式依客戶明示「系統替我找」與「我指定一檔研究」必須明確切開。

> 2026-10-29 補登（ID 取下一個未用號；落盤前 `grep -o 'DEC-[0-9]*' docs/DECISIONS.md` 最大為 DEC-106、DEC-107 0 命中）。要點經總管轉交，**非客戶逐字全文**。

- **決策者**：**客戶**（2026-10-29；經總管轉交之要點）。｜**日期／效力日期**：2026-10-29 起生效。｜**狀態**：生效；~~UI-T 已實作於分支 `uit-impl`（PR #968（合併 SHA 由總管合併後同步））~~ 已合併（PR #968，main `9ec555e7`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；非 done-verified（待客戶實機點驗）。
- **背景**：DEC-099／UI-T-ACCEPT-NAV1-TRANSITION 要求把「🔍 找標的＋🔬 查一檔」整合為單一 🎯 標的頁並移除 NAV-1 過渡切換；版面與動線異動須先草稿（`CLAUDE.md` §-1.5.D v3 §03-2 ①），草稿＝`docs/vnext/NEWUI_D25_UIT_WIREFRAME_2026-10-29.md`。
- **內容（五題皆選推薦方案 A）**：
  1. **A**：整頁順序＝問句→資料狀態→搜尋（判型／期間／均線收進「進階選項」摺疊，MA 保留並標「僅顯示」）→AI 佔位→第一區（板塊圖降為展開區）→第二區→第三區（個股七區塊／ETF 另一版型）→進階分析（多檔比較）。
  2. **A**：候選表下方「選一檔＋🔍 查看此檔」（不用 dataframe 點列；使用者明確操作後才取數）。
  3. **A**：資料狀態「⬜ 尚未彙總」、AI「⬜ 尚未提供」；**不放**「⚡ 需要處理」。
  4. **A**：候選表六欄（標的／產業／基本面／估值／籌碼／狀態）；產業用既有對映；估值＝當日本益比並標明與第三區 357 口徑不同；籌碼只對選取那檔取數，其餘「未取」。
  5. **A**：「仍未覆蓋」功能於進階分析以白話揭露。
  - **補充邊界**：不新增資料源／公式／投資語意／Risk Cap／AI 新規則；不寫 Sheet；缺維度一律 ⬜；移除 NAV-1 過渡切換；手機第一屏不放工程字樣。
- **效力邊界**：不核准任何新資料源、schema、公式、投資語意；不改 `PAGE_LABELS`／`ia_nav`（legacy D2 殼仍用）、`src/ui/tabs/**`、`src/ui/etf/**`、`decision_digest*`；舊 UI Removal Gate 不變。
- **與其他 DEC 的關係**：落實 DEC-092（設計方向）與 DEC-099（過渡切換移除）；與 DEC-097（legacy 入口不得出現在一般使用者導覽）並存，故 S9 不放指路（見偏離 2）；與 DEC-103（範圍膨脹防護）一致，新發現皆登記 P2。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本條要點為總管轉交；「與其他 DEC 的關係」為撰寫組讀法，單組。
- 📌 **實作紀錄（2026-10-29 補；加法式；決策者 AI 總管（事實更新））**：分支 `uit-impl`（基準 `4521fc39`）；~~PR #968（squash SHA 由總管合併後同步）~~ 已合併（PR #968，main `9ec555e7`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。
  - **commit**（前綴 `feat(UI-T):`／`fix(UI-T):`／`test(UI-T):`）：`f942bd80`（新頁＋薄 L3＋守衛）／`94627c92`（移除過渡切換＋`app.py` 最小分流）／`29ae9cb5`（意外 loader 例外只呈現一次）／`7052afcb`（突變補強＋BACKLOG）／`cfc0944d`（QA 回修）／`8db04008`（TTL 表靜態守衛）；其後為本條文件落盤 commit。
  - **改動檔**：新增 `src/ui/views/page_target.py`、`src/ui/views/_target_blocks.py`、`src/services/target_industry_service.py`（薄 L3，既有 `ticker_sector.json` 唯讀視圖）、`tests/uit_fakes.py`、`tests/test_uit_target_page.py`、`tests/test_uit_target_page_qa.py`；修改 `shared/ia_nav4.py`（移除葉常數與函式，新增 `MERGED_VIEWS`，`reconcile_nav4` 同步）、`src/ui/views/shell_nav4.py`（移除葉選擇器）、`app.py`（僅 `_ia_view_find()` 依旗標分流＋一行註解）、`tests/test_batch_z60.py`（`_BASE_DIGEST`）與 `test_nav1_*`／`test_p0x_view_mount_claims` 的有理由改寫。`page_find.py`／`page_inspect.py` **一字未改**。
  - **測試**：Fast lane 全套 32685 passed、1 failed、50 skipped（唯一失敗為已知環境失敗 `test_batch_z59` markdown_it）；UI-T 專屬 138 項；slow 全套（回修前）183 passed、回修後 nav1／sidebar 相關子集 45 passed；mutation 回修前 24 個＋回修後 17 個，逐一拔守衛全數轉紅（存活者 M5、M19、N3 補強後轉紅）。
  - **QA 摘要（總管轉述）**：三組獨立 QA 0 BLOCKER；2 MAJOR（結果記在 session 後靜默過期＝§2.4；`chips_cell`「取數失敗」分支無測試）與數個 P1（查看此檔沿用判型覆寫、值得看列出低分、無指路、文案）已於 `cfc0944d` 回修並補測試與突變。
  - **與線框的偏離（逐項）**：(1) 產業矩陣手機版已改為每產業一張卡片列（回到線框；playwright 390px 驗無橫向捲動），`UIT-MOBILE-MATRIX` 已處理；(2) S9 不放「回舊畫面」指路（遵 DEC-097），只寫「新版尚未提供，後續批次處理」＝`UIT-S9-NO-POINTER`，**待客戶一句話確認，總管推薦同意**；(3) 第三區多一張既有判型結果卡、獲利能力區塊自行安置、排列與 `target.html` 不同＝`UIT-JUDGE-CARD-EXTRA`；(4) 候選表估值資料日寫「⬜ 未提供」（L1 無日期欄）＝`UIT-PE-ASOF-MISSING`；(5) 均線說明改為「僅顯示：勾選只會回顯在判型結果；K 線與均線圖新版尚未接上，不影響任何結論。」（`UIT-MA-DISPLAY-ONLY-WORDING`）。
  - **內部拍板**：新增 `page_target`／`_target_blocks` 而不改舊兩頁（legacy D2 殼可獨立渲染）；`ia_nav4.MERGED_VIEWS`（inspect 併入 p4_target，view id 與 renderer 保留給 legacy）；每個使用者要求的結果以「session 世代 memo＋載入時間提示（超過 `shared/ttls` TTL 改「可能已過期」）」記住到下一次要求（操作隔離＋失敗不被轟炸，非快取層，`UIT-RESULT-MEMO-NOT-REFRESHED`）；新頁只認自己 gate 寫入點的世代（`own_*` 請求），legacy 殘留已套用值不觸發取數；「查看此檔」判型一律 auto。
  - **已知限制（沙箱驗不到）**：Streamlit Cloud 冷啟動、手機實機（iOS／Android、768px 斷點邊界）、`requirements.txt` floor 1.56 實機行為（沙箱僅 1.59.2；`st.form` 內放 expander 為推論）、載入板塊地圖／查看此檔實際等待時間；見 `UIT-CLOUD-MOBILE-VERIFY`。實作組各項結論（含「舊兩頁能力全數有對應位置」）為單組＋機械 parity，非窮舉。
  - **P2 登記**：`UIT-MOBILE-MATRIX`（已處理）、`UIT-MA-DISPLAY-ONLY-WORDING`、`UIT-PE-ASOF-MISSING`、`UIT-PE-DOUBLE-READ`、`UIT-RESULT-MEMO-NOT-REFRESHED`、`UIT-QUADRANT-ORDER-SSOT`、`UIT-ERROR-FRAME-LEGACY-NAME`、`UIT-CLOUD-MOBILE-VERIFY`、`UIT-S9-NO-POINTER`、`UIT-HOLD-DEADLINK-INSPECT`、`UIT-COLD-POISON-WEAK`、`UIT-JUDGE-CARD-EXTRA`、`UIT-OLD-CARD-ENG-WORDS`。


### DEC-108｜新 UI 視覺方向修正批次：十項視覺原則＋凍結後續頁面正式視覺實作直到核准修正版線框（客戶 2026-10-29）

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S42：十項視覺原則中「其餘收合到『查看依據』」「『查看依據』的收合層級規則」的頁內收合通則；僅限 New UI2）** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。
> 📌 **部分取代 BY DEC-109**（2026-10-29 有意識的政策變更，不是漏刪；決策者 客戶（DEC-109）；append-only，本條原文一字未改；判讀出處 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）：客戶 DEC-109 一「目前不要繼續依 #970、DEC-108 或較早的 Presentation／Wireframe 規則往下施工。#970 暫時不要合併。它只作為：舊一輪視覺修正草稿與歷史輸入資料」。**十項視覺原則仍有效**，由 DEC-109 Presentation Contract 具體化（③「圖表縮小」讀為**主圖外露但縮小**，DEC-110 R2）；線框草稿 §客戶待確認 5 題**撤回**；**第 3 點凍結的解除條件改寫為：Phase 1 契約合併後依 Phase 2→7 推進，每個 UI phase 過 Visual Fidelity Gate**（`docs/governance/UI_VISUAL_FIDELITY_GATE.md`）。「線框 Q4 若選 A 將推翻 DEC-107 第 1 點」一句：DEC-107 第 1 點維持有效，改列 Phase 5 線框待客戶拍板點（DEC-110 R3）。線框草稿檔已自本分支移除（原貌只保存在 PR #970 commit `06a7a3e5`）。

> 2026-10-29 補登（ID 取下一個未用號；落盤前 `grep -c DEC-108 docs/*.md docs/vnext/*.md PROJECT_RULES.md` 全 0 命中、最大為 DEC-107）。要點經總管轉交，**非客戶逐字全文**。

- **決策者**：**客戶**（2026-10-29；經總管轉交之要點）。｜**日期／效力日期**：2026-10-29 起生效。｜**狀態**：~~生效；線框草稿 `docs/vnext/NEWUI_D25_UI_CORRECTION_WIREFRAME_2026-10-29.md` **待客戶核准**（未回覆＝不核准、不動工）。~~ **部分取代 BY DEC-109**：十項原則仍有效；線框草稿不再待核准（5 題撤回；檔案已自本分支移除，原貌只保存在 PR #970 commit `06a7a3e5`）；凍結解除條件改為「Phase 1 契約合併後依 Phase 2→7 推進，每個 UI phase 過 Visual Fidelity Gate」（2026-10-29 有意識的政策變更，不是漏刪，決策者 客戶（DEC-109））。
- **背景**：客戶認為目前新 UI（📊 市場、🎯 標的、💼 持股）的畫面方向與先前核准的參考圖（mockup `docs/vnext/d25_wireframes/*.html`，DEC-092）差異過大。客戶自承偏差六點：結論區太下面（第一屏看不到）、圖表太大、空白太多／資訊密度不對、文字太多不像儀表板、板塊感不夠（變長表格／長段落）、與先前核准 mockup 差異太大。
- **內容**：
  1. 開 **docs-only 設計修正批次**：不改資料邏輯，把版型與資訊層級拉回客戶要的方向。
  2. **視覺原則十項**：①結論先行（每頁第一屏先看到現在狀態／是否需行動／下一步）②卡片優先（卡片、icon、chip、badge，不要長段文字）③圖表縮小（只保留判斷必要尺寸；能用 sparkline／小型趨勢圖就不用大圖）④文字極簡（每區塊最多 1 句，其餘收進「查看依據」）⑤避免長表直出（產業機會、風險清單、候選標的優先改卡片／ranking／精簡表）⑥手機優先（第一屏不被大圖、長說明、工程控制項占滿）⑦圖示化（狀態、風險、資料新鮮度、分類、判型盡量用圖示／chip）⑧板塊感（像儀表板，不像報表頁或研究頁）⑨明細收合（依據、公式、來源、例外全進下層）⑩對齊已核准參考圖（以先前核准 mockup 為主，不要自由發散）。
  3. **凍結**：在客戶核准修正版線框前，**不得繼續擴張後續頁面（UI-H 其餘、UI-ME）的正式視覺實作**。
  4. **邊界**：只修版型與資訊階層；不新增資料源、不改公式、不改投資語意；不順手擴大；舊 UI 邏輯可參考，但新 UI 視覺回到核准 mockup 方向。
- **效力邊界**：本條不核准任何新資料源、schema、公式、投資語意、AI 接線；不改 `PAGE_LABELS`／導覽殼／legacy 入口（DEC-097）。已合併的 UI-M（#965）、UI-T（#968）**不被本條自動回退**，是否／如何改由線框核准後的 E0～E2 批決定。
- **與其他 DEC 的關係**：呼叫 DEC-092（核准 mockup 與設計方向）、DEC-082（草稿先行）、DEC-103（範圍膨脹防護）；線框 Q4 若選 A 將**推翻** DEC-107 第 1 點中「選股條件預設展開」一處（須客戶明確回覆才生效）；DEC-081 Q2-1（今日結論句）**原句保留**，只改位置。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：docs-only 撰寫組只落盤裁示與線框草稿，不改程式碼；本條要點為總管轉交、非客戶逐字全文；線框的偏差量測為**冷啟動**畫面（已載入狀態未驗）；單組撰寫、未經第二組驗。
- 📌 **客戶原文逐字補登（2026-10-29；append-only，上文一字未改；有意識的更新，不是漏刪，決策者 AI 總管（事實更新））**：上文要點為總管轉交；客戶 2026-10-29T14:56:48Z 原訊息（本 session，自 session 紀錄逐字取出）補錄如下，供 Context Loss Check 與後續比對（與要點有出入時以原文為準）：

```
目前新 UI 的畫面方向與我原本核准的參考圖差異過大，先不要直接照現在的版型繼續擴張到後續頁面。
先開一個 docs-only 的設計修正批次，目的不是改資料邏輯，而是把新 UI 的版型與資訊層級拉回到我原本要的方向。若目前模型 / Effort 已符合，直接靜默執行，不要再停下要求我重複切換。
這次要先承認的偏差
目前成品有以下問題：

1. 結論區太下面，第一屏看不到。
2. 圖表太大，佔太多空間。
3. 空白太多，資訊密度不對。
4. 文字太多，不像儀表板。
5. 板塊感不夠，變成長表格 / 長段落。
6. 和我之前核准的 mockup / 參考圖差異太大。

新的視覺原則（正式作為修正方向）

1. 結論先行：每頁第一屏先看到「現在狀態 / 是否需行動 / 下一步」。
2. 卡片優先：以板塊卡片、icon、chip、badge 為主，不要長段文字。
3. 圖表縮小：圖表只保留判斷必要尺寸；能用 sparkline / 小型趨勢圖就不要用大圖。
4. 文字極簡：每個區塊最多 1 句說明，其餘收合到「查看依據」。
5. 避免長表直出：像產業機會、風險清單、候選標的，優先改成卡片 / ranking / 精簡表，不要先丟大表。
6. 手機優先：手機第一屏不能被大圖、長說明、工程控制項占滿。
7. 圖示化：狀態、風險、資料新鮮度、分類、判型盡量用圖示／chip 表達，不要純文字堆疊。
8. 板塊感：每頁都要像儀表板，不像報表頁或研究頁。
9. 明細收合：詳細依據、公式、來源、例外情況，全部收進下層。
10. 對齊已核准參考圖：以我之前核准的 mockup 為主，不要自由發散。

這次批次要交付的內容（docs-only）
請不要先改大量 UI code，先交付一份修正版 wireframe / plan，至少包含：
A. 全站共通版型規則

* 首屏固定結構
* 卡片尺寸規則
* 圖表尺寸規則
* 手機 / 桌機的板塊排列規則
* 文字長度上限規則
* 「查看依據」的收合層級規則

B. 三頁優先修正版線框
至少重畫：

1. 📊 市場頁
2. 🎯 標的頁
3. 💼 持股頁

每頁都要明確標示：

* 第一屏有哪些卡
* 哪些內容移到下層
* 哪些大圖改成小圖
* 哪些長表改成板塊卡 / 精簡榜單
* 哪些說明縮成一句話

C. 偏差對照表
做一張「目前畫面 vs 修正後畫面」對照表，逐項列：

* 哪裡太大
* 哪裡太空
* 哪裡文字太多
* 哪裡不像板塊
* 如何修正

必須特別修正的方向
市場頁

* Hero 區要更像總覽卡，不要讓大圖把畫面往下推。
* 圖 A / 圖 B 類的大圖要縮，必要時改成小型趨勢圖。
* 主要風險改成精簡風險卡 / 風險 chip，不要大片文字。

標的頁

* 「產業機會」不要先丟大表格。
* 優先改成：Top 產業卡 / 排名卡 / 精簡榜單，再進一步展開明細。
* 「單一股票」區不要一開始就是大片詳細文字，先做摘要卡，再展開分析。

持股頁

* 第一屏先看到：整體持股狀態、存股 vs 資本利得分類、是否需要調整。
* 不要先給大段細節或報表。
* 先有 AI 總結，再往下看分類、風險、個股明細。

邊界

* 這批先修版型與資訊階層，不是改投資邏輯。
* 不新增資料源、不改公式、不改投資語意。
* 不因這批順手擴大到其他非必要功能。
* 舊 UI 邏輯仍可參考，但新 UI 視覺上要回到我核准過的 mockup 方向。

回報方式
整批完成後一次回報：

* PR 連結
* 哪三頁重畫
* 目前版型偏差如何修正
* 哪些地方之後才進正式 UI code

在這份修正版線框我核准前，先不要繼續擴張後續頁面的正式視覺實作。
```

### DEC-109｜Phase 1 SSOT Reset／Contract Freeze：Presentation Contract＋Visual Budget＋Visual Fidelity Gate＋Blueprint＝Visual SSOT＋Decision Digest Contract＋One AI Brain boundary＋GitHub Durable Memory＋SSOT Precedence＋舊規格 supersede／cleanup＋UI 簡化不得降低 AI 判斷力＋AI 投資總結新輸出格式（客戶 2026-10-29）

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S21／S26：四（第一眼／第二眼／第三層判準）、五（圖表標頭「▸ 為什麼／來源／限制／去哪補」）、六（詳細文字下沉＝頁內收合）、七（頁內 L3 可展開）；十五～十七與五問等其餘維持）** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。

> 📌 **例外登記（非取代）BY DEC-117 Q7**（2026-10-30；決策者 **客戶**（DEC-117）；append-only，本條原文一字未改）：四「第一屏五問」③主要圖、十一「📊 市場頁設計方向」第一屏優先「主要市場圖」、附錄（同日前序指示 15:18Z）「四、目前三頁修正方向 📊 市場」第一屏優先「小型台股趨勢圖」——📊 市場頁**手機版**由客戶核准合理 mobile exception（Primary Visual 可位於第一屏下方；手機第一屏優先序＝今日結論 > 核心狀態 > 是否需行動 > Primary Visual；Primary 須緊接 L1 決策區、不得被 L2／L3 插隊）。例外**只豁免 Primary**：五問④「是否需要行動」在手機仍須在第一屏（線框 §10 C1-10，AI 總管內部判定）。桌機與其餘各頁、本條其餘各項全部照舊（附錄「今日結論必須在第一屏可見」由 DEC-117 Q5 同向加強）。
> 📌 **三十一「執行階段」Phase 1～7 編號部分取代 BY DEC-122**（2026-11-02 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-122）；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S16）：Final UI 主線改以 **Stage A–J**（A 共用呈現基礎→B 市場→C 標的→D 持股→E 我的／Audit→F Headless Decision Digest→G OneBrain Runtime→H Cross-page Consistency→I Real-data／Mobile Acceptance→J Old UI Removal Gate）為準；Phase 7 拆為 F＋G，且 G 不得早於 F 合格。**仍有效**：「不得在 Decision Digest contract 未凍結前直接開始寫新的 LLM prompt／glue」、「具體 dependency 可以調整」；Phase 1～5 已完成成果不回退；本條十五～十七（三條 invariant 的前身，DEC-122 重申）與其餘各點。兩邊理由：舊 Phase 編號貼合當時頁面主線（仍成立）；新 Stage 依客戶明示把 Headless Digest 與 OneBrain 拆開並新增跨頁一致性、真資料驗收與舊 UI Removal Gate。
> 📌 **十一（📊 市場第一屏優先）、十三（💼 持股第一屏優先）、二十一（AI 投資總結輸出）與 DEC-122 的對映**（2026-11-02 登記；決策者 客戶（DEC-122 指示）＋AI 總管〔判讀，INFERENCE〕；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S20）：**十一**不取代、同向——客戶 §6 新增 System Action State、OneBrain Outlook；「今日主要風險」「主要市場圖」仍有效~~（手機位置待 DEC-122 Q3）~~ （手機：DEC-122 Q3=A——緊接第一屏之後、仍屬 L1）。**十三**：客戶 §19 新增 Risk Cap、目前曝險為第一屏項目（加性）；「加碼／留／換／減摘要」與客戶 §20 五詞（加碼／持有／減碼 1/2／全出）的關係~~**條件式待 DEC-122 Q2**，裁示前本條字樣照舊~~ **依 DEC-122 Q2=A 處置**（見下一則 📌）（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留）。**二十一**不取代——客戶 §35 是 OneBrain domain output schema，二十一是呈現切片；「本期行動 ≤3」須引用 `system_action_ref`。
> 📌 **十三「加碼／留／換／減摘要」依 DEC-122 Q2=A 處置；十一手機位置依 Q3=A**（2026-11-02；決策者 **客戶**（DEC-122 裁示）；append-only，本條原文與上兩則 📌 一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S20）：上一則（裁示前登記）的十三部分已結案——「加／留／換／減」**只作呈現分組**，分支名一律沿用既有 deterministic rule 原名，⛔ 藉分組創造新投資語意；「減碼 1/2」「全出」⛔ 映射或產生。十三其餘第一屏項目仍有效（Risk Cap、目前曝險為加性項）。十一「今日主要風險」在手機上緊接第一屏之後、仍屬第一層（Q3=A）。

> 2026-10-29 補登（ID 取下一個未用號；落盤前 `git grep -n "DEC-109\|DEC-110"` 全 repo 0 命中、`docs/DECISIONS.md` 最大為 DEC-108）。**客戶 2026-10-29 逐字**（來源類別 D：客戶訊息 2026-10-29T16:03:29Z，本 session；自 session 紀錄逐字取出，未改一字）。本條只落盤裁示與 Phase 1 文件，**不改任何產品 code／測試／navigation，不改 `CLAUDE.md`／`PROCESS.md`**。

- **決策者**：**客戶**（2026-10-29）。｜**日期／效力日期**：2026-10-29 起生效。｜**狀態**：生效；Phase 1 落盤＝本分支 `ccr-6eace3b6-0gglrs` 新 docs PR（#970 標 superseded、不合併）；Phase 2～7 未開工。
- **落地文件（Phase 1）**：`docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md`（Presentation Contract＋Visual SSOT）、`docs/governance/UI_VISUAL_FIDELITY_GATE.md`、`docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md`、`docs/vnext/ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md`、`docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md`、`docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md`、`docs/vnext/visual_fidelity/phase1_baseline/VISUAL_GAP_AUDIT_2026-10-29.md`、`tools/visual_fidelity/`；治理 `PROJECT_RULES.md` 第 24～26 節；PR 模板「Visual Fidelity」段。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：

```
先重新執行完整 GitHub Verification Gate，再開始任何動作。
我方最新實查：

* main：`978ecedc000ec18b82f18f5e7508374ba0abeaa6`
* 這個 main commit 是每日總經歷史增量；其 parent 為 `7158785708ef97cba0357cd04f5a91d31e45bbbb`
* Open / Draft PR：目前只有 #970
* #970：open、未合併，base 還是 `7158785708ef97cba0357cd04f5a91d31e45bbbb`
* 因此 #970 已落後 current main

若你重新查到更晚狀態，以 GitHub 最新實況為準。
一、立即停止舊 UI 施工方向
目前不要繼續依 #970、DEC-108 或較早的 Presentation / Wireframe 規則往下施工。
#970 暫時不要合併。
它只作為：
舊一輪視覺修正草稿與歷史輸入資料。
先做：
SSOT Reset + Presentation Contract Migration + Decision Digest Contract
完成後，再決定 #970：
A. 關閉並標記 superseded
B. 吸收仍有效內容後重做
C. rebase 後改寫為新的正式 docs PR
不得直接把 #970 當新的 production baseline。
二、本輪目的
這不是 CSS 美化。
這一輪要修的是：

1. 舊 Presentation Contract
2. Visual SSOT
3. Visual Fidelity Gate
4. Decision Digest Contract
5. One AI Brain boundary
6. GitHub durable-memory governance
7. 舊規格 supersede / cleanup
8. UI 簡化與 AI Decision Context 分離

核心目標：
簡單看懂，但不犧牲判斷力。
正式產品原則：
Simple Decision Dashboard, not Report Wall and not Chart Wall.
三、資訊呈現最高優先序
正式採用：
圖表 > 數字 > 短句 > 長文字
但注意：
Visual Priority does not mean Visual Quantity.
不是圖越多越好。
每頁正常 Visual Budget：

* 1 個 Primary Visual
* 最多 2～3 個 Secondary Visual
* 第一屏最多 3～5 個核心數字 / status chips
* 最多 1 句主要判讀
* 詳細證據預設下沉

若超過 Visual Budget，依序優先：

1. 合併
2. 切換
3. 下沉
4. 收合

禁止：

* Report Wall
* Chart Wall
* 第一屏同時多張大型圖互搶視覺權重
* 每個欄位各自畫一張圖
* 用大量 donut / pie 填滿頁面
* 把文字牆單純換成圖表牆

四、第一屏固定回答
正常決策頁第一屏必須優先回答：

1. 現在狀態
2. 重要數字
3. 主要圖
4. 是否需要行動
5. 下一步

如果一頁無法明確回答：

* 第一眼看什麼？
* 第二眼看什麼？
* 第三層才看什麼？

則：
Visual Fidelity FAIL
五、圖表 Presentation Contract
每張主圖上方最多只放：

* 圖表標題
* 3～5 個 metadata / status chips
* 1 句白話說明

例如：
台股加權指數
`資料 10/29` `來源 TWSE` `近 60 日` `✅ 可讀`
「近 60 日仍維持上升，但短線動能放緩。」
接著直接是圖。
下方：
`▸ 為什麼／來源／限制／去哪補`
不要在圖上方放一整篇說明。
六、詳細文字下沉
以下資訊必須保留，但正常情況預設收合：

* 為什麼
* 資料來源
* as_of
* 計算口徑
* 公式
* threshold
* policy reference
* 限制
* Missing 原因
* unavailable 原因
* 去哪補
* provenance
* 工程術語
* service / helper / Lx 等工程資訊

主畫面只留：

* 狀態
* 關鍵數字
* 圖
* 1 句摘要

七、正式遷移「現在／為什麼／去哪補」
舊 contract 中：
「現在／為什麼／去哪補」承載的資訊不能刪除。
但正式取消：
三者必須全部常駐主畫面。
新 contract：
資訊必須存在、可取得、可追溯、可展開，但不要求全部外露。
請完整盤點：

* Note contract
* `V2_SHORT_ROWS`
* card helpers
* rendering helpers
* tests
* wireframes
* blueprint
* DEC / governance
* legacy 三列短句要求

如果現有 test 驗證：
「三段文字一定要顯示在頁面」
請改成驗證：

* 資訊沒有遺失
* 正確資料可取得
* 詳細說明可展開
* provenance 可追溯
* Missing 語意未改

八、Missing Contract 不變
資料治理不能因 UI 簡化而改掉。
維持：

* missing ≠ 0
* missing ≠ neutral
* unavailable ≠ neutral
* not evaluated ≠ safe
* missing ≠ HOLD
* AI 不得補值

但 UI 顯示改成：

* placeholder
* chip
* compact status card

不要拿大段文字填滿頁面。
九、共用 Metadata / Status Chips
優先建立共用呈現方式：

* source
* as_of
* retrieved_at（若既有）
* stale
* freshness
* unavailable
* estimated / proxy
* coverage
* data quality

不要每一張卡重複寫：
「這筆資料來自……目前資料日……可能因為……」
用 chip / metadata component 取代。
十、台股 IA 先維持目前正式四頁
不要因這次改造自行增加或刪除頂層頁面。
目前維持：

1. 📊 市場
2. 🎯 標的
3. 💼 持股
4. 👤 我的

若發現現有正式 spec 與此不一致：
先做 conflict analysis。
不要自行改 IA。
十一、📊 市場頁設計方向
這頁回答：
現在市場環境好不好？可以承擔多少風險？
第一屏優先：

* 市場位階
* Risk Cap / 尚未核准狀態
* 今日主要風險
* 是否需行動
* 主要市場圖

Primary Visual：
以最能回答「目前市場環境」的圖為主。
可以考慮：

* 台股 / 美股 / VIX / 利率 / 美元
* 主圖切換器
* segmented control
* small multiples

但不要同時把全部畫成大型圖。
Secondary Visual：
最多 2～3 張。
EPS×PE 若 production definition 尚未核准：
維持 placeholder / 尚未核准。
不得為了畫面完整自行建立公式或假圖。
十二、🎯 標的頁設計方向
這頁回答：
現在有哪些值得看的產業與股票？
目前最大的問題要優先修：
不要再：

* 先攤開 30～40 個產業長卡
* 每個產業重複顯示相同 Missing 說明
* 候選標的被推到很後面

Primary Visual：
產業強弱 / 資金動能 / 機會分布。
優先形式：

* Top 5
* ranking
* heatmap
* bubble
* compact sector tiles

完整產業清單：
收合 / drill-down。
候選標的：
應更早出現。
單一股票：
先顯示摘要卡＋主要圖，再展開完整分析。
Top-N First：
產業、候選、風險、排名預設 Top 5～10，其餘收合。
十三、💼 持股頁設計方向
這頁回答：
我的持股該加、留、換、減什麼？
第一屏優先：

* 目前該做什麼
* 需處理幾檔
* 加碼 / 留 / 換 / 減摘要
* 主要風險
* 組合狀態
* Primary Visual

Primary Visual 可依實際資料選：

* 持股配置
* 風險分布
* 損益分布
* 核心 / 衛星
* 主要曝險

Secondary Visual 最多 2～3。
VaR、壓力測試、配息、完整規則、門檻、分母：
不得全部第一層外露。
投資目的分類仍保留：

* 存股
* 資本利得
* 未分類

AI 不得自行推測分類。
十四、👤 我的
這頁不是分析頁。
不用硬塞圖表。
主要承載：

* Google / account
* Sheet
* portfolio
* watchlist
* strategy classification
* 低頻設定
* 資料健康 / 診斷入口

是否把 Google login 固定左側：
本輪先依既有台股正式 IA / mobile constraints 做 conflict analysis。
不要直接照搬其他專案。
十五、UI 簡化不得降低 AI 判斷力
正式新增硬規則：
Presentation Simplification must never reduce AI Decision Context.
UI 可以：

* 少顯示
* 聚合
* Top-N
* 收合
* 隱藏工程細節
* 圖像化
* 用摘要取代長文字

但不得因此刪除或降低：

* canonical data
* normalized data
* provenance
* source
* as_of
* stale / freshness
* missing / unavailable
* deterministic rule outputs
* indicator outputs
* Risk Cap inputs / outputs
* market data
* international data
* sector data
* candidate data
* holdings data
* strategy classification
* identity
* relevant history
* AI Decision Context

十六、正式建立 Decision Digest Contract
架構正式朝：
Raw Sources
→ Canonical Data
→ Deterministic Rules / Indicators / Risk Cap
→ Decision Digest
→ One AI Brain
→ UI Local Summary / AI 投資總結
正式寫入：
Data View ≠ Decision Context ≠ AI Output
Decision Digest 是：
AI 的完整、結構化、可追溯決策輸入層。
它不是 UI scrape。
十七、AI 不得從 UI 反推資料
One AI Brain 不得：

* scrape Streamlit 文字當 canonical data
* 從顏色猜狀態
* 從 widget 顯示文字推斷數據
* 因 expander 收合就不讀某資料
* 因 UI 沒顯示某指標就認定不存在
* 從 UI Top-N 認為只有 Top-N 資料存在

Decision Digest 必須直接由：
canonical data + formal rule results
建立。
十八、Decision Digest 最低概念契約
不要現在建立巨大 schema。
先盤點 repo 既有結構，建立 minimum sufficient contract。
每個可判斷項概念上至少保留：

* identifier
* value / result
* unit（如適用）
* source
* as_of
* retrieved_at（若已有）
* stale / freshness
* missing / unavailable
* provenance
* rule result
* relevant threshold / policy reference
* confidence / evidence state（只有既有正式語意才保留）

不得創造新的 confidence 語意。
十九、One AI Brain
沿用既有正式方向：
One AI Brain, Many Data Views
不是：

* 市場一套 AI
* 標的一套 AI
* 持股一套 AI
* 最後再另一套 AI

各頁只提供：

* Data View
* Rule Result
* Local Explanation
* scoped AI summary（需要時）

Local AI Summary 必須來自：
同一 Brain + 同一 Decision Digest 的對應 slice。
避免跨頁 AI 結論互相矛盾。
二十、🤖 AI 投資總結定位
目前 repo 已有 One AI Brain / AI 投資總結方向。
本輪先盤點其正式入口與 spec。
不要自行增加第五個頂層頁。
若現有正式設計是：

* 頁內集中區
* 固定入口
* 其他形式

先保留並分析。
只有真的需要 page-count / IA 變更時：
整理成單一最小 Decision Gate。
二十一、AI 投資總結不是資料頁
AI 投資總結只回答：

1. 現在整體環境如何？
2. 最大的 1～3 個變化是什麼？
3. 我的持股是否需要動？
4. 是否有新的值得看的機會？
5. Risk Cap 是否限制行動？
6. 哪些地方因 Missing 無法判斷？

目標輸出：
市場
一句
持股
一句
標的機會
一句
主要風險
1～3 點
本期行動
最多 3 項
每一項都可以：
`查看依據`
回到：

* Decision Digest
* canonical evidence
* rule result

禁止：

* 把所有市場圖重畫一次
* 把持股表再複製一次
* 重複候選表
* 長篇 AI essay
* 成為另一個 Report Wall

二十二、現有 build_ai_summary 不得直接視為 One AI Brain
完整盤點現有：
`build_ai_summary`
至少確認：

* input
* scope
* provenance
* missing handling
* freshness
* Risk Cap integration
* cross-page consistency

如果它目前只是：
holdings digest / 舊持股 AI summary
則只能標：
partial / legacy building block
不得宣稱 One AI Brain 已完成。
先決定：

* reuse
* refactor
* replace

不得只因函式名稱有 summary 就當作符合新架構。
二十三、Visual Fidelity Gate
正式升成 UI Stage 完成條件。
每個 UI PR 至少需要：

* desktop screenshot
* mobile 390px screenshot

對核准 blueprint 檢查：

1. 第一屏結構
2. Primary Visual 是否突出
3. 圖表 / 文字比例
4. 卡片密度
5. 空白比例
6. 圖表大小
7. Top-N
8. 詳細文字是否下沉
9. Missing 是否用 placeholder
10. 主要 CTA / 行動是否首屏可見
11. mobile 是否被大表、大圖、長文塞滿

正式規則：
CI / QA / tests / mutation 全綠 ≠ UI Stage complete。
若 screenshot 與 blueprint 在：

* 資訊層級
* 圖文比例
* 第一屏
* Visual Budget
* 圖表尺寸
* 卡片密度

明顯偏離：
Visual Fidelity FAIL。
二十四、Blueprint 地位
核准 blueprint 不再只是參考圖。
正式定義：
blueprint = Visual SSOT / visual acceptance baseline
Production 可以因：

* 真資料
* Streamlit 限制
* mobile constraint

做合理調整。
但不可自行改掉：

* 第一屏資訊順序
* 主圖 / 次圖層級
* 資訊密度
* 圖文比例
* card hierarchy

若必須明顯偏離：
開 Gate。
二十五、GitHub Durable Memory Contract
客戶正式要求：
重要結論不得只留在 ChatGPT / Claude conversation。
正式寫入：
Conversation 不是 SSOT；GitHub 是 durable memory。
任何重要：

* 客戶裁示
* Presentation Contract
* Visual Fidelity
* Decision Digest
* One AI Brain architecture
* Missing semantics
* IA
* blueprint
* 未完成工作
* supersede 關係
* Next Action

都必須落 GitHub。
二十六、正式落盤位置
至少同步：
`PROJECT_RULES.md`
跨 Batch 長期治理規則。
`docs/DECISIONS.md`
客戶正式裁示、amendment、supersede。
正式 vNext design / architecture spec

* Presentation Contract
* Visual SSOT
* Visual Fidelity
* Decision Digest
* One AI Brain
* IA / blueprint

`docs/BACKLOG.md`
尚未完成工作、Gate、後續 Batch。
`docs/PROJECT_STATE.md`
當前 Stage 與狀態。
`docs/HANDOFF.md`
目前 main、Stop Point、唯一下一步。
注意：
HANDOFF 只是索引，不是規格 SSOT。
HANDOFF 應指向正式文件。
二十七、中斷 / Compact 防遺失
驗收條件之一：
如果現在立刻：

* compact
* 換新對話
* 額度中斷
* 換模型
* 換 AI session

新 session 只讀：

* GitHub current main
* PROJECT_RULES
* DECISIONS
* BACKLOG
* PROJECT_STATE
* HANDOFF
* 正式 SSOT

就能完整恢復。
如果做不到：
本 Stage 尚未完成。
二十八、舊記錄 / 規格整理
不要把所有歷史硬刪掉。
分成：
A. 正式歷史 Decision
保留。
但若已被新規格取代：
明確標：
`SUPERSEDED BY <new DEC>`
避免下一個 AI 誤認仍然 active。
B. 過期 active instructions
更新 / 清除：

* HANDOFF 過時 next action
* PROJECT_STATE 過時 current state
* BACKLOG duplicate / superseded items

C. 未合併草稿
例如 #970：
盤點後決定：

* close superseded
* 重做
* 吸收部分有效內容

D. 可刪文件 / assets
只有在：

* 無正式引用
* 無 audit 唯一價值
* 已被新 SSOT 完整吸收
* 不影響 tests/build

時才刪。
不要為了乾淨破壞 audit trail。
二十九、SSOT Precedence
請正式建立 precedence。
至少要讓新 session 不需要猜：
哪份規格有效。
建議概念：

1. PROJECT_RULES / permanent governance
2. 最新有效 DECISIONS
3. 最新正式 Presentation / Architecture / Data Contract / Visual SSOT
4. PROJECT_STATE
5. BACKLOG
6. HANDOFF
7. historical / superseded wireframes

若 repo 現有 constitution 有更高 precedence：
遵守既有 constitution，並在其下整合。
不得無聲覆寫更高階規則。
三十、本輪 Scope Guard
這一輪先做：

* SSOT Reset
* Presentation Contract
* Visual Fidelity
* Decision Digest Contract
* One AI Brain boundary
* supersede / cleanup
* helper / test migration plan
* visual gap audit

先不要：

* 新增資料來源
* 新增投資公式
* 定義尚未裁示的台股趨勢公式
* 定義尚未裁示的國際趨勢公式
* 改 Risk Cap 算法
* 新增 EPS×PE production rule
* 改投資語意
* 大量 production UI implementation
* 清理無關歷史技術債

發現這些問題：
登 BACKLOG。
除非是 P0 correctness / security blocker，不打斷主線。
三十一、執行階段
Phase 1 — SSOT Reset / Contract Freeze
完成：

* GitHub current-state audit
* #970 disposition analysis
* Presentation Contract
* Visual Budget
* Visual Fidelity Gate
* Decision Digest Contract
* One AI Brain boundary
* supersede map
* durable-memory contract
* formal docs 落盤

這一階段以 docs/spec/governance 為主。
Phase 2 — Helper / Test Contract Migration
修改：

* old presentation helpers
* Note contract
* V2_SHORT_ROWS 等
* tests

原則：
資訊仍存在，但不要求全部外露。
Phase 3 — Shared Visual Components
例如：

* metadata chips
* status chips
* chart header
* evidence expander
* Missing placeholder
* compact KPI card

Phase 4 — 📊 市場 reference implementation
先做一頁作 Visual Fidelity reference。
Phase 5 — 🎯 標的
Phase 6 — 💼 持股
Phase 7 — One AI Brain / Decision Digest / AI 投資總結正式實作
具體 dependency 可以調整。
但不得在 Decision Digest contract 未凍結前：
直接開始寫新的 LLM prompt / glue。
三十二、Model × Effort
目前這一輪：
Claude Opus 5.5
Effort：High
因為目前涉及：

* SSOT precedence
* Presentation Contract
* Decision Digest architecture
* One AI Brain boundaries
* old/new contract conflict
* test semantics
* durable-memory governance

若目前實際設定已是 Opus 5.5 + High：
不要要求我再確認。
直接執行。
當上述規格全部正式凍結，開始：

* common components
* chips
* expander
* layout
* chart arrangement
* routing
* mechanical migration

走 Model / Effort Change Gate：
推薦切換：
Claude Sonnet 5.5
Effort：Medium
只有實際需要切換時才停。
三十三、Hard Output Gate
維持既有規則。
中途不要回報：

* 已開始
* 正在掃描
* commit
* push
* PR opened
* CI running
* QA running
* agent running
* waiting
* merge ready
* retry

只有：

1. 真正客戶 Decision Gate
2. 真正 Model / Effort Change Gate
3. 需要客戶手動操作
4. 整個 Phase / Batch 完成
5. context 不安全

才可輸出。
三十四、本輪完成回報格式
Phase 1 完成後，只需精簡回報：

1. 最新 main / PR
2. 新 Presentation Contract 落點
3. Visual Fidelity Gate 落點
4. Decision Digest Contract 落點
5. One AI Brain boundary 落點
6. 哪些舊規格 / DEC 被 supersede
7. #970 最終如何處理
8. 哪些資料實際刪除、哪些保留歷史
9. BACKLOG 新增哪些未完成項
10. HANDOFF 是否能在新對話完整恢復
11. 下一個唯一安全接手點

最後再次確認本輪最高原則：
簡化 UI，不簡化判斷。
圖表 > 數字 > 短句 > 長文字。
Visual Priority does not mean Visual Quantity.
Simple Decision Dashboard, not Report Wall and not Chart Wall.
Presentation Simplification must never reduce AI Decision Context.
Data View ≠ Decision Context ≠ AI Output.
One AI Brain, Many Data Views.
Conversation 不是 SSOT；GitHub 才是 durable memory。
先完成 Phase 1 的 SSOT Reset / Contract Freeze，並依 Hard Output Gate 靜默執行。
```

- **要點**（撰寫組摘要，**非客戶原文**；以上方 fence 為準）：(1) 停止依 #970／DEC-108／較早 Presentation／Wireframe 規則施工，#970 不合併、只作歷史輸入、不得作 production baseline；(2) 呈現最高優先序「圖表 > 數字 > 短句 > 長文字」，但 Visual Priority ≠ Visual Quantity，每頁 1 Primary＋≤2～3 Secondary、第一屏 3～5 數字／chip、≤1 句主要判讀；(3) 第一屏五問、三層答不出＝Visual Fidelity FAIL；(4) 主圖 header＝標題＋3～5 chip＋1 句＋圖＋`▸ 為什麼／來源／限制／去哪補`；(5) 詳細文字下沉；(6)「現在／為什麼／去哪補」資訊不刪、取消常駐；(7) Missing 契約不變；(8) 共用 metadata／status chips；(9) IA 維持四頁；(10) 三頁方向＋👤 我的非分析頁；(11) Presentation Simplification must never reduce AI Decision Context；(12) Decision Digest 架構鏈與最低概念契約、不得創造新 confidence 語意；(13) One AI Brain, Many Data Views；(14) AI 投資總結只回答六題、新目標輸出、查看依據、禁止清單；(15) `build_ai_summary` 不得直接視為 One AI Brain；(16) Visual Fidelity Gate 11 項、CI 全綠 ≠ UI complete；(17) blueprint＝Visual SSOT；(18) GitHub Durable Memory、正式落盤位置、HANDOFF 只是索引、中斷防遺失驗收；(19) 舊記錄整理 A／B／C／D；(20) SSOT Precedence（遵守既有 constitution 並在其下整合）；(21) Scope Guard；(22) Phase 1～7；(23) Model × Effort；(24) Hard Output Gate；(25) Phase 1 完成回報格式。
- **取代關係（DEC-109 生效後；逐項判讀見 `docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2；舊條文一字不改，各條頭已加 📌）**：
  - DEC-108：部分取代（十項原則仍有效；線框 5 題撤回；凍結解除條件改為「Phase 1 契約合併後依 Phase 2→7 推進，每個 UI phase 過 Visual Fidelity Gate」）。PR #970 線框草稿（A.4／Q2「大圖只在 L2」、Q2-B「首屏不放圖」）：SUPERSEDED（R2）。
  - DEC-017 鐵律 4 三要素**呈現位置**：部分取代（內容保留）。葉1 ②「兩套刻度常駐非摺疊」：**維持有效**（本條原文未點名），列 Phase 6 線框待客戶拍板點。
  - DEC-111（補登，客戶 2026-09-24「三要素要在卡面上看得到」）：部分取代（位置）；DEC-112（補登，客戶 2026-09-25「v2 卡面三列短句」）：部分取代（列數）；K1 與「⛔ 不得只剩 hover」維持並延伸到手機。
  - **張力調和**：DEC-091 §一 客戶原文「禁止：大量三要素文字卡＋工程說明＋資料來源＋門檻＋診斷全部同層」與 DEC-111／DEC-112（只存在程式碼註解、要求三要素上卡面）**此前從未調和**；本條「資訊保留、可取得、可追溯、可展開、預設下沉」**同時滿足兩者**（內容不消失、不只剩 hover＝DEC-111／112 的保護目的；不同層外露＝DEC-091 §一 的禁令）。
  - AI 投資總結輸出格式：DEC-091(d)／§九「固定五段」客戶原文＋A 規格 `NEWUI_D25_A_FOUR_PAGE_SPEC_2026-10-27.md` §5＋`docs/vnext/d25_wireframes/ai_summary.html`（經 DEC-092 設計方向核准承接；DEC-092 本文無「五段」字樣）的**呈現格式**被本條第二十一段取代（R12）；存股／資本利得／未分類分類資料保留，AI 不得推論分類。AB-2a 程式寫死五段（`shared/decision_digest_terms.py`、`decision_digest_grounding.py` G5、`src/services/decision_digest_summary.py`）→ Phase 7 內部改動（BACKLOG `P1R-AB2A-FIVE-SECTION-REWIRE`）。
  - DEC-105 1A（結論句位置）：部分取代（相對順序可維持、須進第一屏；客戶同日前序原文「今日結論必須在第一屏可見」）；DEC-107 4A 候選表全表外露：部分取代（本條十二 Top-N First）。**DEC-107 1A 頁面順序、UIT 線框「選股條件預設展開」、DEC-105 第 4 點指路形式：維持有效**（本條原文未點名），列 Phase 4／5 線框待客戶拍板點（DEC-110 R3）。
  - 與本條無關、但本 phase 一併補標的既有取代（出處各自為先前 DEC）：DEC-018／071／072／076／081／083 Q1 措辭／021 → DEC-083／091／092／097；DEC-091 §四 → DEC-105 2A；DEC-073 → DEC-084；DEC-099 已執行完畢。
- **效力邊界**：本條不核准任何新資料源、schema、公式、門檻、TTL、投資語意、Risk Cap 算法或顯示、正式趨勢定義、EPS×PE production rule、AI 接線；**不改 IA**（四頁）、不改 `PAGE_LABELS`／導覽殼／legacy 入口（DEC-097）；不修改舊 UI（DEC-019）；**不改 `CLAUDE.md`／`PROCESS.md`**（客戶原文「若 repo 現有 constitution 有更高 precedence：遵守既有 constitution，並在其下整合。不得無聲覆寫更高階規則」）。已合併 UI-M（#965）、UI-T（#968）由 Phase 4／5 依 Gate 回修，不自動回退。
- **與其他 DEC 的關係**：具體化 DEC-091 §一（三層）、DEC-092（blueprint 核准）、DEC-108（十項原則）；強化 DEC-067／068／079／086（durable memory）；呼叫 DEC-082（版面設計變更仍須草稿先行）、DEC-103（Scope Inflation Guard）、DEC-104（Hard Output Gate）、DEC-084／106（Model×Effort）、DEC-085／`PROJECT_RULES.md` §19.9（呈現與決策邏輯分離）；DEC-081 Q2-1／Q2-2、DEC-092 Q2／Q5、DEC-101(1)(2)(3)、DEC-102、DEC-105 2A／3A／第 4 點、DEC-051、DEC-054／055 的**內容**全部保留，只遷移位置。內部讀法 R1～R19 見 DEC-110。
- **附錄：同日前序客戶指示（客戶 2026-10-29T15:18:41Z「Presentation Contract Migration + Visual Fidelity Gate」，逐字）**：此則在本條之前頒布，前一輪撰寫被中止、**從未落盤**；依 Context Loss Check A 一併逐字收錄。讀法（AI 總管內部，DEC-110；客戶可推翻）：其 PCM-1／PCM-2／PCM-3 階段命名由本條 Phase 1～7 取代；其 10 項 Gate 由本條 11 項取代（同向擴充）；其餘（新契約 8 條、Visual Density、Top-N First、三頁方向、圖表標頭、Blueprint 地位、保存規則）與本條同向、**仍有效**。

```
請暫停把目前新 UI 繼續往後擴張。這一輪不是 CSS 美化，而是正式進行：
Presentation Contract Migration + Visual Fidelity Gate
目標：修正目前新 UI 與已核准視覺方向明顯偏離的根因。
目前 production / 實際列印 PDF 已確認出現以下問題：

* 圖表太大、空白太多。
* 結論被推到很下方。
* 文字卡過多，主畫面像研究報告／工程診斷頁，不像決策儀表板。
* 「現在／為什麼／去哪補」等資訊被全部常駐外露。
* 產業、候選、持股等區塊大量使用長表／長文字，板塊感不足。
* 已核准 mockup / blueprint 的「圖表優先、卡片化、第一屏決策」精神沒有被 production UI 忠實實作。
* 功能、CI、QA 雖然正確，但 Visual Fidelity 明顯不合格。

先依 GitHub Verification Gate 重新核對：

* current main SHA
* Open / Draft PR
* 最近相關 UI PR 與 diff
* CI / QA
* 現行 UI / wireframe / blueprint / DEC / tests / helper
* 特別找出仍要求「現在／為什麼／去哪補」必須外露的舊 presentation contract

GitHub 為 SSOT，HANDOFF / STATE 只作輔助。
一、正式遷移新的 Presentation Contract
新的最高呈現優先序：
圖表 > 數字 > 短句 > 長文字
這是新 Visual SSOT。
新契約

1. 圖表原則上外露
   * 主決策圖表不要藏在 expander。
   * 詳細解釋文字才收合。
2. 每張主圖上方最多：
   * 標題
   * 3～5 個狀態 / 規格 chip
   * 1 句白話用途說明
3. 第一屏優先呈現：
   * 現在狀態
   * 關鍵數字
   * 主要圖表
   * 是否需要行動
   * 下一步
4. 主卡只保留：
   * 狀態
   * 關鍵數字
   * 1 句摘要
5. 以下資訊必須保留，但預設下沉：
   * 為什麼
   * 資料來源
   * 公式 / 口徑
   * 限制
   * Missing 原因
   * 去哪補
   * 工程層級 / helper / Lx 等資訊
6. Missing 原則：
   * missing ≠ 0
   * missing ≠ neutral
   * missing ≠ HOLD
   * missing ≠ safe
   * 不得腦補
   * 但主畫面用簡潔 Missing placeholder / chip 呈現，不用拿大段文字填滿版面。
7. 共用 metadata / status chips 優先：
   * 資料日
   * source
   * stale
   * coverage
   * unavailable
   * estimated / proxy
不要每個區塊重複寫長句。
8. 不能刪除「現在／為什麼／去哪補」所承載的資訊。
只是把：
「必須全部外露」
改成：
「必須可取得、可追溯、可展開」。

二、舊 Presentation Contract 必須正式遷移
請盤點所有仍把舊呈現方式寫死的地方，例如但不限於：

* `現在 / 為什麼 / 去哪補`
* Note → 三列短句
* V2_SHORT_ROWS
* card helper
* tests 要求三段文字一定顯示
* wireframe / blueprint / DEC 中過時的 presentation requirement

請分類：
A. 必須淘汰
B. 必須改成「資訊存在但可收合」
C. 仍然有效
D. 與新 Visual SSOT 衝突
新的 precedence 必須明確寫入正式規格：
若舊 helper / test / wireframe 的 presentation requirement 與新的 Presentation Contract 衝突，以新的 Visual SSOT 為準。
但注意：

* 只遷移「呈現責任」
* 不准改資料語意
* 不准改公式
* 不准改 Risk Cap
* 不准改 investment semantics
* 不准新增資料來源

三、Visual Density 規則
避免再出現目前 PDF 的大空白 / 大文字 / 大圖問題。
外露區禁止

* 整張 prose card
* 大段工程解釋
* 重複「現在／為什麼／去哪補」
* 大表直接佔據第一屏
* 同一頁同時堆太多大型圖表

優先使用

* sparkline
* mini trend
* small multiple
* heatmap
* Top-N bar
* ranking cards
* compact KPI cards
* status chip
* icon
* badge
* compact comparison chart

Top-N First
產業、風險、候選、排名：

* 預設只顯示 Top 5～10
* 完整清單放展開區
* 不再一開始把 30～40 個產業全部攤開

四、目前三頁修正方向
📊 市場
第一屏優先：

* 市場位階
* Risk Cap / 尚未核准狀態
* 今日主要風險
* 是否需行動
* 小型台股趨勢圖

修正：

* 大圖縮小。
* 國際市場多系列改 small multiples / compact charts。
* 更新模式與工程說明下沉。
* 今日結論必須在第一屏可見。
* 主要風險用 chip / compact card，不用大片文字。
* EPS×PE 未核准時保持 placeholder，不填假圖。

🎯 標的
目前最需要回修。
修正：

* 第一區「產業機會」不能再先列全部產業長卡。
* 改成：
   * Top 產業卡
   * ranking
   * heatmap / bubble / compact sector view
* 產業完整明細收合。
* 候選標的應更早出現。
* 候選表預設只顯示必要欄位＋Top-N。
* 單一股票先摘要卡＋主要圖，再展開完整分析。
* 未接線功能只在進階 / 查看依據說明。

💼 持股
第一屏優先：

* 該做什麼
* 需處理幾檔
* 加碼 / 減碼 / 換股摘要
* 主要持股風險
* 組合狀態
* 必要圖表

修正：

* 「現在／為什麼／去哪補」不再每張卡全部外露。
* VIX / 燈牆 / 配置 / VaR / 現金流改 compact chart/card。
* 來源、門檻、分母、算法限制全部下沉。
* AI 總結是摘要出口，不要再加文字牆。

五、圖表標頭規格
每個主圖使用一致 header：
【標題】
chips：
`資料日 10/29`
`來源 TWSE`
`近 60 日`
`✅ 可讀`
`⚠ stale`
一句話：
「近 60 日資金持續流入，但最近 5 日動能放緩。」
接著直接顯示圖。
下方只留：
`▸ 為什麼／來源／限制／去哪補`
禁止在圖上方先放一整段說明文章。
六、Visual Fidelity Gate
從這一輪起，UI Stage 不能只靠：

* CI
* tests
* QA
* mutation

來判定完成。
新增正式驗收條件：
Visual Fidelity Gate
每個 UI PR 必須提供實際 screenshot，至少：

* desktop
* mobile 390px

並與已核准 blueprint / mockup 對照：

1. 第一屏結構
2. 圖表 / 文字比例
3. 卡片密度
4. 圖表尺寸
5. 空白比例
6. Top-N 是否正確
7. 長文字是否下沉
8. Missing 是否以 placeholder 表示
9. 主要 CTA / 結論是否首屏可見
10. mobile 是否不被大表 / 大圖 / 長文佔滿

若 screenshot 與 blueprint 明顯偏離：
即使 CI / QA / tests 全綠，也不得標記 UI Stage complete。
七、Blueprint 地位
目前已核准的視覺 mockup / wireframe 不再只是「參考」。
請正式定義：

* blueprint = Visual SSOT
* production UI 必須以 blueprint 為 visual acceptance baseline
* 可以因真資料 / Streamlit 限制做合理調整
* 但若資訊層級、圖文比例、首屏結構、板塊密度明顯偏離，必須開 Gate，不得自行發散

八、執行順序
這次不要一次爆改全部 UI。
Stage PCM-1：Audit + Contract Migration
先完成：

* 找出舊 presentation contract
* 建立新 Visual SSOT
* precedence
* helper / test contract migration plan
* Visual Fidelity Gate
* 三頁 visual gap audit

這一階段以 docs / spec / tests contract 為主。
完成後若沒有真正 product decision 需要客戶裁示，可依既有授權繼續。
Stage PCM-2：共用 helper / tests 遷移

* 修改 presentation helper
* 修改相關 tests
* 確保資訊仍可追溯
* 不改資料語意

Stage PCM-3：三頁 UI 回修
順序：

1. 📊 市場
2. 🎯 標的
3. 💼 持股

每頁獨立 PR / 可回滾 checkpoint。
九、Scope Guard
本次不得順手做：

* 新資料來源
* 新投資規則
* Risk Cap 新公式
* EPS×PE production rule
* 台股趨勢正式定義
* 國際趨勢正式定義
* 大規模 IA 重構
* legacy cleanup
* 歷史技術債整理

發現這些 → BACKLOG，不打斷主線。
十、保存規則
本次所有正式結論必須落盤：

* Decision → `docs/DECISIONS.md`
* Backlog → `docs/BACKLOG.md`
* Stage / status → `docs/PROJECT_STATE.md`
* Resume checkpoint → `docs/HANDOFF.md`
* Visual SSOT / Presentation Contract → 正式 vNext spec
* Visual Fidelity Gate → 正式 UI governance / acceptance spec

沒有落盤 ≠ 完成。
十一、Model × Effort
目前這一階段推薦：
Opus + High
原因：

* SSOT precedence
* 舊 contract migration
* tests semantics
* helper semantics
* blueprint precedence
* Visual Fidelity acceptance

完成 PCM-1 / PCM-2 並進入明確機械式 UI implementation 後：
切換 Sonnet 5.5 + Medium
依 DEC-084 / DEC-106：

* 若目前實際模型 / Effort 已符合推薦值，不要停下來要求我重複確認。
* 只有真的需要切換時，才在安全 checkpoint 告訴我精確模型＋Effort，等我回「改好了」。

十二、回報規則
維持 Hard Output Gate。
中途不要回報：

* 已開始
* 正在掃描
* commit
* push
* PR opened
* CI running
* QA running
* 等待
* merge ready

只有：

* 真正需要客戶裁示
* 真正需要 Model×Effort 切換
* 需要客戶手動操作
* 整個 Stage 完成
* context 不安全

才可以出聲。
Stage 完成回報保持極簡：

1. main SHA
2. PR
3. Presentation Contract 改了什麼
4. Visual Fidelity Gate 是否建立
5. 下一個單一 Stage
```

- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：fence 為逐字；「要點」「取代關係」「張力調和」「附錄讀法」為撰寫組讀法，**單組、未經第二組驗證**。客戶原文中的 SHA、PR 狀態為客戶當時實查值，以 GitHub 最新實況為準。

### DEC-110｜Phase 1 SSOT Reset 的 AI 總管內部決定 R1～R19（AI 總管內部，2026-10-29）

> 📌 **R4（`CV1-DR-12`／W9 裁示前維持現狀、Gate 對 KPI 欄數暫不判定）由 DEC-117 Q1 裁示結案；R5 指路形式由 DEC-117 Q2 裁示結案；R2「1 Primary Visual 在第一屏」在 📊 市場頁手機版由 DEC-117 Q7 部分取代（客戶核准 mobile exception，附條件）；R7 卡片摺疊標籤統一與否在 📊 市場頁由 DEC-117 Q3 裁示結案**（2026-10-30 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-117）；append-only，本條原文一字未改）：R4：📊 市場頁桌機 3 個核心狀態 tile、手機 2＋1；客戶明示「固定 3 欄」是桌機核心狀態網格要求、手機依可讀性自適應（客戶解釋記於 DEC-117，`CLAUDE.md` 不改）；R4「不在 DECISIONS 重新解釋 `CLAUDE.md`」作為總管行為約束仍有效。R2：桌機照舊；手機 Primary 可位於第一屏下方，但須緊接 L1 決策區、不得被 L2／L3 插隊。R7：圖用「▸ 為什麼／來源／限制／去哪補」、tile／⚡ 維持「🔍 查看依據」；Phase 5～6 仍待各頁線框。R5：「DEC-105 指標危險度指路句**維持**（改 chip 與否＝W2，待 Phase 4 線框拍板）」由 DEC-117 Q2 裁示結案——維持說明句、縮短、必須保留「指標危險度」「指標明細（16 項）」與指向最上方的關係、不新增 chip；R5 其餘項不變。契約 Q11（結論句 ≤+200／+260）**不受影響**（DEC-117 Q5 同向）。
> 📌 **R8「狀態一律沿用 `UI_STATE_META` 既有符號／十態不另造」在 L1 外露字樣部分受 DEC-122 影響（待客戶拍板）**（2026-11-02 登記；決策者 客戶（DEC-122 指示，客戶 §5「全站統一」）；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S8、§3）：L1 Missing 外露字樣改為 `⬜ 資料未取得`／`⬜ 資料未備`，⟳／⊘／▨ 留作 L0 與 L2 子原因；**十態本身、符號、「不另造第 11 態」全部仍有效**——客戶四態（Missing／Stale／Unavailable／Not evaluated）是語意分類層，不是新狀態（對映表見 Final UI 契約 §5.2）。

> 2026-10-29 補登（ID 取下一個未用號；落盤前 0 命中、DEC-109 為前一號）。**本條不是客戶裁示**（DEC-109 才是），依 `CLAUDE.md` §-1.5.D v3 §03-1 內部自決落文；**客戶可推翻任何一條**，推翻後以客戶為準並同步受影響文件。

- **決策者**：AI 總管內部（依 `CLAUDE.md` §-1.5.D v3 §03-1；**非客戶裁示**）。｜**日期**：2026-10-29。｜**狀態**：生效（隨 Phase 1 PR）。
- **內容**：
  - **R1**：舊記錄清理分 A 正式歷史 Decision／B 過期 active instructions／C 未合併草稿／D 可刪文件（客戶 DEC-109 二十八定義）；舊 presentation contract 盤點另用 P-A～P-D（避免撞名；Migration Plan §2）。
  - **R2**：主圖外露但 compact，**1 Primary Visual 在第一屏**；PR #970「大圖只在 L2」、Q2-B「首屏不放圖」被取代；#970 §客戶待確認 5 題撤回。
  - **R3**（2026-10-29 總管改判；本行為本 PR 內撰寫之文字，直接改寫）：DEC-107「選股條件預設展開」**維持有效**；在 DEC-109 Visual Budget 下是否改為預設收合＋摘要 chip，列為 **Phase 5（🎯 標的）線框草稿的一個待客戶拍板點**（依草稿先行，本 phase 不另開 Gate、不改；BACKLOG `P1R-P5-WF-SCREEN-COND`）。改判理由：這是客戶核准線框的裁示，且 DEC-108 記載「改此點須客戶明確回覆」；**AI 總管讀法不得推翻客戶裁示**。同一原則複查其他 R 條（見下方「同原則複查」）。
  - **R4**（2026-10-29 第二輪 QA 總管裁定改寫；本行為本 PR 內撰寫之文字，直接改寫）：**不在 DECISIONS 重新解釋 `CLAUDE.md`**。`CLAUDE.md` v3 §00「固定 3 欄自適應網格」與 DEC-091 §四「3～4」／現行 Hero 4 欄（DEC-105 第 5 點 P2 偏離）的牴觸登 BACKLOG `CV1-DR-12` 待客戶裁示，並列 Phase 4 線框待拍板點 **W9**；**裁示前維持現狀**，Visual Fidelity Gate 對 KPI 欄數暫不判定；**不改 `CLAUDE.md`**。
  - **R5**：客戶裁示內容保留、只換位置：DEC-081 Q2-1 結論句在第一層；Q2-2 Risk Cap 措辭逐字；DEC-092 均線句逐字；DEC-101／102 價格時間 chip 在原 E17 位置（PR #970 B.3 ② 移位須更正）；DEC-105 指標危險度指路句**維持**（改 chip 與否＝W2，待 Phase 4 線框拍板；2026-10-29 第二輪 QA 改寫）；Risk Cap 完整度 chip 緊鄰數字；外資（外幣）排除逐字 chip；停利未判 chip；AI 揭露 chip；稅前 chip。
  - **R6**：客戶 2026-09-24「三要素要在卡面上看得到」（DEC-111）、2026-09-25「v2 卡面三列短句」（DEC-112）：**位置**被 DEC-109 取代；內容契約與 K1 摘錄保留；「⛔ 不得只剩 hover」保留並延伸到手機（必須可點開）。DEC-017 鐵律 4：內容保留、位置改可展開（DEC-109 七明確點名）。DEC-017 葉1 ②「兩套刻度常駐非摺疊」：**維持有效**，是否改 chip＋可展開＝Phase 6 線框待客戶拍板點（總管 2026-10-29 改判）。
  - **R7**（2026-10-29 總管改判後範圍）：**主圖 header 下方**的摺疊標籤用「▸ 為什麼／來源／限制／去哪補」（DEC-109 五客戶原文明確給定）；**卡片摺疊標籤「▸ 詳細」**（客戶 2026-09-25 核可線框逐字，`src/ui_v2/markup.FOLD_SUMMARY_TEXT`）**維持有效**，是否統一為新字樣列為各頁 phase 線框待客戶拍板點（`P1R-WF-FOLD-LABEL`）；具名 expander 不改名。
  - **R8**（2026-10-29 第二輪 QA 改寫）：metadata chips 是獨立家族（不進 BADGES 11 封閉集）；**狀態一律沿用 `shared/ui_state.UI_STATE_META` 既有符號**（`⛔ 未接線`、`▨ 無資料`、客戶 2026-09-23 D-3(a) 三態 `⟳ 缺漏 · 可重跑`／`⊘ 不適用 · 重跑無效` 等），**既有徽章族優先，⛔ 同一狀態出現兩種符號**；🔴 只給系統真錯誤；stale 用 ⚠；每個色塊都要有文字。
  - **R9**：Top-N 只是顯示切片（`TOP_N_OPTIONS`／`DEFAULT_TOP_N` 不變）；Digest 與 AI 不受 Top-N 影響。
  - **R10**：expander 不省運算；既有 gate 保留。
  - **R11**：#970 處置＝關閉 #970（superseded）＋同分支開新 PR；有效部分（DEC-108 裁示、§C 偏差量測、§D 能力守恆表、§E 順序、A.5 工程字樣清單）吸收進新契約／遷移計畫；舊線框檔 `docs/vnext/NEWUI_D25_UI_CORRECTION_WIREFRAME_2026-10-29.md` 與 `docs/vnext/ui_correction_assets/`（15 png）**自本分支移除**（從未進 main）；DEC-108 保留、標部分取代；#970 不成為 production baseline。**執行（2026-10-29 第二輪 QA 總管裁定）**：總管於 push 後關閉 #970（留言指向 commit `06a7a3e5`），自同分支開新 PR，以 **squash merge** 合併 → `06a7a3e5` 不進 main 歷史，**#970 原貌只保存在 commit `06a7a3e5`**；#970 §C 冷啟動量測不吸收，Phase 3 Gate 前重量（BACKLOG `P1R-COLD-START-BASELINE`）。
  - **R12**：AI 投資總結輸出格式＝客戶 DEC-109 二十一（市場一句／持股一句／標的機會一句／主要風險 1～3／本期行動 ≤3，每項附查看依據）即新客戶裁示，取代 DEC-091(d)／A 規格 §5／`ai_summary.html` 五段的**呈現格式**；分類資料保留於 Digest 與查看依據，AI 不得推論分類；Phase 7 實作前依草稿先行出線框；**不另開 Gate**（依據：`PROJECT_RULES.md` §0.1「變更需新的客戶 Decision」——DEC-109 即是；DEC-013 已裁示事項不重問）。
  - **R13**：AI 投資總結入口＝各頁 L1 固定元素（E2 卡＋展開面板），計入 Visual Budget；不是第五頁，IA 不變。
  - **R14**：👤 我的 Google login 只做衝突分析（契約 §13.4）；正式位置維持 👤 我的卡①；舊側欄登入區塊隱藏與否屬版面異動且碰 DEC-083 E 段 → 登 BACKLOG 為未來客戶 Gate（本 phase 不問、不改）。
  - **R15**：Visual SSOT：blueprint（`docs/vnext/d25_wireframes` 核准 mockup）＝視覺驗收基準；`src/ui_v2/tokens.py`＝實作 token 來源；色值不一致 → blueprint 為準，tokens 於 Phase 3 收斂（BACKLOG）；差異表寫入契約 §14.2。**2026-10-29 總管改判範圍**：tokens 內**客戶裁示的色值**（CTA 主色 `#1f6feb`／light `#044cb6`，客戶 2026-09-22；`--sig-neutral`／`-bg`，客戶 2026-09-21）**維持有效**、不在 R15「blueprint 為準」的射程內；是否改為 blueprint 色值列為 Phase 3 草稿待客戶拍板點（`P1R-P3-WF-CUSTOMER-COLORS`）。 📌 **2026-10-30：客戶已裁示（DEC-115 D1a=A 維持客戶裁示色值；D1b=B 非客戶色延到 Phase 4～6 逐頁收斂＝本條「tokens 於 Phase 3 收斂」時程被客戶調整；R15 其餘不變）。**（有意識的更新，不是漏刪；決策者 客戶（DEC-115）；本條原文未改）
  - **R16**：SSOT 位階兩軸——規範軸：`CLAUDE.md`（§-2 > §-1.5 > §-1 > §0～8）> `PROCESS.md` > `PROJECT_RULES.md`＋`docs/governance` > 最新有效 DEC（客戶 DEC > 總管內部 DEC）> 正式契約／Visual SSOT > `PROJECT_STATE` > `BACKLOG` > `HANDOFF`（索引）> historical／superseded；事實軸：GitHub 實況 > code／tests > 正式文件 > HANDOFF > PROJECT_STATE > AI 記憶 > 聊天。客戶建議序（PROJECT_RULES 第一）置於既有憲法之下；兩軸不牴觸。`PROCESS.md` §1「只讀 STATE.md」與五檔讀序衝突 → 本 phase 不改 `PROCESS.md`，維持 `CV1-DR-04` 待裁示。落點 `PROJECT_RULES.md` 第 25 節。
  - **R17**：根目錄舊文件（`HANDOFF_2026-08-15.md`、`PLAN_T1_T2.md`、`PLAN_T4.md`、`BATCH_A_DELIVERY.md`）＝D 類候選，本 phase 不刪不改，只登 BACKLOG P2；repo 內 `scratchpad/*.md` 保留。
  - **R18**：`tools/visual_fidelity/`（量測 harness，非 production、不被 app import）納入 repo，確保 Visual Fidelity Gate 可重跑；不被任何 test 收集、fast checks 綠（Phase 1 PR 實跑）。
  - **R19**（2026-10-29 第二輪 QA 總管裁定改寫）：Phase 2（helper／test 契約遷移）用 **Opus 5.5＋High**；進入**明確機械式 UI implementation**（Phase 3 起視情況，例如線框已拍板後的元件／排版搬移）才切 **Sonnet 5.5＋Medium**（客戶 DEC-109 三十二）；Phase 7（Digest／Brain）**Opus 5.5＋High**。寫入 HANDOFF 下一接手點；開工時依 DEC-084／DEC-106 比對現況，符合即靜默繼續。 📌 **2026-10-29：Phase 2 的 Model×Effort 被客戶後續指示降級，見 DEC-113（以 DEC-113 為準；本條 R19 原文未改）。**
  - **同原則複查（2026-10-29 總管裁定「凡總管讀法改變客戶核准過的呈現、且 DEC-109 客戶原文沒有明確點名者，一律維持＋列入該頁 phase 線框待拍板點」後，撰寫組逐條複查）**：改為「維持＋待拍板」者＝R3（選股條件預設展開，Phase 5）、DEC-107 1A 頁面順序下候選如何提前（Phase 5）、`ZONE1_SORT_NOTE` 排序依據句由說明句改 chip（Phase 5）、DEC-017 葉1 ②兩套刻度常駐非摺疊（Phase 6，原 R6 一部分）、DEC-105 第 4 點指路由說明句改 chip（Phase 4）、卡片摺疊標籤「▸ 詳細」換字（各頁，原 R7 一部分）、tokens 客戶裁示色值（Phase 3，原 R15 一部分）。**維持原判（客戶原文有明確點名）**者＝R2（DEC-109 三／十一 Primary Visual、同日前序「主決策圖表不要藏在 expander」）、R5 價格時間＋來源改同位置 chip（DEC-109 九 as_of／source 用 chip 取代重複長句）、R5 外幣排除逐字 chip 與 Missing chip（DEC-109 八）、Risk Cap 完整性 coverage chip（DEC-109 九 coverage；仍在卡面緊鄰數字）、DEC-105 1A 結論句進第一屏（同日前序「今日結論必須在第一屏可見」）、DEC-107 4A 候選 Top-N（DEC-109 十二）、三要素位置（DEC-109 七）、更新模式 radio 下沉（同日前序「更新模式與工程說明下沉」）、R12 AI 投資總結格式（DEC-109 二十一）；R8／R9／R10／R13／R14 不改變客戶核准的呈現，維持。**第二輪 QA（2026-10-29）再收斂**：R5「DEC-105 指路為 chip」改為維持指路句＋W2 待拍板；R4 不再作讀法，改登 `CV1-DR-12`＋W9；DEC-021 取代範圍縮到 DEC-083 Q1 明確點名的「換一本／建新 Sheet」；舊 Stage D 各列改為「排程 superseded、能力項目維持 open」（`P1R-STAGE-D-CARRYOVER`）；「最大 1～3 個變化」選取規則改列 W8（Phase 7），不作內部預設。判準：客戶 DEC 的呈現裁示只有在 DEC-109 或同日前序指示（15:18Z）**明確點名**處才被取代。⚠️ 複查為撰寫組單組，未經第二組驗證。
- **與其他 DEC 的關係**：DEC-109（客戶裁示）的內部落文；DEC-003（內部自決區）、DEC-082（版面變更草稿先行）呼叫；不降低任何 Security／Investment／Data／CI／Audit Gate。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：R1～R19 由 AI 總管依五組單組調查（Inv-1～Inv-5）＋獨立稽核組勘誤定案；撰寫組照錄，**未經第二組驗證**。

### DEC-111｜（補登）客戶 2026-09-24 裁示批 1：「三要素要在卡面上看得到，⛔ 不是只剩一條指路＋hover」＋今天頁「三張同版」「一次整頁卡化」（客戶 2026-09-24）

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S27：對 New UI2 之三要素「▸ 詳細」機制（Legacy 凍結維持））** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。

> 2026-10-29 **補登**（ID 取下一個未用號；**補登，來源＝程式碼註解 `src/ui/views/page_today.py`**；本裁示此前只存在程式碼註解與測試 docstring，`docs/**` grep 0 命中）。**非客戶逐字全文**：下列引文為程式碼註解內所記之客戶裁示字句（撰寫組照錄註解原字，未見客戶原訊息）。

- **決策者**：客戶（2026-09-24；經程式碼註解轉述）。｜**日期**：2026-09-24。｜**範圍**：UI／呈現（新版 v2 卡面：今天頁三要素卡）。｜**取代鏈**：DEC-111 →（位置）DEC-109 七；內容仍有效。｜**狀態**：**部分取代 BY DEC-109**（2026-10-29 有意識的政策變更，不是漏刪，決策者 客戶（DEC-109））——三要素的**位置**（卡面常駐）被取代；三要素**內容**（`Note` 三段非空、不得消失）維持。
- **來源**（類別 **E**：程式碼註解轉述；約 L 僅參考）：`page_today.py` 約 L2933「🔴 **2026-09-24 客戶裁示：三要素要在卡面上看得到，⛔ 不是只剩一條指路 ＋ hover。**」；約 L2683／L2689「2026-09-24 客戶裁示批 1……客戶 2026-09-24 看過對照之後裁示「三張同版」」；約 L2764／L2775「客戶 2026-09-24 裁示：放棄分批，一次整頁卡化」。
- **兩邊理由並陳**：舊做法（三要素上卡面）最不會讓「為什麼沒有／去哪補」被忽略，且明確反對「只剩 hover」——**理由仍成立**；新做法（DEC-109）勝出的原因：三要素常駐使畫面成為文字牆（客戶 DEC-108／DEC-109 自承偏差），且與 DEC-091 §一 客戶原文「禁止：大量三要素文字卡＋…全部同層」張力未調和；DEC-109 以「保留、可取得、可展開、預設下沉」同時滿足兩者。
- **仍有效部分**：「⛔ 只剩 hover」的禁令（延伸到手機：必須可點開）；「三張同版」作為今天頁（legacy 可達）既有設計。

### DEC-112｜（補登）客戶 2026-09-25 裁示 1～4：v2 卡面三列短句（裁示 2）＋K1 原文摘錄＋「⛔ 完整原文不得只剩 hover」＋16 燈卡三列出處收進「▸ 詳細」（客戶 2026-09-25）

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S27：對 New UI2 之「▸ 詳細」機制（Legacy 凍結維持））** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。

> 2026-10-29 **補登**（ID 取下一個未用號；**補登，來源＝程式碼註解 `src/ui/views/page_find.py`、`page_today.py`**（另見 `page_hold.py`、`page_inspect.py`、`page_why.py`、`src/ui_v2/markup.py` 同構註解）；`docs/**` grep 0 命中）。**非客戶逐字全文**：引文為程式碼註解所記字句。

- **決策者**：客戶（2026-09-25；經程式碼註解轉述）。｜**日期**：2026-09-25。｜**範圍**：UI／呈現（新版 v2 卡面：三列短句、K1、hover 禁令、16 燈卡摺疊）。｜**取代鏈**：DEC-112 →（列數／位置；含下方「非 live 卡三要素照留卡面」）DEC-109 七；K1、hover 禁令、「▸ 詳細」機制與字樣仍有效。｜**狀態**：**部分取代 BY DEC-109**（2026-10-29 有意識的政策變更，不是漏刪，決策者 客戶（DEC-109））——「三列短句上卡面」的**列數／位置**被取代；**K1**（卡面字句須為 Note 原文摘錄、不新造）與「**⛔ 完整原文不得只剩 hover**」**維持**並延伸到手機；「▸ 詳細」純 CSS 摺疊**機制與標籤字樣**維持（換字與否＝各頁線框待客戶拍板點，DEC-110 R7）。
- **來源**（類別 **E**：程式碼註解轉述；約 L 僅參考）：`page_find.py` 約 L769「v2 卡面的短語表（客戶 2026-09-25 裁示 2）」、約 L770「每一則 `Note` → 卡面上的**三列短句**（現在 / 為什麼 / 去哪補）」、約 L774「客戶 2026-09-25 最終裁示：⛔ 不得只剩 hover，手機要看得到」、約 L2098、約 L2134「2026-09-25 客戶最終裁示：**⛔ 不得有只活在 hover 的字**」；`page_hold.py` 約 L4782「客戶 2026-09-25 裁示 2 ＋ K1」；`page_today.py` 約 L3014「🔴 **2026-09-25 客戶核可線框：16 盞燈卡（`detail.*`）的三列出處說明收進「▸ 詳細」。**」、約 L3017「非 live 卡的三要素（現在／為什麼／去哪補）與 degraded 的「現值」**照留卡面、⛔ 不摺**。」（同一 2026-09-25 核可線框的範圍界定；其中「三要素照留卡面」的**位置**由 DEC-109 七取代、內容保留；degraded「現值」是觀測值、DEC-109 未明確點名 → **維持卡面**）、約 L3019「2026-09-25 客戶選 (b)」；`src/ui_v2/markup.py` 約 L586「客戶 2026-09-25 核可線框逐字「▸ 詳細」」。
- **兩邊理由並陳**：舊做法（三列短句上卡面＋全文摺疊）在保留全文的同時讓卡面有可讀摘要——**理由仍成立**；新做法勝出原因：三列×每卡超出 Visual Budget（第一屏 3～5 數字／chip、≤1 句主要判讀），且客戶 DEC-109 七明令取消「三者必須全部常駐主畫面」。

### DEC-113｜Phase 2 Model×Effort 降級：helper／測試遷移類工作用 Sonnet 5.5＋Medium（客戶 2026-10-29）

> 2026-10-29 補登（取下一個未用號；落盤前 `grep -rn "DEC-113" docs PROJECT_RULES.md` 0 命中）。**來源類別：客戶，經總管轉交要點，非逐字**。

- **決策者**：客戶（2026-10-29，Phase 1 完成後）。
- **內容**：Phase 1 完成後，Phase 2 若仍是 helper／測試遷移、守衛盤點、遷移計畫與文件同步，依 Minimum Sufficient Effort 降為 **Sonnet 5.5＋Medium**；**只有**碰投資語意、Risk Cap、資料契約、重大架構衝突或其他 High Gate 才升回 **Opus 5.5**（High）。客戶已切換（「改好了，繼續 Phase 2」）。
- **兩邊理由並陳**：舊做法（DEC-110 R19：Phase 2 用 Opus 5.5＋High）對「畫面零變更、不碰投資語意」的機械遷移較保守，**理由仍成立**於一旦牽涉守衛鏈或契約判斷；新做法勝出：DEC-073／084 Minimum Sufficient Effort，高於所需不必浪費。
- **與其他 DEC 的關係**：修訂 DEC-110 R19（只改 Phase 2 的 Model×Effort；R19 其餘—Phase 3 起視情況、Phase 7 用 Opus 5.5＋High—不變）；承 DEC-073／084／106；DEC-109 三十二（客戶原文）不改。

### DEC-114｜Phase 2 前的 Safe Handoff／Session Close 指示（客戶 2026-10-29）

> 2026-10-29 補登。**來源類別：客戶，經總管轉交要點，非逐字**。

- **決策者**：客戶（2026-10-29）。
- **要點**：停止 Phase 2 實作；做正式 Safe Handoff／Session Close，使全新對話只靠 GitHub 冷啟動；Scope Guard（不開始 Phase 2、不新增資料源／公式／語意；本批只改 docs／governance）；Hard Output Gate（DEC-104，過程不輸出）；完成條件＝docs 提交並一般 push、HANDOFF 索引為實況、預備實測存入 repo。
- **落點**：`docs/HANDOFF.md` 置頂索引；`docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md` §11；`docs/PROJECT_STATE.md` §48；`docs/BACKLOG.md` `P1R-PHASE1-CONTRACT-FREEZE`／`P1R-PHASE2-HELPER-TEST-MIGRATION`。

### DEC-115｜Phase 3 步驟 0 客戶裁示：D1a=A／D1b=B／D3=A／D5=A／D6=B／D8=B／D10=(a)＋七項補充邊界＋站殼間距處置＋施工授權（客戶 2026-10-30）
> 📌 **D3=A 末句「不得新增會與既有 Missing／限制語意混淆的第四套視覺語言」部分取代 BY DEC-122**（2026-11-02 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-122）；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S5）：客戶 2026-11-02 §4 正式新增 Semantic Chip 四種語意 tone（Positive／Allowed、Warning、Danger、Neutral／Info）；Danger 專用於確定性違規／Risk Cap。**本 📌 讀法**：四 tone＝語意軸、D3 三族＝外觀軸，兩軸正交併存（撰寫組讀法，INFERENCE）。**仍有效**：三族外觀（資訊／狀態／護欄）、護欄實線粗框、該末句的**目的**（Danger／Positive ⛔ 與 Missing／限制語意混淆：⛔ 用 ⬜、⛔ 與 `🔴 取得失敗` 同字）、D1a／D1b／D5／D6／D8／D10(a)。兩邊理由：舊句防止視覺語言爆炸（仍成立）；新句依客戶明示需要「確定性違規」與「中性資訊」兩種既有三族表達不了的語意。

> 2026-10-30 補登（取下一個未用號；落盤前 `grep -rn "DEC-115" docs PROJECT_RULES.md` 0 命中，DEC-114 為上一號）。**來源類別：客戶（使用者本輪對話原文），經總管轉交「逐字要點」給撰寫組；撰寫組照錄要點，非客戶訊息全文逐字**（客戶原訊息全文撰寫組未見；下列引號內文字為總管轉交的客戶要點原句）。

- **決策者**：客戶（2026-10-30，針對 `docs/vnext/PHASE3_SHARED_COMPONENTS_WIREFRAME_2026-10-30.md` §6 裁示表七題；題幹／選項見該檔 §6）。｜**日期**：2026-10-30。｜**範圍**：UI／呈現（Phase 3 共用視覺元件：色彩、chip、迷你圖、冷啟動空槽、切換鈕、圖 A 標籤配額）。｜**狀態**：**生效**。
- **裁示（客戶逐字要點，以此為準）**：

| 題 | 裁示 | 白話 |
|---|---|---|
| D1a | **A** | 客戶已裁示的顏色全部維持（含淺色版中性暫值照現況，不另改） |
| D1b | **B** | 客戶沒裁示過的顏色與圓角，**延到 Phase 4～6 逐頁收斂**，Phase 3 不全站換色 |
| D3 | **A** | chip 採三族；護欄＝實線粗框 |
| D5 | **A** | 迷你趨勢線與小倍數都不顯示數字 |
| D6 | **B** | 主圖冷啟動保持同高；次要圖／小倍數缺資料時縮成一行誠實 placeholder |
| D8 | **B** | 切換鈕用膠囊式；但須先在最低支援 Streamlit 1.56 實跑驗證，不成立就退回 A |
| D10 | **(a)** | 圖 A 的「來源」下沉到摺疊；兩條逐字護欄各自獨立、不合併 |

- **補充邊界（客戶要點）**：
  1. **D1a**：已由客戶裁示的主按鈕藍（`#1f6feb`／light `#044cb6`）、深色中性灰藍（`--sig-neutral`／`-bg` dark `#8fa3b8`／`#26313d`）維持，**不因 Phase 3 共用元件重做而改色**。（📌 來源標示：「淺色版中性暫值照現況」＝D1a 題幹／客戶裁示 A 的內容；「深色中性灰藍 `#8fa3b8`／`#26313d`」數值＝D1a 題幹所載之現況值，**非總管加碼**；此為標示來源，非新增決定。）
  2. **D1b**：未裁示的顏色與圓角**不要在 Phase 3 一次改全站**；Phase 4～6 各頁依核准線框**逐頁收斂**，避免 Phase 3 擴張成全站換膚。
  3. **D3**：chip 採三族（資訊／狀態／護欄）；護欄用**實線粗框**。**不得**新增會與既有 Missing／限制語意混淆的**第四套視覺語言**。
  4. **D5**：mini sparkline／small multiples **不額外顯示最新／最高／最低數字**。重要數字應由 KPI／status chip 承擔，避免圖表再次數字化。
  5. **D6=B**：Primary Visual 保持正式高度／位置，避免載入前後 layout jump；Secondary Visual 缺資料時縮為一行誠實 placeholder，避免手機與桌機出現大片無資訊空槽；**不得因此隱藏 Missing／unavailable 狀態**；此項若改變既有 Presentation Contract 字面規則，**以本次客戶裁示正式追加 DEC 並同步契約／相關 SSOT，不得只留在線框**（＝本 DEC＋契約 §8-4 就地加註，見下）。
  6. **D8=B**：膠囊式切換**必須先在最低支援 Streamlit 1.56 實跑驗證**；若 API／行為／手機互動不成立，**直接退回 A 圓點單選，不需要再次請示**；**不得為了 B 升高最低版本**（`requirements.txt` floor 不動）。
  7. **D10=(a)**：來源下沉到「為什麼／來源／限制」摺疊；兩條語意護欄維持各自獨立，不合併。理由：語意護欄優先於 metadata source；來源仍可追溯，只是進 L3，不算刪除資訊。（📌 來源標示：「語意護欄優先於 metadata source；來源仍可追溯、不算刪除資訊」為**客戶原文要點**，非總管加碼；此為標示來源，非新增決定。）**不要為了把 6 顆壓成 5 顆而做出一顆過長、混合兩個語意的 chip。**
- **站殼間距（原 D7）**：依 AI 總管原方案——**先內部實測**，取得實際像素差與最小改動方案後，**若屬整體 layout 變更再送客戶裁示**；本 DEC 不核准任何站殼改動。
- **W2～W9**：**維持原 Gate，不提前處理**（Presentation Contract §22 原樣有效；W1 已由 D1a 裁示「維持」）。
- **施工授權（客戶要點）**：依**已核准 Phase 3 範圍**靜默施工；Sonnet 5.5＋Medium 若符合最低必要設定直接繼續；除真正 Customer Decision Gate、Model×Effort 必須切換、需客戶手動操作、完整 Phase 3 完成或 context 不安全外，全程 SILENT。（承 DEC-084／DEC-106 不重複要求切換；DEC-113 對 Phase 2 的降級已隨 Phase 2 結束，Phase 3 步驟 1 起的 Model×Effort 仍依 DEC-084／106 開工前核對實際設定。）
  - 📌 **來源標示（2026-10-30 有意識的更正，不是漏刪；決策者 AI 總管〔事實更正：來源歸屬〕）**：上列「施工授權」五項（依已核准 Phase 3 範圍靜默施工；Sonnet 5.5＋Medium 若符合 Minimum Sufficient Effort 直接繼續、不需再次確認；除 Customer Decision Gate／Model×Effort 必須切換／需客戶手動操作／完整 Phase 3 完成／context 不安全外全程 SILENT）為**客戶授權**，保留。**「只有碰投資語意、Risk Cap、資料契約、重大架構衝突才升回 Opus 5.5＋High」不是客戶原文，是 AI 總管內部判斷（依 DEC-084／DEC-106）**，僅為總管判斷何時須回報「Model×Effort 必須切換」的操作準則，不得被引用為客戶授權；Migration Plan §16.1 已同步改標。
- **改變既有契約字面的三處（有意識的政策變更，不是漏刪；契約原文保留、已就地加註）**：
  1. **D6=B → 契約 §8-4**「圖槽保留同一 compact 高度」的冷啟動字面：改為**僅 Secondary／small multiples／mini 圖**缺資料時縮為一行；**Primary 不變**（仍同高、仍不畫任何線／點）。Gate A9 的「圖槽」判準同步讀作 Primary。
  2. **D1b=B → 契約 §14 R15／§14.2「tokens 於 Phase 3 收斂」**時程：改為**Phase 4～6 逐頁**；Phase 3 只加性新增幾何 token（含 14px 圓角 token，只新增、不套用）、不改任何既有色值，`page_css()` 輸出 byte-identical。DEC-110 R15 的時程部分被本條取代（R15 其餘——blueprint＝Visual SSOT、客戶裁示色值除外——不變）。
  3. **D10(a) → 契約 §4 圖 A chip 配額**：圖 A 外露 5 顆＝資料日、窗口、可讀＋2 顆**各自獨立**的逐字護欄；客戶範例（DEC-109 五）中的「來源」chip **移入摺疊「來源」段**（資訊仍在、可追溯）。契約 §6 同步記 D3（chip 三族、護欄實線粗框、禁第四套視覺語言）。
  - 未改字面、僅記錄採用：D1a、D3（契約 §6 無外觀規定，屬新增）、D5（契約 §19 Q4／Q5 無數字規定，屬新增）、D8（契約 §12.1 僅寫「segmented／switcher」，未定外觀）。
- **兩邊理由並陳**：
  - **D6**：舊字面（所有圖槽冷啟動同高）的理由——載入前後版面不跳動——**仍成立，故 Primary 保留**；新做法勝出於 Secondary，因為客戶的第一個抱怨之一是「空白太多／資訊密度不對」（DEC-108，經總管轉交），次要圖在第一屏之外，載入後位移影響最小。**代價（據實）**：載入後下方內容會下移一次。
  - **D1b**：舊時程（Phase 3 全站一次收斂）的理由——新舊頁立刻同色、與 blueprint 一致最早——**仍成立**；新做法勝出因為 Phase 3 沒有任何頁面掛新元件，無法證明換色後第一屏仍合格，逐頁換色可逐頁對照驗收。**代價（據實）**：過渡期既有頁面與 blueprint 視覺基準不一致、新舊頁可能並存兩套近似色（登 BACKLOG `P1R-P3-D1B-TRANSITION-PALETTE`）。
  - **D10(a)**：DEC-109 五的客戶範例把「來源」列為外露 chip——**理由仍成立**（來源是可追溯性的第一線）；(a) 勝出於客戶本次明示「語意護欄優先於 metadata source」，且不犧牲追溯（來源進 L3 摺疊）、不做出混合兩個語意的長 chip。
- **線框草案中因本裁示而「未採用」的內容**（原文保留於 `PHASE3_SHARED_COMPONENTS_WIREFRAME_2026-10-30.md`，已加註）：D10(b) 的合併護欄 chip（`parts` 欄位與合併 kind 規則、桌／手機 (b) 線框）；護欄虛線（D3 B）；D5 B／C（小倍數每格最新值、三個數字）；D6 A／C（全部同高／全部縮一行）；D8 C（pills）、D8 預設 A 的「不裁示預設」；D1a B／C、D1b A。
- **與其他 DEC 的關係**：承 DEC-109（客戶 Phase 1～7、blueprint＝Visual SSOT）、DEC-110（R15、契約 §4／§6／§8／§19 內部規格——被本裁示調整的三處見上）、DEC-113／114；呼叫 DEC-082（版面草稿先行：本裁示即該線框的核准）、DEC-106（Model×Effort 不重複要求切換）；不降低任何 Security／Investment／Data／CI／Audit Gate；Missing Contract（DEC-109 八）、逐字護欄句（DEC-092 Q2）、`UI_STATE_META` 十態、`BADGES` 封閉 11 種皆不變。
- **落點**：`docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md`（§4、§6、§8、§11、§14、§19、§22 就地加註）；`docs/vnext/PHASE3_SHARED_COMPONENTS_WIREFRAME_2026-10-30.md`（狀態改已核准、§6「裁示結果」）；`docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md` §16（核准範圍與施工拆分）；`docs/HANDOFF.md`、`docs/PROJECT_STATE.md` §48、`docs/BACKLOG.md`。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本 DEC 由撰寫組依總管轉交之要點落盤，**未經第二組獨立驗證**；「三處改變契約字面、其餘未改」為撰寫組單組判讀（已 grep 契約與線框文件相關詞，但全稱句屬待驗事項）；D8 的 1.56 實跑**尚未做**，不得當作已驗。

### DEC-116｜Phase 3 站殼間距（原 D7）客戶裁示：D7=B 最小改動，七條限制；施工結果（客戶 2026-10-30）

> 2026-10-30 補登（取下一個未用號；落盤前 `grep -c "DEC-116" docs/DECISIONS.md` ＝ 0，DEC-115 為上一號）。**來源類別：客戶裁示（經 AI 總管轉交的要點，撰寫／施工組照錄；非客戶訊息全文逐字）**。承 **DEC-115**「站殼間距：先內部實測，若屬整體 layout 變更再送客戶裁示；本 DEC 不核准任何站殼改動」——本條即該客戶裁示。

- **決策者**：客戶（2026-10-30）；AI 總管依 DEC-115 判定屬整體 layout 變更後，附推薦方案 R 送客戶。｜**範圍**：UI／呈現（站殼：新版四頁模式上留白）。｜**狀態**：**生效**（施工與實測結果見下；Streamlit 僅量 1.59.2）。
- **裁示（客戶要點）**：**D7＝B 最小改動**。以下七條為限制，違反任一條＝退回方案 C（維持現況、不改 `src/`），不需請示：
  1. 只作用於新版四頁（nav4）模式；`?legacy=1` 逐 byte 不得受影響（只能改 `src/ui/views/shell_nav4.py::_CSS_TEMPLATE`；不得動 `app.py`、不得動 z60 指紋範圍內任何檔）。
  2. 上留白縮到約 72px，且只隱藏「確定只含 `<style>`／無內容」的空 element-container（Measurement 報告 §4 方案 R 的兩條規則）。
  3. `:has()` 或 Streamlit 內部 selector 失效時必須安全退回現況、不得破版；須有測試守這點（不得有任何「靠 CSS 才顯示」的規則）。
  4. 完成後四頁（📊 市場、🎯 標的、💼 持股、👤 我的）都要驗：desktop 1440×900、mobile 390×844、cold start、loaded state（能造什麼造什麼，造不出須據實寫「未實測」與原因）、並做 Visual Fidelity Gate（`docs/governance/UI_VISUAL_FIDELITY_GATE.md` §5 例外流程：前後截圖）。
  5. 若 selector 誤藏內容、造成 layout jump、影響 legacy，或必須擴大成全站高風險 CSS → 退回方案 C，並如實寫報告，不需請示。
  6. 不得提高 Streamlit 最低版本（`requirements.txt` 不動）。
  7. 不得提前做 Phase 4 任何事。
- **兩邊理由並陳**：
  - **方案 C（不做）／方案 A（只改 padding −24px）**：理由仍成立——零風險／風險最低，且不依賴 Streamlit 內部 `data-testid` 與 `:has()`。
  - **方案 B（R）勝出**：客戶明示「空白太多／資訊密度不對」（DEC-108 經轉交）；R 不增減任何可見元件、僅 nav4 注入、`:has()` 失效時規則不命中而回到現況（良性降級）。**代價（據實）**：新增對 Streamlit 內部 `stMainBlockContainer`／`stVerticalBlock`／`stElementContainer`／`stMarkdownContainer` 的依賴；四頁第一屏所有內容統一上移（見施工結果）。
- **施工結果（2026-10-30，執行組實測；細節見 `docs/vnext/PHASE3_SHELL_SPACING_MEASUREMENT_2026-10-30.md` §8）**：未觸發退回 C。改動＝`src/ui/views/shell_nav4.py::_CSS_TEMPLATE` 加兩條無 media 規則（`padding-top:72px !important`、隱藏 style-only 容器）＋`tests/test_nav1_shell_nav4.py::TestCss` 守衛調整（放寬只到「style-only 容器那一條」，另加 mutation 守衛）；`app.py`、z60 指紋範圍、`requirements.txt`、`src/ui_v2/tokens.py`／`page_css()` 0 diff。實測：四頁第一個 H2／第一個可見內容 y 一律 **135.19**（原 223.19／207.19）；`?legacy=1` 全部量測值前後相同、DOM 不含新規則；規則剝除後回到原值。僅量 Streamlit 1.59.2，**1.56～1.58 未驗**；單組執行與自驗，待獨立 QA。
- **與其他 DEC 的關係**：承 DEC-115（站殼間距條）、DEC-108／109（空白太多、Phase 1～7）；呼叫 DEC-082（版面草稿先行：客戶裁示即核准）；不降低任何 Security／Investment／Data／CI／Audit Gate；不動 DEC-115 的 D1a～D10 任何一條；Phase 4 仍須先出 📊 市場頁文字線框（W2、W3、W9）送客戶拍板，拍板前不得寫 Phase 4 UI code。
- **落點**：`docs/vnext/PHASE3_SHELL_SPACING_MEASUREMENT_2026-10-30.md`（§8）、`docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md`（§17.2／§17.6／§18）、`docs/governance/UI_VISUAL_FIDELITY_GATE.md`（§5 例外流程紀錄）、`docs/HANDOFF.md`、`docs/PROJECT_STATE.md`、`docs/BACKLOG.md`。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本 DEC 的「客戶裁示」欄由執行組依總管轉交要點落盤；「施工結果」為單組實測自述，**未經獨立 QA 複驗**，不得當前提。

### DEC-117｜Phase 4 步驟 0（📊 市場頁線框）客戶裁示：Q1=B／Q2=A′／Q3=A／Q4=P-B／Q5=B／Q6=A／Q7=A／Q8 8a／8b／8c 全 A＋補充裁示（含 DEC-105 1A 在 📊 市場頁的 supersede）＋Model×Effort 切換指示（客戶 2026-10-30）

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S24／S25：Q2=A′ 指路必指向 16 項 expander；Q3=A 圖／tile 摺疊標籤；Q6 完整原句保留在摺疊（落點→Evidence，退化句逐字外露維持）；Q8 圖 C 原句→「為什麼」、⚡ 展開清單的頁內落點）** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。

> 📌 **Q4「保留正式原生圖」＝客戶澄清為「保留正式完整主圖的資料與視覺語意」，不是把 implementation 永久綁死在 `st.line_chart`；手機 Primary 圖高維持約 220px（契約 Q3 手機 ≤140px 內部建議值於 📊 市場頁為客戶明確例外） BY DEC-119**（2026-10-31 客戶澄清／例外，有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-119）；append-only，本條原文一字未改）。圖 A 實作改為 `st.vega_lite_chart` 自訂 spec（指數線／MA4 條水平參考線／y 軸／5 項圖例全保留）。

> 📌 **Q7 手機 mobile exception 擴及「⚡ 需要處理」（附條件）、線框 §10 C1-10／U4 取代、C1-9 補充（真錯誤改放今日結論正下方）BY DEC-118**（2026-10-30 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-118）；append-only，本條原文一字未改）。
> 📌 **Q1=B 的手機「2＋1」核心狀態排法 SUPERSEDED BY DEC-122 Q3=A（只限 📊 市場頁手機）**（2026-11-02 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-122 裁示 Q3=A）；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S10）：手機第一屏改為「市場目前狀態、Risk Cap、是否需要行動、主 Update CTA」不用滑；第三格「今日主要風險」移到**緊接第一屏之後**（仍屬 L1，不得被 L2／L3 插隊）。**仍有效**：Q1 桌機 3 個核心狀態 tile＋頁首主 CTA、「固定 3 欄」為桌機網格要求；Q2～Q8（含 Q5 桌機順序、Q6 主要風險縮短行與退化句逐字外露、Q7 手機 Primary mobile exception）；補充裁示。兩邊理由：2＋1 讓三張核心狀態在手機並列（當時成立）；新條依客戶 Q3=A 的手機第一屏必要項，並由客戶指名 supersede DEC-117。

> 2026-10-30 補登（取下一個未用號；落盤前 `grep -rn "DEC-117" docs PROJECT_RULES.md` 0 命中，DEC-116 為上一號）。**來源類別：客戶（使用者 2026-10-30 本輪對話原文），經總管轉交「客戶裁示原文」給撰寫組；下方 fence 內逐字收錄，未改一字**（撰寫組未見客戶原訊息本身，只見總管轉交之全文；若與原訊息有出入，以原訊息為準）。

- **決策者**：**客戶**（2026-10-30，針對 `docs/vnext/PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30.md` §6 決策表 Q1～Q8；題幹、選項、推薦與「會動到」見該檔 §6）。｜**日期／效力日期**：2026-10-30 起生效。｜**範圍**：UI／呈現（📊 市場頁第一屏結構、核心狀態網格、主圖形態、摺疊標籤、指路句、風險卡外露層、手機第一屏、三項下沉）＋治理（Model×Effort 切換指示）。｜**狀態**：**生效**（裁示＝線框核准；**施工尚未開始**——客戶指示先依 Durable Memory Contract 落盤、再停在安全 checkpoint 通知切換 Model×Effort，客戶回覆「改好了」後才施工）。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：

```
Phase 4 步驟 0 裁示如下：
- Q1：B
- Q2：A′
- Q3：A
- Q4：P-B
- Q5：B
- Q6：A
- Q7：A
- Q8：8a／8b／8c 全部 A

補充裁示：
Q1
桌機採 3 個核心狀態 tile：
- 市場位階
- 建議總持股水位
- 今日主要風險
「🚀 更新今日戰情」改為頁首主 CTA，不再占一張 KPI tile。
手機採 2＋1：
- 市場位階｜水位並排
- 今日主要風險整列
這裡明確裁示：
「固定 3 欄」是桌機核心狀態網格要求，不代表手機必須硬排 3 欄；手機應依可讀性自適應。

Q2
採 A′。
維持說明句，不新增指路 chip。
文字縮短，但必須保留：
- 「指標危險度」
- 「指標明細（16 項）」
- 指向最上方的關係

Q3
採 A。
- 圖表：使用 "為什麼／來源／限制／去哪補"
- tile／⚡：維持「查看依據」
兩者是不同資訊物件，不必為了表面一致而強制改成同一套。

Q4
採 P-B。
- 🇹🇼 台股趨勢＝Primary Visual
- 保留正式原生圖、MA 參考線、y 軸、圖例
- 國際 5 系列＝Secondary small multiples
- 不做切換列
- mini／small multiples 不顯示數字，沿用既有裁示
- 詳細數值仍保留在 L2 原始資料／完整圖中
不得因 compact 顯示而改變台股／國際趨勢的正式定義；目前未定義仍必須顯示 "⬜ 尚未定義"。

Q5
採 B：今日結論全面提前到核心狀態 tile 之前。
我明確同意更新／取代 DEC-105 1A 在市場頁的舊相對順序。
新順序：
頁首
→ 更新 CTA
→ 今日結論
→ 3 個核心狀態
→ ⚡需要處理
→ AI／資料狀態
→ Primary Visual
理由：
手機第一屏必須優先看到「現在怎麼樣／是否需要行動」；不能為保留舊順序而讓手機結論被截在第一屏之外。
請正式新增 DEC，建立清楚 supersede 關係，不要直接改掉舊 DEC 歷史。

Q6
採 A。
主要風險外露層採縮短行：
"燈色＋桶名＋燈名＋方向"
完整原句、燈說明、同級並列等資訊全部保留在摺疊。
但下列退化／護欄句必須外露逐字保留，不得縮掉：
- 未評估不等於安全
- 資料不足／無法判定
- 尚未載入
- 真錯誤

Q7
採 A，接受手機 Primary Visual 位於第一屏下方，Visual Fidelity Gate 登記合理 mobile exception。
手機第一屏優先順序：
今日結論 > 核心狀態 > 是否需行動 > Primary Visual
不得為了硬塞主圖進第一屏，而把核心狀態或結論擠出去。
但 Primary 必須緊接 L1 決策區後方，不得被其他 L2／L3 長內容插隊。

Q8
8a／8b／8c 全部 A：
- 圖 C 的完整原句移到「為什麼」
- 更新模式 radio＋長說明移到「更新選項」
- ⚡需要處理改成一行 bar＋展開清單
資訊只能下沉，不得刪除。

請先依 Durable Memory Contract 把本次 Q1～Q8 裁示正式落盤：DECISIONS、PROJECT_STATE、HANDOFF、Phase 4 wireframe／相關正式規格、必要 BACKLOG 狀態。之後再開始 Phase 4 UI code。
本階段頁面組裝涉及：今日結論位置、missing≠0、未評估≠安全、Risk Cap 未核准語意、客戶逐字句、還原鏈。因此同意切換至 Model：Opus 5.5／Effort：High。依 Model×Effort Gate，請先停在安全 checkpoint，通知我切換；我回覆「改好了」後再施工。
後續機械式測試改寫／mutation／截圖與量測若可安全降回 Sonnet 5.5＋Medium，依既有 Gate 在完整安全 checkpoint 再通知即可。
```

- **裁示整理表**（撰寫組整理；**以上方 fence 原文為準**，有出入以原文為準。「施工約束」欄凡加引號者為客戶原文，其餘為撰寫組依線框 §3／§6 對應的既有常數／元件名，屬 INFERENCE 對映）：

| 題 | 裁示 | 施工約束（⭐＝客戶原文明示） | 受影響物件（依線框 §6「會動到」與 §7；實作前以當時 main 重測） |
|---|---|---|---|
| **Q1**（W9／`CV1-DR-12`） | **B** | ⭐ 桌機 **3 個核心狀態 tile**：市場位階／建議總持股水位／今日主要風險；⭐「🚀 更新今日戰情」改為**頁首主 CTA**，**不再占一張 KPI tile**；⭐ 手機 **2＋1**（市場位階｜水位並排；今日主要風險整列）；⭐ **「固定 3 欄」是桌機核心狀態網格要求，不代表手機必須硬排 3 欄；手機應依可讀性自適應**（客戶對 `CLAUDE.md` v3 §00 的明示解釋，見下方「固定 3 欄」條） | `_market_blocks.render_hero`（`st.columns(4)`→3 tile＋頁首動作列）、`page_market.render_page_market` 頁首（還原鏈新頭節）、更新 form 組裝位置（`single_submit_form` 語意不變）、`tests/test_market_blocks.py::TestStructure`（T23 欄數斷言改寫為欄數＋資訊守恆）；Gate A11／§2.2「KPI 列欄數暫不判定」解除 |
| **Q2**（W2） | **A′** | ⭐ **維持說明句，不新增指路 chip**；⭐ 文字縮短，但必須保留「**指標危險度**」「**指標明細（16 項）**」與**指向最上方的關係**；DEC-105 第 4 點三條守衛（冷／熱 session 皆有、目標 expander 標題字面「指標明細（16 項）」不改、expander 內第一張卡含「指標危險度」）照留 | `_market_blocks.DANGER_POINTER`（改字；線框示例 `指標危險度：見下方「指標明細（16 項）」最上方`，※示例非定稿）、風險 tile／圖 D 兩處渲染、`test_market_blocks` 指路守衛（字面改為「三要素存在」斷言，⛔ 降強度） |
| **Q3**（W3） | **A** | ⭐ **圖表**用「▸ 為什麼／來源／限制／去哪補」；⭐ **tile／⚡ 維持「查看依據」**；⭐「兩者是不同資訊物件，不必為了表面一致而強制改成同一套」 | 圖 A、國際組、圖 D 的摺疊（六欄 Basis→四段映射，線框 §3.5／F-10，內部拍板）；tile／⚡ 的「🔍 查看依據」六欄不動；16 燈卡「▸ 詳細」不動（在 L2 內，`page_today` 共用） |
| **Q4** | **P-B** | ⭐ 🇹🇼 台股趨勢＝**Primary Visual**；⭐ 保留**正式原生圖、MA 參考線、y 軸、圖例**；⭐ 國際 5 系列＝**Secondary small multiples**；⭐ **不做切換列**；⭐ mini／small multiples **不顯示數字**（沿用 DEC-115 D5=A）；⭐ 詳細數值仍保留在 **L2 原始資料／完整圖**；⭐ **不得因 compact 顯示而改變台股／國際趨勢的正式定義；目前未定義仍必須顯示「⬜ 尚未定義」** | `_market_blocks.render_chart_a`／`render_chart_b`（重寫）、小倍數組裝（`compact.small_multiples_html`＋`sparkline_svg`；掛頁一律 `st.markdown(unsafe_allow_html=True)` 或 data-URI，F-4）、系列顯示名 8 字上限（F-3，內部拍板）；L2「國際市場（原始資料）」expander 與走勢圖 gate **原樣保留**；D8 切換鈕不再需要 |
| **Q5** | **B** | ⭐ **今日結論全面提前到核心狀態 tile 之前**；⭐ **客戶明確同意更新／取代 DEC-105 1A 在市場頁的舊相對順序**；⭐ 新順序：**頁首 → 更新 CTA → 今日結論 → 3 個核心狀態 → ⚡需要處理 → AI／資料狀態 → Primary Visual**；⭐ 理由：手機第一屏必須優先看到「現在怎麼樣／是否需要行動」；結論句**句子與標題逐字不改**（DEC-081 Q2-1，本題只動位置） | `page_market.render_page_market` 區塊順序（還原鏈頭節）；`test_page_market`／`test_uim_market_page` 的順序斷言改為新順序；契約 §16 DEC-081 Q2-1 列「Hero／⚡ 相對順序可維持」在市場頁失效（見下 supersede） |
| **Q6** | **A** | ⭐ 主要風險外露層採**縮短行「燈色＋桶名＋燈名＋方向」**；⭐ 完整原句、燈說明、同級並列等**全部保留在摺疊**；⭐ 下列**退化／護欄句必須外露逐字保留，不得縮掉**：「未評估不等於安全」「資料不足／無法判定」「尚未載入」「真錯誤」；方向詞沿用 L2 原詞（⛔ 翻成惡化／好轉，線框 Q6 A） | `_market_blocks.hero_risk_lines`／`risk_item_text`（新增縮短函式，整句版保留供摺疊）；hero 與圖 D 仍同源（`hero_risk_items`＝`risks.risk_rows[:HERO_RISK_MAX_ITEMS]`，⛔ 重排／重算）；`test_market_blocks` hero 文字斷言改資訊守恆；四類退化句對應的既有字串見線框 §3.5b／§6 Q6「退化狀態文案處理」（撰寫組對映，INFERENCE） |
| **Q7** | **A** | ⭐ **接受手機 Primary Visual 位於第一屏下方**；⭐ **Visual Fidelity Gate 登記合理 mobile exception**；⭐ 手機第一屏優先順序：**今日結論 > 核心狀態 > 是否需行動 > Primary Visual**；⭐ **不得為了硬塞主圖進第一屏，而把核心狀態或結論擠出去**；⭐ **Primary 必須緊接 L1 決策區後方，不得被其他 L2／L3 長內容插隊** | 不動程式（排序已由 Q5 定）；`docs/governance/UI_VISUAL_FIDELITY_GATE.md` §8 例外紀錄；Gate 報告 A2（手機）依本題註明；守衛：區塊順序測試＋手機截圖量測 |
| **Q8** | **8a／8b／8c 全 A** | ⭐ 8a **圖 C 的完整原句移到「為什麼」**；⭐ 8b **更新模式 radio＋長說明移到「更新選項」**；⭐ 8c **⚡需要處理改成一行 bar＋展開清單**；⭐ **資訊只能下沉，不得刪除** | 圖 C 渲染（`CHART_C_SAY`／`CHART_C_BASIS`→摺疊「為什麼」，零數值／零圖形不變）；更新 form（`single_submit_form(options_label=…)`；預設值與「按了才重抓」語意不變）；`_market_blocks.render_alerts_block`（三態判別與「沒有來源不寫沒事」不變）；守衛：`chart_c_texts` 零數字、`ALERTS_NO_SOURCE` 三態、form 單次 submit |

- **「固定 3 欄」的客戶明示解釋（Q1 補充裁示；`CLAUDE.md` 不改）**：客戶原文「**「固定 3 欄」是桌機核心狀態網格要求，不代表手機必須硬排 3 欄；手機應依可讀性自適應。**」本句是**客戶本人**對 `CLAUDE.md` §-1.5.D v3 §00 前端/UI 組「固定 3 欄自適應網格」的**明示解釋**，記於本 DEC；⛔ 不是 AI 總管或撰寫組讀法。**`CLAUDE.md` 本身一字不改**（v3 §00 原文保留於逐字封存區；`PROJECT_RULES.md` 第 0.1 節：本團隊不修改、不重新解釋 `CLAUDE.md`）。DEC-110 R4「不在 DECISIONS 重新解釋 `CLAUDE.md`」約束的是**總管讀法**，本條為客戶解釋，不牴觸 R4；R4 所登的牴觸（`CV1-DR-12`／W9）由本 DEC Q1 **裁示結案**。⚠️ 本解釋的射程（撰寫組讀法，單組）：只就「核心狀態網格」與「手機排法」兩點；**不**延伸解釋 v3 §00 其他字句（例：Checkbox Gate、防重繪 `st.form`），也**不**自動適用其他頁的 KPI 列——其他頁仍依各頁線框（契約 §22）。
- **supersede 關係（有意識的政策變更，不是漏刪；決策者 客戶（DEC-117）；舊 DEC 原文一字未改，僅在條頭加 📌 指向本 DEC；append-only）**：

| 舊條 | 被取代的部分 | 關係 | 仍有效部分 |
|---|---|---|---|
| **DEC-105 1A**（今日結論句「維持在 Hero 四卡與『⚡ 需要處理』之間」；已被 DEC-109 部分取代為「相對順序可維持，但須在第一屏」） | **在 📊 市場頁**，結論句相對 Hero／⚡ 的**舊相對順序**（結論在 tile 之後）→ 改為 **Q5 新順序**（結論在 3 核心狀態 tile 之前） | **取代（📊 市場頁）**；客戶原文「我明確同意更新／取代 DEC-105 1A 在市場頁的舊相對順序」 | DEC-109 的「結論句必須在第一屏」照舊（Q5 同向加強）；結論句內容／標題逐字（DEC-081 Q2-1）不變；DEC-105 2A、3A、第 4 點指路三守衛不變 |
| **DEC-105 第 5 點**「Hero 用 4 欄（P2 偏離維持）」 | 📊 市場頁 Hero 4 欄 → **桌機 3 核心狀態 tile＋頁首主 CTA；手機 2＋1** | **取代（📊 市場頁）** | 第 5 點其餘三項 P2：「AI 佔位＋資料狀態 chip 合併一行」**維持**，其**位置**由 Q5 取代（⚡ 之後、Primary 之前）；「圖 D 文字指路」「更新鈕字樣未改」兩項不變；更新鈕字樣：客戶 Q1 原文以現行字樣「🚀 更新今日戰情」稱呼該 CTA，實作沿用現行字樣、不改字；字樣是否改為 DEC-091 §四「🚀 更新市場資料」仍屬 `UIM-UPDATE-BUTTON-WORDING`（P2），**本 DEC 不判**（撰寫組讀法） |
| **DEC-105 第 4 點**指路「形式（說明句 vs chip）」待 Phase 4 線框（DEC-105 條頭 📌、DEC-110 R5、`P1R-P4-WF-POINTS`） | 待拍板狀態 → **裁示：維持說明句（縮短），不新增 chip** | **裁示結案**（非推翻：第 4 點字面要求全部保留） | 第 4 點三條守衛＋「必須保留三要素」 |
| **DEC-091 §四**「第一列只放 3～4 個核心狀態：…更新：主 CTA『🚀 更新市場資料』」 | 📊 市場頁第一列取 **3** 個核心狀態；**更新改為頁首主 CTA、不占第一列 tile** | **部分取代（📊 市場頁）** | 「3～4」的上限語意（3 在範圍內）；「更新＝主 CTA」的角色保留（只換位置）；CTA 字樣「🚀 更新市場資料」vs 現行「🚀 更新今日戰情」不在本 DEC 範圍（`UIM-UPDATE-BUTTON-WORDING`）；§四 其餘（副標、圖 A～D 方向）不變；「市場狀態 🟢偏多…」早已被 DEC-105 2A 取代 |
| **DEC-091 §四 圖C**「圖上方『用企業獲利 EPS 搭配不同合理本益比情境，觀察目前指數位在便宜、合理或偏貴區域。』」＋**DEC-092** 設計方向核准「每張圖上方有白話說明」 | **📊 市場頁圖 C**：該句不再外露於圖上方，移到圖 C 摺疊「為什麼」（Q8a）；圖 C 外露只留標題＋「研究框架，未啟用」＋`CHART_C_EMPTY` 一句 | **部分取代（📊 市場頁圖 C）** | 句子本身逐字保留（只下沉、不刪，Q8「資訊只能下沉，不得刪除」）；圖 A、圖 B（國際組）、圖 D 的圖上方說明句照舊；EPS×PE 仍為 Research Framework |
| **DEC-110 R4**（總管內部）「`CV1-DR-12` 裁示前維持現狀；Gate 對 KPI 欄數暫不判定」 | 待裁示狀態 → **客戶已裁示（Q1）**；📊 市場頁 Gate 恢復判欄數（桌機 3 tile、手機 2＋1） | **裁示結案** | R4「不在 DECISIONS 重新解釋 `CLAUDE.md`」作為總管行為約束仍有效（本 DEC 的解釋是客戶本人的） |
| **DEC-110 R2**（總管內部）「1 Primary Visual 在第一屏」＋契約 §2 B1、§3 五問③ | **📊 市場頁手機版**：Primary 可位於第一屏下方（客戶核准的 mobile exception，附條件） | **部分取代（📊 市場頁手機）** | 桌機 Primary 仍須在第一屏（header＋圖上緣）；手機例外附條件：Primary 緊接 L1 決策區、不得被 L2／L3 插隊 |
| **DEC-110 R7**（總管內部）卡片摺疊標籤是否統一＝各頁線框待拍板（`P1R-WF-FOLD-LABEL`） | 📊 市場頁：**不統一**（圖用四段字樣；tile／⚡ 維持「查看依據」） | **裁示結案（📊 市場頁）** | Phase 5～6 各頁仍待各自線框；「▸ 詳細」（16 燈卡）不動 |
| **DEC-109**（客戶） | **不取代**。DEC-109 四「第一屏五問」中的③主要圖、十一「📊 市場頁設計方向」第一屏優先「主要市場圖」、附錄（同日前序指示 15:18Z）「四、目前三頁修正方向 📊 市場」第一屏優先「小型台股趨勢圖」：📊 市場頁**手機**依 Q7 由客戶核准例外（只豁免 Primary；「是否需行動」仍須在第一屏，線框 §10 C1-10）；DEC-109 三 Visual Budget、五（主圖 header 與摺疊字樣）、八（Missing Contract）全部照舊 | 例外登記（非取代） | 全部 |
| **DEC-110 契約 Q11**（結論句頂端相對 H2 ≤+200／+260，內部建議上限） | **不取代**（Q5=B 依線框靜態示意為 +151／+207，同向；真值待 Gate 實量） | 無 | 全部 |
| **DEC-081**（Q2-1 結論句、Q2-2 Risk Cap 逐字）、**DEC-092 Q2**（均線聲明逐字、趨勢 `⬜ 尚未定義`）、**DEC-115**（D1a～D10）、**DEC-116**（D7=B） | **不取代**；本 DEC 只動位置與外露層形式，所有逐字句與 Missing 語意照舊 | 無 | 全部 |

- **Model×Effort（客戶指示；承 DEC-084／DEC-106／`PROJECT_RULES.md` 第 18 節）**：
  - **頁面組裝**（今日結論位置、missing≠0、未評估≠安全、Risk Cap 未核准語意、客戶逐字句、還原鏈）：客戶**同意切換至 Opus 5.5／High**；客戶指示「**先停在安全 checkpoint，通知我切換；我回覆「改好了」後再施工**」。→ **在客戶回覆「改好了」之前，不得開始任何 Phase 4 UI code**（本 DEC 的落盤批次本身是 docs-only）。
  - **機械式工作**（測試改寫／mutation／截圖與量測）：客戶同意「**若可安全降回 Sonnet 5.5＋Medium，依既有 Gate 在完整安全 checkpoint 再通知即可**」→ 降回須在**完整安全 checkpoint**（`PROJECT_RULES.md` 第 18.2 節）並通知客戶；⛔ 在頁面組裝未完成的中途降級；⛔ 不經通知自行降級。
  - 何者屬「頁面組裝」、何者屬「機械式」的逐步切分＝AI 總管內部判斷（Migration Plan §20 草擬），不是客戶原文；客戶可推翻。
- **兩邊理由並陳**：
  - **Q5（DEC-105 1A 舊順序 → 新順序）**：舊順序（Hero 四卡在前、結論在後）的理由——先看狀態卡再讀合成結論、與 UI-M 已實作版面一致、改動最小——**仍成立**；且線框 Q5 推薦 A 時已指出桌機在 A 下結論句已在第一屏。新順序勝出：客戶原文「**手機第一屏必須優先看到『現在怎麼樣／是否需要行動』；不能為保留舊順序而讓手機結論被截在第一屏之外**」；並與 DEC-108 ①「結論先行」同向。**代價（據實）**：桌機的改動多於「只為第一屏可見」所必要（線框 Q5 B 缺點）；`test_page_market`／`test_uim_market_page` 順序斷言須改寫。
  - **Q1（Hero 4 欄 → 3 tile＋頁首 CTA）**（⚠️ 下列兩邊理由**出自線框 §6 Q1 總管推薦，非客戶原文**；客戶原文只有裁示與「固定 3 欄」解釋）：4 欄的理由——與 blueprint「4 張 hero」及 DEC-105 一致、改動最小——**仍成立**；3 tile 勝出：更新卡在 Q8b 下沉後只剩一顆鍵，單獨占一欄浪費，且桌機 tile 列高與手機 KPI 區塊（靜態示意 145／299px）才能落在契約 Q1／Q2 上限內。**代價（據實）**：偏離 blueprint「4 張 hero」（依 Gate §5 第 2 列以本 DEC 引用，不算偏離）；更新 form 移入頁首動作列，實高未驗（`P1R-P4-HEADER-FORM-HEIGHT`）。
  - **Q7（Primary 在手機第一屏 → mobile exception）**（⚠️ 客戶原文＝「接受手機 Primary Visual 位於第一屏下方」與第一屏優先序；「blueprint 手機框」一句**出自線框 §6 Q7 總管推薦，非客戶原文**）：「Primary 在第一屏」（R2／B1）的理由——圖表優先、第一眼看到主圖——**仍成立，且桌機照舊**；例外勝出於手機：客戶排定的第一屏優先序（結論 > 核心狀態 > 是否需行動 > 主圖），blueprint 手機框本身亦把圖 A 放在「往下捲」之後。**代價**：手機第一屏不含主圖。
- **線框中因本裁示「未採用」的內容**（原文保留於線框檔，已加註）：Q1 A（4 欄／2×2）、C（3＋1）、手機 B1 單欄堆疊；Q2 A（38 字原句）、B（chip）；Q3 B／C；Q4 P-A（切換列）、P-C（全小倍數）；Q5 A（線框重審後的推薦預設）、C（僅手機前移）、（D）只壓縮 tile；Q6 B／C；Q7 B／C；Q8 各子項 B；各題「不裁示預設」。
- **效力邊界**（各條出處；⚠️ 客戶本則原文未逐條重述，下列為撰寫組依既有 DEC／契約歸納，單組）：⛔ 新資料源／schema／公式／門檻／TTL／投資語意（出處：DEC-091 保護規則、DEC-109 Scope Guard〔`PROJECT_RULES.md` 第 24 節〕、線框 §1 不做清單）；⛔ Risk Cap 數字顯示（DEC-081 Q2-2、DEC-091(g)、DEC-109；本則 fence「Risk Cap 未核准語意」）；⛔ EPS×PE production rule（DEC-091(g)、DEC-109 十一）；⛔ 台股／國際趨勢正式定義（DEC-092 Q2；本則 fence Q4「不得因 compact 顯示而改變…正式定義；目前未定義仍必須顯示『⬜ 尚未定義』」）；⛔ 「惡化」判定（DEC-105 效力邊界）；⛔ 改 `PAGE_LABELS`／導覽殼／legacy（DEC-097、DEC-105 效力邊界）、`page_today.py`（DEC-081 Q1=C、DEC-105 效力邊界、Plan §7）、`app.py`（線框 §7.1：掛載點不變、z60 指紋）、`requirements.txt` floor（DEC-115 D8、DEC-116 第 6 點）；⛔ 提前做 Phase 5～7、W4～W8（DEC-109 三十一、契約 §22）；⛔ 接 Decision Digest／One AI Brain（DEC-109 三十一 Phase 7；Digest 契約）；Missing Contract（DEC-109 八）、`UI_STATE_META` 十態（DEC-110 R8）、DEC-081 Q2-1／Q2-2、DEC-092 Q2 逐字句全部不變；不降低任何 Security／Investment／Data／CI／Audit Gate（`PROJECT_RULES.md` 第 14／16 節慣例）。
- **與其他 DEC 的關係**：落實 DEC-082／`CLAUDE.md` v3 §03-2 ①（版面草稿先行：本裁示即 Phase 4 線框核准）、DEC-109 三十一（Phase 4＝📊 市場 reference）、`PROJECT_RULES.md` 第 0.1 節（變更既有裁示須新客戶 DEC：Q5 對 DEC-105 1A 即依此）與第 26 節（Durable Memory Contract）；承 DEC-115（D3／D5／D6／D10 照舊）、DEC-116；呼叫 DEC-084／DEC-106（Model×Effort 雙向 Gate）、DEC-104（Hard Output Gate）。
- **落點**：`docs/vnext/PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30.md`（狀態改已核准；§4 標題；§6 各題「客戶裁示（DEC-117）」；新增 §10「Phase 4 施工驗收條件」；§10.6 U1～U6＝AI 總管內部判定，非客戶裁示）；`docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md`（檔頭、§3、§12.1、§15 R4、§16〔含 DEC-081 Q2-1 與 DEC-105 第 4 點兩列〕、§19 Q2、§22〔含 W2／W3／W9 表內〕就地加註）；`docs/governance/UI_VISUAL_FIDELITY_GATE.md`（§2.1 A2／A11、§2.2 KPI 欄數、§8 例外紀錄）；`docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md` §20（Phase 4 步驟 1+ 施工計畫）；`docs/HANDOFF.md`、`docs/PROJECT_STATE.md` §48、`docs/BACKLOG.md`（`P1R-PHASE4-MARKET`、`CV1-DR-12`、`P1R-P4-WF-POINTS`、`P1R-WF-FOLD-LABEL`、`P1R-P3-READABLE-VS-UNDEFINED`、`P1R-P4-RISK-TILE-FORM` 等）；本檔 DEC-091／DEC-092／DEC-105／DEC-109／DEC-110 條頭 📌 與 §5 取代鏈總表。
- 📌 **QA 修正輪（2026-10-30；本 DEC 為同一未合併批次內撰寫之文字，直接改寫；決策者 AI 總管〔依兩組獨立 QA 回報〕）**：補登 Q8a 對 DEC-091 §四 圖C／DEC-092「每張圖上方有白話說明」的部分取代；DEC-105 第 5 點、DEC-109（十一、附錄）、DEC-110 R5 的註記補正；兩邊理由標明出處；效力邊界逐條註出處；落點更正。線框 §10.6 U1～U6 由 AI 總管內部判定（非客戶裁示），fence 一字未動。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：fence 為總管轉交之客戶原文逐字；**整理表、supersede 表、「固定 3 欄」射程、四類退化句與既有字串的對映、頁面組裝／機械式切分**皆為撰寫組單組整理，**未經第二組獨立驗證**；「其餘 DEC 不取代」為撰寫組 grep 相關 DEC 後的判讀，全稱句屬待驗事項。

### DEC-118｜Phase 4 P4-1 客戶裁示：問題 1＝A（手機 ⚡ mobile exception）／問題 2＝D1（更新真錯誤放今日結論正下方）＋Customer Decision Gate 輸出硬限制＋GitHub Verification Gate 以當下 origin/main 為準（客戶 2026-10-30）
> 📌 ~~**問題 1=A（📊 市場頁手機 ⚡ 位於第一屏之後的 mobile exception）：條件式，待 DEC-122 Q3**（2026-11-02 登記，**不是取代**；決策者 客戶（DEC-122 指示）＋AI 總管〔判讀〕；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S10、§2）：客戶 2026-11-02 §40「市場 不用滑：市場狀態、Risk Cap、是否行動、refresh」與本條問題 1=A（客戶看過「手機第一屏一定看得到是否需行動」選項後知情選 A；總管轉述）相反，且需改 DEC-117 Q1 手機 2＋1 → 送 DEC-122 **Q3**（A＝照 §40 正式改本條與 DEC-117 Q1；B＝維持本條、§40 在市場頁讀為「緊接第一屏」）。**裁示前本條全部照舊有效**；問題 2=D1、Customer Decision Gate 輸出硬限制、GitHub Verification Gate 以當下 `origin/main` 為準在任何 Q3 結果下都仍有效。~~（2026-11-02 客戶裁示 Q1～Q3 後已過期；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留，現行見下一則 📌）
> 📌 **問題 1=A（📊 市場頁手機 ⚡ 位於第一屏之後的 mobile exception）SUPERSEDED BY DEC-122 Q3=A（只限手機部分）**（2026-11-02 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-122 裁示 Q3=A）；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S10）：客戶 2026-11-02 裁示 Q3=A——市場頁 Mobile-first，手機第一屏必須不用滑看到「市場目前狀態、Risk Cap、是否需要行動、主 Update CTA」；「今日主要風險」緊接第一屏之後、仍屬 L1、不得被 L2／L3 插隊。**被取代**：⚡ 位於手機第一屏之後的 mobile exception。**仍有效**：問題 2=D1（更新真錯誤放今日結論正下方）、Customer Decision Gate 輸出硬限制、GitHub Verification Gate 以當下 `origin/main` 為準；桌機不受影響；「緊接、不得被 L2／L3 插隊」原則延用到今日主要風險。兩邊理由：舊例外在當時結構下保住結論＋3 核心狀態進第一屏（當時成立）；新條依客戶最新、明確的手機要求（客戶原文「正式 supersede 與此衝突的 DEC-117／DEC-118／相關 DEC-120 mobile exception」）。

> 2026-10-30 補登（取下一個未用號；落盤前 `grep -rn "DEC-118" docs PROJECT_RULES.md` 0 命中，DEC-117 為上一號）。**來源類別：客戶（2026-10-30 本輪對話原文），經總管轉交；下方 fence 內逐字收錄，未改一字**（撰寫組未見客戶原訊息本身，只見總管轉交之全文；若有出入以原訊息為準）。題幹（問題 1／2 的選項文字）由總管撰寫送出、本檔未收錄原題；下方「整理」依客戶理由句與總管轉交之指示對映（撰寫組讀法，單組）。

- **決策者**：**客戶**（2026-10-30）。｜**效力日期**：2026-10-30 起。｜**範圍**：UI／呈現（📊 市場頁手機第一屏、更新報告真錯誤位置）＋治理（對客戶輸出格式、GitHub Verification Gate）。｜**狀態**：**生效**；實作隨 Phase 4 P4-1（Migration Plan §20）。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：

```
裁示：
- 問題 1：A
- 問題 2：D1

理由：
1. 手機第一屏優先維持「今日結論＋核心狀態」；⚡ 需要處理可列為 mobile exception，放在第一屏緊接之後，不得被其他 L2／L3 內容插隊。
2. 更新部分失敗時，真錯誤必須外露，但放在「今日結論」正下方，不得把今日結論擠出手機第一屏。

請將本次裁示正式落盤後繼續 P4-1。

另外再次修正你的對客戶輸出規則：

Customer Decision Gate 輸出硬限制

當真的需要我裁示時，只能輸出：
1. 第一行："🔴 需要你裁示"
2. 一句話說明「衝突是什麼」
3. 最多 2～3 題決策
4. 每題只保留：
   - A／B／C 選項
   - 每個選項最多一句差異
   - AI 推薦
5. 最後一行告訴我「請回覆 A／B／C」

總長原則 ≤12 行。

禁止在客戶訊息中輸出：
- QA 過程
- 測試數量
- 分支狀態
- 尚未開 PR
- 已 push
- 哪些內部修正正在做
- 哪些檔案 0 diff
- CI 等待狀態
- 多段像素表
- 內部實驗過程
- 「我接下來會…」
- 重複說同一個阻塞

這些全部寫進 PR／DEC／STATE／HANDOFF，不要倒給客戶。

只有當某個數值本身直接影響客戶選 A/B/C 時，才可保留該數值，而且只留最少必要值。

Hard Output Gate 不只判斷「能不能說」，還要判斷「最少要說多少」。

另外 GitHub Verification Gate 必須以當下 "origin/main" 實查為準；cron 可能已推進 main，不得把舊的功能 merge SHA 說成「最新 main」。
```

- **整理（撰寫組；以 fence 為準）**：

| 題 | 裁示 | 施工約束（⭐＝客戶原文） |
|---|---|---|
| 問題 1（線框 §10 C1-10：手機第一屏放不下 ⚡ bar） | **A** | ⭐ 手機第一屏優先維持「**今日結論＋核心狀態**」；⭐ ⚡ 需要處理列為 **mobile exception**，**放在第一屏緊接之後**；⭐ **不得被其他 L2／L3 內容插隊**。總管落地條件：⚡ 緊接在 3 核心狀態之後、中間不得有任何 L2／L3 內容；手機第一屏必含今日結論＋核心狀態（位階｜水位列） |
| 問題 2（線框 §10 C1-9：更新部分失敗的真錯誤位置） | **D1** | ⭐ 更新部分失敗時，**真錯誤必須外露**（⛔ 收合）；⭐ **放在「今日結論」正下方**；⭐ **不得把今日結論擠出手機第一屏**。CTA 與今日結論之間只剩收合的「更新選項」「更新報告」標題列 |
| 治理：Customer Decision Gate 輸出硬限制 | — | 見 fence 逐字；寫入 `PROJECT_RULES.md` 第 3 節（Hard Output Gate 小節下方 📌）與第 21.2 節（🔴 格式收斂） |
| 治理：GitHub Verification Gate | — | 以**當下 `origin/main` 實查**為準；cron 可能已推進 main，⛔ 把舊功能 merge SHA 說成「最新 main」；寫入 `PROJECT_RULES.md` 第 2 節 📌 |

- **supersede／補充關係（有意識的政策變更，不是漏刪；決策者 客戶（DEC-118）；舊文原文一字未改，條頭加 📌；append-only）**：

| 舊條 | 被取代／補充的部分 | 關係 | 仍有效部分 |
|---|---|---|---|
| **DEC-117 Q7**（手機 mobile exception 只豁免 Primary Visual） | 手機例外**擴及 ⚡ 需要處理**：⚡ 可位於手機第一屏之下，條件＝緊接 3 核心狀態之後、不得被 L2／L3 插隊 | **補充（擴大例外射程，附條件）** | Q7 其餘：手機優先序、Primary 緊接 L1 決策區、不得擠出結論／核心狀態 |
| 線框 §10 **C1-10**／§10.6 **U4**（總管判定：手機第一屏必須含 ⚡ bar） | 由本 DEC 問題 1=A **取代** | **取代** | 「是否需行動」改為「第一屏緊接之後」 |
| 線框 §10 **C1-9**（CTA→結論之間只允許兩個收合標題列）與 2026-09-24 客戶裁示（真錯誤留在收合區外） | 兩者衝突由 **D1** 調和：真錯誤外露、改放今日結論正下方 | **補充（解衝突）** | C1-9 嚴格化（任何狀態 CTA→結論之間無外露內容）；2026-09-24「真錯誤不得藏進收合區」照舊 |
| `docs/governance/UI_VISUAL_FIDELITY_GATE.md` §8 | 新增一列：手機 ⚡ mobile exception（§5 第 2 列） | 例外登記 | — |
| `PROJECT_RULES.md` 第 21.2 節 🔴 格式、第 3 節 Hard Output Gate、第 2 節 GitHub-first verification | 輸出格式收斂、「最少要說多少」、`origin/main` 當下實查 | 收斂／補充（舊文劃線＋理由並陳） | 其餘照舊 |

- **兩邊理由並陳**：問題 1——舊（U4，總管內部）理由：DEC-109 四④「是否需要行動」須在第一屏；新（客戶）理由：手機第一屏優先維持「今日結論＋核心狀態」，⚡ 緊接其後即可。問題 2——舊（2026-09-24 客戶）理由：真錯誤藏進收合＝假平安，仍成立且保留；舊（C1-9，總管內部）理由：CTA 與結論之間不得插長內容，仍成立；新（客戶）調和：真錯誤仍外露，只是位置改到今日結論正下方，不擠出結論。
- **效力邊界**：只動位置與手機例外射程；⛔ 新資料源／公式／門檻／TTL；⛔ 改 `page_today.py`、`app.py`；結論句、Risk Cap、趨勢 `⬜ 尚未定義` 等逐字約束照 DEC-117／DEC-081／DEC-092。
- **落點**：線框 §10（C1-9／C1-10 改寫、§10.7）、Gate §8、`PROJECT_RULES.md` 第 2／3／21.2 節、HANDOFF、PROJECT_STATE、BACKLOG、本檔 DEC-117 條頭 📌 與 §5 取代鏈。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：fence 逐字；整理表與 supersede 判讀為撰寫組單組產出，未經第二組驗證。
- 📌 **送審題幹附錄（2026-10-30 補登，append-only；QA 第二輪要求；上方各段原文未改）**：**出處＝AI 總管 2026-10-30 送客戶的裁示訊息**（由總管提供原文；撰寫組未見送出畫面本身）；**客戶回覆＝「問題 1：A；問題 2：D1」**（見上方 fence）。下方 fence 逐字收錄兩題選項；表格欄位依序為「方案｜做法｜優點｜缺點／風險」。客戶是在**知道各選項缺點**的前提下作答——尤其 D1 缺點「部分失敗時，3 張狀態卡會被往下推」與 A 缺點「手機要往下捲一下才看到 ⚡」皆屬客戶知情接受的代價。

```
問題 1：手機上 ⚡ 不在第一屏，怎麼處理？
| A（推薦） | 接受，和主圖一樣登記為手機例外；第一屏維持「結論＋位階｜水位＋風險卡」 | 完全照你 Q7 的優先序；字級和可讀性不受影響 | 手機要往下捲一下才看到 ⚡ |
| B | 只在手機把 ⚡ 那一行移到 3 張狀態卡之前，桌機順序不變 | 手機第一屏一定看得到是否需行動 | 改了你核准的順序，和 Q7 優先序相反 |
| C | 再壓字級到 13px、頁面標題縮小 | 順序不動 | 可讀性下降；有更新報告時仍做不到 |
問題 2：更新部分失敗時，結論句被擠出手機第一屏，怎麼處理？
| D1（推薦） | 錯誤訊息仍然外露、不收合，但移到「今日結論」正下方 | 兩條裁示都守住：真錯誤外露、結論先出現 | 部分失敗時，3 張狀態卡會被往下推 |
| D2 | 維持現狀，錯誤訊息排在結論之前 | 錯誤最先被看到 | 結論被擠出手機第一屏，違反你 Q5 的理由 |
```

  ⚠️ 撰寫組註（單組讀法）：題 1 選項 A 的做法欄寫「第一屏維持『結論＋位階｜水位＋風險卡』」，實量手機 loaded 態風險卡只露出上半（位階｜水位列完整在第一屏內）；施工條件依 Gate §8 該列（今日結論＋位階｜水位列在第一屏內）。若客戶以「風險卡須完整在第一屏」為準，屬待確認事項，記於 BACKLOG `P1R-P4-RISK-TILE-FIRST-SCREEN`（P2）。

### DEC-119｜Phase 4 P4-5 客戶裁示：題 1＝A（手機 Primary 維持約 220px，改用可完整控制圖例的自訂圖表呈現 5 項圖例；DEC-117 Q4「保留正式原生圖」之澄清）／題 2＝A（桌機全頁約 blueprint 2.02× 登記為已知輕微偏差）（客戶 2026-10-31）

> 2026-10-31 補登（取下一個未用號；落盤前 `grep -rn "DEC-119" docs PROJECT_RULES.md` 0 命中，DEC-118 為上一號）。**來源類別：客戶（2026-10-31 本輪對話原文），經總管轉交；下方 fence 內逐字收錄，未改一字**（撰寫組未見客戶原訊息本身，只見總管轉交之全文；若有出入以原訊息為準）。題幹（題 1／2 的選項）由總管撰寫送出；下方「送審題幹附錄」依總管轉交摘要收錄。

- **決策者**：**客戶**（2026-10-31）。｜**效力日期**：2026-10-31 起。｜**範圍**：UI／呈現（📊 市場頁圖 A 手機圖例與圖表元件、桌機全頁高）＋Visual Fidelity Gate 例外登記。｜**狀態**：**生效**；實作隨 Phase 4 P4-5（F1）。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：

```
題 1：A
題 2：A

補充裁示：

題 1
同意手機 Primary 維持約 220px，並改用可完整控制圖例的正式圖表實作，讓 5 項系列都可見。

我在此澄清 DEC-117 Q4 的「保留正式原生圖」：
要求的是保留正式完整主圖的資料與視覺語意，不是把 implementation 永久綁死在 "st.line_chart"。

必須保留：
- 指數主線
- MA5／MA60／MA120／MA200
- y 軸
- 5 項圖例全部可讀
- 資料來源／日期／Missing／stale 等既有語意
- 不得變成 sparkline／mini chart
- 不得正規化、改公式或改趨勢定義

允許為 mobile readability 改用 Streamlit 可承載的自訂圖表元件。

本裁示同時構成市場頁對 Visual Fidelity Gate「手機 Primary ≤140px」內部建議值的明確例外；不要再為了 140px 壓縮可讀性。

完成後仍需重新驗證 390×844：
- 無水平捲動
- 5 項 legend 全部可見
- 不遮圖
- 不擠壓第一屏既有優先內容
- desktop 不退化

題 2
選 A。
接受目前桌機全頁約 blueprint 2.02×，登記為已知輕微偏差。
理由：扣除站殼後內容約 1.9×；超出 2× 約只有 1%，不足以合理化重新設計 11 個已核准 L2/L3 摺疊列。
不得因此展開新的頁尾結構重構。

請把兩項裁示正式落盤後，依原 Phase 4 Gate 收尾。

建議模式：Sonnet 5.5／Effort：Medium
這是已明確定義的 UI／Visual Fidelity 修正，不需要升 Opus；只有修正過程碰到資料語意、投資定義、Risk Cap 或既有 DEC 新衝突時才升級。
```

- **整理（撰寫組；以 fence 為準）**：

| 題 | 裁示 | 施工約束（⭐＝客戶原文） |
|---|---|---|
| 題 1（手機圖 A 圖例被裁＋圖高 220 > 契約 ≤140；P4-3 Gate A6／F1） | **A** | ⭐ 手機 Primary 維持約 220px；⭐ 改用可完整控制圖例的正式圖表實作，5 項系列都可見；⭐ 必須保留：指數主線、MA5／MA60／MA120／MA200、y 軸、5 項圖例全部可讀、資料來源／日期／Missing／stale 等既有語意；⭐ 不得 sparkline／mini chart、不得正規化／改公式／改趨勢定義；⭐ 允許改用 Streamlit 可承載的自訂圖表元件；⭐ 重新驗證 390×844：無水平捲動、5 項 legend 全可見、不遮圖、不擠壓第一屏既有優先內容、desktop 不退化 |
| 題 2（P4-3 Gate A5：桌機全頁 3061／blueprint 1517＝2.02×） | **A** | ⭐ 接受約 2.02×，登記為已知輕微偏差；⭐ 不得因此展開新的頁尾結構重構；⭐ 不重新設計 11 個已核准 L2／L3 摺疊列 |

- **supersede／補充關係（有意識的政策變更，不是漏刪；決策者 客戶（DEC-119）；舊文原文一字未改，條頭加 📌；append-only）**：

| 舊條 | 被取代／補充的部分 | 關係 | 仍有效部分 |
|---|---|---|---|
| **DEC-117 Q4**（保留正式原生圖、MA 參考線、y 軸、圖例） | 「原生圖」＝**客戶澄清**為保留正式完整主圖的資料與視覺語意，不綁死 `st.line_chart`；允許自訂圖表元件 | **澄清（加註，不改舊文）** | Q4 其餘：台股＝Primary Visual、國際 5 系列＝small multiples、不做切換列、小倍數不顯示數字、詳細數值仍在 L2、`⬜ 尚未定義` |
| **契約 Q3**（Primary 主圖本體高 mobile ≤140px；`PRESENTATION_CONTRACT_vNext_2026-10-29.md` 表內 Q3 列）／DEC-110 R 系列內部建議值 | 📊 市場頁手機 Primary 維持約 220px | **明確例外（客戶；只限 📊 市場頁圖 A）** | 其餘頁、其餘 Primary 圖仍適用 Q3（桌機 ≤220px 不變）；契約與 DEC-110 原文不改 |
| `docs/governance/UI_VISUAL_FIDELITY_GATE.md` §2 A5（桌機全頁 ≤ blueprint 2×）／A6 | 市場頁 A6 例外、A5 登記為客戶接受之已知輕微偏差 | 例外登記（§5 第 2 列，客戶裁示覆蓋） | Gate 其餘項目與判準不變；⛔ 不得為過 Gate 放寬他頁判準 |
| P4-3 `GATE_REPORT.md` §11.1 題 1／題 2（原待客戶判斷） | 兩題由本 DEC 結案 | 結案（舊文劃線保留） | §0～§15 其餘不變 |

- **兩邊理由並陳**：
  - 題 1——舊（契約 Q3／DEC-110 內部建議值）理由：手機第一屏空間珍貴，Primary 圖壓低可讓更多優先內容進第一屏，**仍成立**（且 Primary 位於手機第一屏下方已是 DEC-117 Q7 例外）；新（客戶）理由：壓到 140px 會讓 y 軸與 5 項圖例更擠、可讀性下降，**可讀性優先**，且圖例被裁已讓客戶明列「保留圖例」的要求在手機失效。舊（DEC-117 Q4 字面「原生圖」）理由：沿用 Streamlit 既有圖元件最小改動，**仍成立為預設**；新（客戶澄清）：要保留的是資料與視覺語意，元件可為 mobile readability 更換。
  - 題 2——舊（Gate A5 ≤2×）理由：頁面長度是視覺密度的粗略護欄，**仍成立**；新（客戶）理由：扣除站殼後內容約 1.9×，超出約 1%，不足以合理化重新設計 11 個已核准 L2／L3 摺疊列。
- **效力邊界**：只動 📊 市場頁圖 A 的**呈現元件**與 Gate 例外登記；⛔ 新資料源／公式／門檻／TTL／趨勢定義（`⬜ 尚未定義` 照舊）／MA 水平參考線語意（仍是「市場評估」輸入的**最新值**水平線，不自行算均線）／Risk Cap／Digest／Brain；⛔ 動 `page_today.py`、`app.py`、`requirements.txt`、`compact.py`（只加不改）、z60 指紋、page_css sha；⛔ 他頁套用 220px 例外；⛔ 據題 2 展開頁尾／摺疊列重構。
- **落點**：`src/ui/views/_market_blocks.py`（圖 A `render_twii_chart`＋`twii_chart_spec`／`twii_chart_long`；`twii_chart_frame` 不變）、`tests/test_p4_2_market_charts.py`（圖 A 守衛改寫為 vega spec 語意守衛，不降強度）、`docs/vnext/phase4_market/p4_5/`（量測腳本／截圖／mutation）、`p4_3/GATE_REPORT.md` §16、Gate §8、HANDOFF、PROJECT_STATE、BACKLOG（`P1R-P4-GATE-A5-PAGE-HEIGHT`／`-A6-MOBILE-CHART-HEIGHT`／`P1R-P4-PRIMARY-LEGEND-MOBILE(-FIX)` 結案）、本檔 DEC-117 條頭 📌 與 §5 取代鏈、`PROJECT_RULES.md` 第 24.2 節 📌。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：fence 逐字；整理表與 supersede 判讀為撰寫組單組產出，未經第二組驗證。
- 📌 **送審題幹附錄（2026-10-31；append-only）**：**出處＝AI 總管送客戶的裁示題幹摘要（總管轉交；撰寫組未見送出畫面本身）**；客戶回覆見上方 fence。題 1：**A**＝主圖維持 220px，圖例改用自訂圖表呈現、縮短系列名並分兩行排，5 項都看得到；**B**＝壓 140px 圖例收進摺疊；**C**＝維持現狀。題 2：**A**＝接受 2.02× 記為已知偏差；**B**＝合併頁尾 11 個摺疊列。（⚠️ 題 1 A 的「縮短系列名」由實作組落實為：圖例短名＋「最新值，參考」限定語移到圖例標題，完整系列名逐字留在資料與 tooltip；見 P4-5 PR 說明。）

### DEC-120｜Phase 4 P4-3 Visual Fidelity Gate 收尾客戶裁示：選 A——📊 市場頁 A2／A4／A10／A11 四項 🟡 接受為已知合理偏離，不因「🟡≥4 視為 ❌」升格；Gate 判定 PASS（客戶 2026-10-31）
> 📌 ~~**A10／A11：條件式，待 DEC-122 Q3**（2026-11-02 登記，**不是取代**；決策者 AI 總管〔判讀〕；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S11）：若 Q3=A（手機「是否行動」進第一屏、改 DEC-117 Q1 手機排法），A10（手機主 CTA／行動首屏）與 A11（手機 KPI 區高度）失去 DEC-118 例外的前提，Stage B 重新量測、重新依 Gate 判定；若 Q3=B 則照舊。**裁示前本條全部照舊有效**；A2、A4 例外與「僅 📊 市場頁、不得泛化他頁」在任何結果下都仍有效。~~（2026-11-02 客戶裁示 Q1～Q3 後已過期；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留，現行見下一則 📌）
> 📌 **A10／A11 兩項 mobile exception SUPERSEDED BY DEC-122 Q3=A**（2026-11-02 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-122 裁示 Q3=A）；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S11）：A10（手機主 CTA／行動首屏）、A11（手機 KPI 區高度）的接受建立在 DEC-118 問題 1=A 的手機結構上；該結構已由 Q3=A 正式取代 → 兩項降為 Phase 4 歷史基準，Final UI Stage B 依新結構重新量測、依 Gate 判定。**仍有效**：A2 例外；**A4 桌機部分（桌機卡面）**；「僅 📊 市場頁、不得泛化他頁」；Phase 4 Gate PASS 的歷史結論。**A4 手機部分**（三卡均高 1.30×、手機卡面 114 字）成因為手機 2＋1 排法，已隨 S10 失去前提 → Stage B 重新量測並照 Gate 判定（AI 總管內部判定，屬收緊例外；2026-11-02 Freeze 獨立驗收修正）。

> 2026-10-31 補登（取下一個未用號；DEC-119 為上一號）。**來源類別：客戶（2026-10-31 本輪對話裁示「選 A」），經總管轉交。⚠️ 撰寫組只見總管轉交之摘要，未見客戶原訊息逐字；因此本條不設「逐字 fence」，下方為總管轉交之裁示摘要，若與客戶原訊息有出入，以原訊息為準。** 所選「A」對應 `p4_3/GATE_REPORT.md` §16.2 題（A＝接受這 4 項為已知合理偏離，不累計成 ❌；B＝逐項壓到上限；C＝只接受部分）。

- **決策者**：**客戶**（2026-10-31）。｜**效力日期**：2026-10-31 起。｜**範圍**：⛔ **僅限 📊 市場頁**（Phase 4）；⛔ **不得泛化到其他頁面**（🎯 標的頁、💼 持股頁、🏠 今日頁等各自重新量測、各自照 Gate 規則判定）。｜**狀態**：**生效**（裁示）；**Gate 結論「PASS」尚未完全成立**——條件見下。
- **裁示內容**：📊 市場頁 Phase 4 Visual Fidelity Gate 的四項 🟡 全部接受為「已知合理偏離」，**不**因 Gate §2「🟡 ≥4 視為 ❌」升格；Gate 判定 **PASS**。
- **四項偏離逐項（數值取自 `p4_3/GATE_REPORT.md` §16.2／§15 QA 更正後 P4-5 實量；內部建議值，非客戶硬規格）**：

| 項 | 量測值（📊 市場頁） | 內部建議值 | 成因（已核准結構的可預期結果） |
|---|---|---|---|
| **A2** Primary 突出 | 桌機 **report 態**圖本體頂端 y≈**916**（第一屏 900）；loaded 基準態 y868 ✅ | 第一屏至少露圖上緣（契約 B1） | report 態多出「更新報告」區塊，把 Primary 往下推（DEC-117／DEC-118 已核准的 report 態結構） |
| **A4** 卡片密度 | 手機三卡均高 211／blueprint 162＝**1.30×**（1.2～1.5＝🟡）；「今日主要風險」卡面 **98 字（桌機）／114 字（手機）**＞60；桌機均高 0.70× ✅ | 手機卡高 ≤1.2×；卡面 ≤60 字 | C6-3／C2 要求外露逐字保留退化／指路句；客戶核准 2＋1 排法（DEC-117 Q1） |
| **A10** 主 CTA／行動首屏 | 手機結論句頂端相對 H2：loaded **+269**／cold **+269**／report **+356**／partial **+292**（原 P4-3 區間 +269～+356）；上限 +260；桌機不超標 | 手機 ≤+260 | CTA 在結論前（客戶核准）＋站殼；Q7 手機 mobile exception（DEC-117／DEC-118） |
| **A11** 手機不被塞滿 | 手機 KPI 區塊 loaded **461**／cold **394**（report 同 loaded 量級）＞ **≤340**；水平捲動 0 | 手機 KPI 區 ≤340 | 3 核心狀態＋⚡ 緊接（DEC-118 問題 1=A）；風險卡保留逐字句 |

- **接受理由（客戶，經總管轉交摘要）**：四項均為**已核准結構的可預期結果**；**無資訊遺失**；**無 Missing／Risk／護欄語意退化**；**無新水平捲動或破版**；再壓回上限會**犧牲已核准的第一屏優先序或風險資訊**（即 §16.2 選項 B 與 DEC-117 Q1／Q6、DEC-105 相牴觸）。
- **「🟡≥4 規則」的處置**：Gate §2 的「🟡 ≥4 視為 ❌」規則對 **📊 市場頁這四項已裁示免升格**；**其他頁面仍照該規則**，⛔ 不得引用本條放寬他頁。V3 已於 §15 QA 改判 ✅，不在本裁示射程內。
- **Gate PASS 條件（兩者缺一不可；未滿足前不得宣稱 Stage complete／Phase 4 已結案／已 merge）**：① **CI 綠**（Fast checks＋Slow tests，以 PR #987 head 實查為準）；② **獨立 QA 組複驗**（Gate §4；A2／A10／A11 與全部 🟡 項，且須複驗「無 Missing／Risk／護欄語意退化、無新水平捲動」這幾句免升格前提確實成立；任一不成立＝本裁示失效，該項重回 Gate 判定）。
- **supersede／補充關係（有意識的政策變更，不是漏刪；決策者 客戶（DEC-120）；舊文原文一字未改；append-only）**：

| 舊條 | 被取代／補充的部分 | 關係 | 仍有效部分 |
|---|---|---|---|
| `docs/governance/UI_VISUAL_FIDELITY_GATE.md` §2 合計規則「🟡 ≥4 視為 ❌」 | 對 📊 市場頁 A2／A4／A10／A11 四項免升格 | **例外登記（僅 📊 市場頁；Gate §5 第 2 列：客戶裁示覆蓋）** | 規則本身對其他頁面不變；⛔ 不得為過 Gate 放寬他頁判準 |
| `p4_3/GATE_REPORT.md` §16.2「需客戶判斷（1 題）」與「Gate 判定：❌ FAIL（僅因 🟡≥4）」 | 題由本 DEC 結案（A）；判定改 PASS（待 CI＋QA） | 結案（舊文保留；新增 §17） | §16 其餘（F1 修正、量測、mutation）不變 |
| DEC-119 | 無衝突 | 銜接：DEC-119 題 1／題 2 的 A6 例外與 A5 偏差仍有效 | 全部 |

- **兩邊理由並陳**：舊（Gate 合計規則）理由——多項輕微偏離累積會讓頁面整體失去視覺紀律，**仍成立**，故他頁照舊；新（客戶）理由——四項皆由已核准結構決定、無資訊或護欄退化，壓回上限的代價（犧牲第一屏優先序或風險資訊）高於偏離本身。
- **效力邊界**：⛔ 只登記例外，**不改任何 UI／程式**；⛔ 不得趁機展開 UI 重構（頁尾／摺疊列／卡片排法）；⛔ 不得泛化到其他頁；⛔ 新資料源／公式／門檻／TTL／趨勢定義／Risk Cap／Digest／Brain 不動。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：客戶裁示僅見總管轉交摘要；四項數值轉錄自 GATE_REPORT（單組量測，未經第二組驗證；獨立 QA 複驗尚未發生）；「PASS」為裁示後的**待驗判定**，非已驗結論。


## DEC-121｜Phase 5（🎯 標的頁）step 0 客戶裁示：Q1=A／Q2=B／Q3=A（2026-10-31；客戶；docs-only 落盤）
> 📌 **Q2=B「整頁已核准順序不變」一句部分取代 BY DEC-122**（2026-11-02 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-122）；append-only，本條原文一字未改；判讀出處 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 S2）：🎯 標的頁改為客戶 2026-11-02 §10 雙模式，整頁順序隨之改變。**仍有效**：Q2 其餘（選股條件預設收合＋一行摘要、候選先顯示 Top 10、完整候選以展開取得、`DEFAULT_TOP_N=50` 等請求參數不變、Top 10 僅為呈現切片、收合不得解讀為減少抓取或計算）；**Q1=A、Q3=A 全部**；效力邊界（DEC-117／118／119／120 例外不自動繼承到標的頁）。兩邊理由：舊句保護已核准的單頁順序（當時成立）；新條依客戶明示雙模式。

- **Q1 = A（僅限產業 Top 5 的呈現與顯示排序）**：橫條圖，依既有欄位「近 5 日法人累計淨流入」由大到小。⛔ 不得改變候選池准入、基本面初篩、個股排序／分數、Risk Cap、正式產業趨勢定義或任何確定性投資規則；Missing 不得補 0、不得視為最強／最弱，沿用既有 Missing Contract。若實作需要改動領域語意，停手走 Decision Gate，不得擴大 Q1。
- **Q2 = B**：整頁已核准順序不變；選股條件預設收合＋一行摘要；候選先顯示 Top 10，完整候選以展開／細節取得。`DEFAULT_TOP_N=50` 等請求參數不變，Top 10 僅為呈現切片；收合 UI 不得解讀為減少抓取或計算。
- **Q3 = A**：排序依據維持一句說明（不改 chip）；主圖用「為什麼／來源／限制／去哪補」；其餘既有標籤不變；不為視覺統一而改全頁命名。
- **效力邊界**：只登記裁示，不改任何 UI／程式；Phase 5 UI 實作須先重跑 GitHub Verification Gate；DEC-117／118／119／120 的例外**不自動繼承**到標的頁。
- **關係**：補充 DEC-092（標的頁排序依據句客戶原句仍有效，本 DEC 不改句子文字）；實施依據 `docs/vnext/PHASE5_TARGET_PAGE_WIREFRAME_2026-10-31.md`。
- ⚠️ 揭露：裁示內容轉錄自 PR #990 checkpoint（`docs/HANDOFF_QUOTA_CHECKPOINT_2026-10-31.md` §2），未見客戶逐字原文；以客戶原訊息為準。

### DEC-122｜Final UI Contract Freeze：客戶 2026-11-02「vNext Final UI Convergence＋Decision Digest Headless＋OneBrain Integration」指示全文＋裁示 A（先做 docs-only Freeze，不開始 Stage A）；四頁 Final UI Blueprint、Semantic Chip、四態、Single Action Authority、Risk Cap Enforcement 等 Freeze 草案落盤，~~Freeze 內容待客戶拍板；Q1～Q3 PENDING~~ **Freeze 已由客戶拍板；Q1=A／Q2=A／Q3=A**（客戶 2026-11-02）

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S28：客戶 §9 市場 L2／L3、§22 持股 L2（evidence／rule IDs）、§25～§27 Audit 區頁內 Data Freshness／System Information／Digest raw snapshot→MIGRATE；其餘（Slice≠Context、Headless Digest、OneBrain 唯讀 Digest、Single Action Authority 等）維持）** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。
> 📌 **施工路線（原 Stage A～E）由 DEC-123（New UI2 Greenfield Presentation Layer）取代；Freeze semantic contracts 全部保留為 New UI2 的 input**（2026-11-02 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-123）；append-only，本條原文與下方各補註一字未改）：客戶 2026-11-02 裁示 (5)「立即停止目前原本的 Stage A／現有 New UI 延續路線」「後續正式 UI 路線改為 New UI2 Greenfield Presentation Layer」「#996 的定位不變……全部保留。New UI2 必須以這些 semantic contracts 為 input」（逐字見 DEC-123）。**仍有效**：本條 Q1=A／Q2=A／Q3=A、產品方向、架構鏈、6 條永久 invariant、四頁 IA、Mobile-first、Risk Cap boundary、Single Action Authority、Missing semantics、Freshness／Provenance、Decision Digest、OneBrain boundary、Stage F～J（F 與 UI2 先後依 DEC-123 G3′）。**被取代**：「Freeze 驗收 PASS 後開 Stage A-1」與 Stage A～E「在現有 New UI 上施工」的路線（本條狀態欄「下一步＝待客戶切換 Model×Effort 後開 Stage A-1」自 2026-11-02 起失效）。兩邊理由：舊路線沿用已上線的 New UI，改動小、交付快（當時成立）；新路線依客戶明示——持續 patch 現有 New UI 不再是主線，改建全新 Presentation Layer、沿用底層。逐項對映見 DEC-123「與 DEC-122 的關係」與 `docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md`。

> 2026-11-02 補登（ID 取下一個未用號；落盤前 `grep -rn "DEC-122" docs PROJECT_RULES.md` 0 命中，DEC-121 為上一號）。**來源類別 D：客戶 2026-11-02 本輪對話原文，經總管轉交逐字檔；下方 fence 內逐字收錄，未改一字**（撰寫組未見客戶原訊息本身，只見總管轉交之全文；若有出入以原訊息為準）。總管送審題幹（A／B／C）由總管撰寫，**非客戶原文**，另列於 fence 後。

- **決策者**：**客戶**（2026-11-02）。｜**效力日期**：2026-11-02 起。｜**範圍**：產品／UI（四頁 Final UI）＋資料語意呈現（chip、四態、freshness）＋架構（Headless Digest、OneBrain 邊界）＋治理（Stage A–J、回報格式）。｜**狀態**：~~**客戶指示 A 生效；Freeze 內容待客戶拍板（含 Q1～Q3）**——Freeze 三份文件是送客戶拍板的草案，**不是 Approved 規格**；**Q1（Risk Cap 曝險分母／數值啟用／兩頁區間顯示）、Q2（持股動作詞彙）、Q3（📊 市場頁手機第一屏）PENDING**；Stage A 未開始。~~ **Freeze 已由客戶拍板（2026-11-02；Q1=A／Q2=A／Q3=A，逐字見本條末「客戶裁示 Q1～Q3」）~~；Stage A 須待 Freeze 獨立驗收（含必要 QA）PASS 後才能開始**~~ ；Freeze 獨立驗收兩輪已 PASS（2026-11-02；第一輪 PASS with fixes、第二輪 PASS；單組驗收）；下一步＝待客戶切換 Model×Effort（Opus 5.5＋High → Sonnet 5.5＋Medium）後開 Stage A-1（≤3 項）**（2026-11-02 Freeze 獨立驗收第二輪 PASS 後同步；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕；原文刪除線保留）（客戶原文「不得因本裁示直接跳過 Freeze 驗收」）（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留）。
- **正式規格落點**：契約 `docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md`~~（Freeze 草案，待客戶拍板；Q1～Q3 條款標 PENDING）~~ （**客戶拍板版**，Q1～Q3 已裁示）；能力對照 `docs/vnext/FINAL_UI_CAPABILITY_MAP_2026-11-02.md`（85 列，critical 7 列）；取代關係 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md`（S1～S20；~~S10／S11 條件式待 Q3~~ S10／S11 依 Q3=A 改為正式取代）。契約狀態＝**客戶拍板版**（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留）。
- **客戶原文一：主線指示全文（逐字，fence 內未改一字；具約束力）**：

```
任務名稱

vNext Final UI Convergence + Decision Digest Headless + OneBrain Integration

Repository：

"linchen-20200325/my-stock-dashboard"

本提示語只能在：

«Final UI Contract Freeze 已完成、已進 main、GitHub / DECISIONS / BACKLOG / PROJECT_STATE / HANDOFF 同步完成»

之後執行。

如果上述條件未滿足：

停止施工，回到 Final UI Contract Freeze。

---

0. 工作模式

整體採：Silent Autonomous Cruise

主線目標：
1. 四頁 Final UI 收斂
2. UI 與 Decision Context 完全解耦
3. Headless Decision Digest
4. Single Action Authority 落地
5. OneBrain runtime 最後接入
6. Real-data / Mobile acceptance
7. 舊 UI 最終替代確認後才移除

Minimum Sufficient Effort。依工作自動選：
| 任務 | 建議 Model | Effort |
| 純 UI layout / component / chart | Sonnet 5.5 | Medium |
| CSS / responsive / chip / expander | Sonnet 5.5 | Medium |
| 文件同步 | Sonnet 5.5 | Low / Medium |
| Data semantic / Missing / Freshness | Opus 5.5 | High |
| Risk Cap / Action Authority | Opus 5.5 | High |
| Decision Digest architecture | Opus 5.5 | High |
| OneBrain boundary / grounding | Opus 5.5 | High |
| 估值公式／Forward EPS 語意 | Opus 5.5 | High |
不要整個施工期固定使用 Opus。只有真正需要語意／架構推理時才升級。

---

1. 每個 Batch 前都必須重新做 GitHub Verification Gate
至少："origin/main"、Open / Draft PR、active branches、relevant commit / diff、CI / QA、current BACKLOG / DECISIONS / STATE / HANDOFF。
GitHub = SSOT。cron 會推進 main。禁止引用上一輪 SHA 當最新 main。

---

2. 執行總順序（嚴格）
Stage A — Shared Presentation Foundation
↓ Stage B — 市場頁 Final UI
↓ Stage C — 標的頁 Final UI
↓ Stage D — 持股頁 Final UI
↓ Stage E — 我的 / Audit Final UI
↓ Stage F — Headless Decision Digest
↓ Stage G — OneBrain Runtime Integration
↓ Stage H — Cross-page Consistency
↓ Stage I — Real-data / Mobile Acceptance
↓ Stage J — Old UI Supersede / Removal Gate
禁止：«一邊改 UI、一邊提前接 LLM、一邊重構資料層。»

---

3. Batch 大小
每批：最多 3 個安全工作項目。避免一次改：四頁、Digest、Risk Cap、OneBrain 形成超大 PR。每個 Stage 可以拆多個 PR。

---

Stage A — Shared Presentation Foundation
目標：先建立所有四頁共用的 presentation primitives。例如依現有架構調整／擴充：status card、metric card、freshness micro-tag、source tag、missing state、stale state、neutral/info chip、Risk Cap alert、section header、chart container、audit link、mobile stack、expander hierarchy。
不要重寫整套 component library。優先 reuse 現有："src/ui_v2" 及既有 common component。

---

4. Semantic Chip Contract
正式區分：
Positive / Allowed：用於真正正向 deterministic state。
Warning：用於需注意。
Danger：用於 deterministic violation / Risk Cap。
Neutral / Info：用於：類型、產業、計數、估值口徑、資料來源。
禁止拿："guard_chip" 之類的警告元件表示：半導體、3 項、PE、股票。避免語意污染。

---

5. Missing / Stale / Unavailable
全站統一：
Missing → ⬜ 資料未取得 / 資料未備
Stale → 有資料，但已超過 freshness tolerance
Unavailable → 來源目前不可用
Not evaluated → 尚未評估
四者不得混用。
永遠：missing ≠ 0；missing ≠ HOLD；missing ≠ neutral；unavailable ≠ safe；not evaluated ≠ safe

---

Stage B — 📊 市場頁 Final UI
目的：回答：«現在市場環境如何？風險多大？目前可以多積極？»

6. 市場頁 L1
第一屏控制在：市場總結。包含：Regime、Risk Cap、System Action State、OneBrain Outlook、是否需行動。不得塞大量說明。

7. 市場核心指標
用精簡卡片：台股、VIX、US 10Y、利差、DXY、PMI / 景氣、其他已正式存在且重要的指標。
每個卡片：value、short state、as_of、source。不要共用假的全域更新時間。

8. 市場 Charts
主要採：
台股主圖：index、正式趨勢線／均線、Regime annotation
Volatility：VIX、正式 threshold / reference band
International：優先 small multiples：DJI、NASDAQ、SOX、DXY、Yield
Macro：使用 mini chart、sparkline、multi-series 取代大段文字。

9. 市場頁 L2 / L3
L2：為什麼、counter evidence、data freshness、source
L3：raw table、full macro detail、engineering diagnostics
不得重新把舊市場頁數千字搬回 L1。

---

Stage C — 🎯 標的頁 Final UI
目的：兩件事：A. 系統替我找；B. 我指定一檔研究。必須明確切開。

10. 雙模式
頂部：[ 市場精選 ] [ 即時查一檔 ]。不得同時完整展開。

11. 市場精選 Mode
保留：產業機會，以 Top N、bar、score/state、freshness 表示。
候選標的：Top N 只做 presentation。完整 candidate universe 不可丟失。

12. 即時查一檔 Mode
搜尋：股票代碼 / 股票名稱。查詢後進入研究 workspace。自動把市場精選：收合、隱藏、或退到另一個 tab。

13. Ad-hoc Session Isolation
查一檔：Session-only。
不得自動：加入持股、加入觀察、加入 candidate pool、改 strategy、寫 Sheet、改 Risk Cap、改 ranking。
只有：顯式 CTA：加入觀察 才能寫入既有正式 watchlist 流程。
如果該流程尚未正式存在：CTA disabled / not available。不得臨時造寫入邏輯。

14. 單檔 Workspace
建議順序：股票 Header ↓ 6 維 Snapshot ↓ Primary Price Chart ↓ Fundamental ↓ Valuation ↓ Institution / Chip ↓ Industry ↓ Risk ↓ OneBrain Research Explanation

15. 6 維 Snapshot
最多顯示：基本面、估值、籌碼、趨勢、產業、市場環境。每個：state + short text。避免大段 prose。

16. 估值區
正式支援：
Current：PE、PB、existing valuation metrics
Historical：歷史估值區間圖。
Forward：只有資料真的存在才能使用。
Scenario：只有 approved deterministic assumptions 才能呈現。
顯示：EPS basis、EPS source、EPS as_of、PE multiple、PE source / policy、calculation

17. EPS × PE
如果使用：Fair Value = Forward EPS × PE
必須明確：FY2026E、FY2027E、NTM、Forward 1Y
禁止只寫：EPS 45 × PE 24 讓人不知道時間軸。

18. Ad-hoc OneBrain
OneBrain輸出：研究展望、信號一致性、核心理由、最大反證、資料限制
不要：買進 30%、今天加碼、賣出一半
除非 deterministic action contract 正式允許。
Ad-hoc research：不是 portfolio action engine。

---

Stage D — 💼 持股頁 Final UI
這是 Phase 6 最重要頁。
第一屏：必須先看到：Portfolio Risk Cap、目前曝險、System Action State、今日需處理

19. Risk Cap 優先
如果：Exposure > Cap
立即：🔴 Risk Cap 超限 禁止新增曝險
而不是：AI 看多 加碼

20. 今日需處理
只呈現真正 Action：加碼、持有、減碼 1/2、全出
但必須來自正式 deterministic action state。
如果沒有動作：顯示：今日無需調整。不要硬填 action。

21. Portfolio Overview
Charts：portfolio performance、benchmark、sector exposure、strategy distribution、concentration。能圖就不要長表。

22. Holdings Table
L1 只保留重要欄：代碼、名稱、持股比例、成本、現價、報酬、策略、System Action
詳細：fundamental、risk、chip、evidence、rule IDs 放 L2。

23. OneBrain 持股摘要
OneBrain只能：解釋 system actions、指出共同風險、分析 portfolio context、提出反證
若：System Action = 禁止加碼，AI text 也必須遵守。
加入 automated grounding check。

---

Stage E — 👤 我的 / Audit
目標：設定 + 管理 + 追溯

24. 一般設定
保留：Google、Sheet、Portfolio、Watchlist、Strategy、Notifications、Display preference。依既有正式能力。

25. Audit 區
新增正式入口：Decision Digest、Rule Registry、Data Freshness、System Information

26. Rule Registry
唯讀。例如：Rule ID、parameter、current value、version、effective_from、decision/source
不提供：slider、editable text、direct save

27. Decision Digest Viewer
L1：Human-readable。例如：VIX 32.4　R-VIX-02　→ 高波動狀態
L2：raw structured snapshot。
不得顯示：API key、secret、token、OAuth credential

---

Stage F — Headless Decision Digest
此 Stage：Opus 5.5 + High

28. 核心目標
將 Digest 從 UI state 解耦。正式 invariant：Decision Digest must exist without rendering any Streamlit page.

29. 禁止依賴
Digest assembly 不得要求：st.session_state、market page render、holding page render、expander open、chart render、tab selected
UI 是 consumer。不是 data producer。

30. Digest Pipeline
目標：Canonical Services ↓ Canonical Snapshot ↓ Deterministic Rules ↓ Risk Cap ↓ System Action ↓ Decision Digest

31. Digest 必須保存
至少：all relevant raw values、normalized values、missing state、provenance、as_of、freshness、rule result、Risk Cap、System Action、portfolio context、candidates、industries、market state

32. Presentation Slice Independence Test
新增測試：同一份 canonical state：
Scenario A：UI Top 5。
Scenario B：UI Top 10。
Scenario C：section collapsed。
Scenario D：page never rendered。
Digest 必須：semantically equivalent。

---

Stage G — OneBrain Runtime
此 Stage：Opus 5.5 + High
不得在 Headless Digest 合格前開始。

33. OneBrain 唯一輸入
OneBrain production reasoning：只讀 Decision Digest。
不得：UI scraping、session scraping、自己呼叫 source、自己查 Sheet、自己抓 Yahoo、自己改 portfolio

34. Provider Neutral
Domain 不得 hardcode Claude。維持：OneBrain ↓ Provider interface ├ Claude ├ Fake └ future providers
若 Claude API 尚未經 Secret / Cost / Provider Gate：先 Shadow。不要偷偷上 production paid call。

35. Structured Output
OneBrain output 至少：summary、outlook、signal_consistency、reasons[]、counter_evidence[]、limitations[]、evidence_refs[]
如有 action explanation：system_action_ref
AI 不產生 independent action。

36. Grounding Gate
所有 OneBrain output：必須通過：grounding check
至少檢查：evidence refs 存在、不引用不存在數值、不創造 Rule ID、不違反 Risk Cap、不產生禁用 action、不產生偽 probability
Failure：fallback deterministic summary

37. Cache / Cost
只對相同 semantic fingerprint cache。Digest 變更：重新計算。
禁止因：tab switch、rerender、mobile layout、expander 重複付費呼叫。
Paid call 原則：explicit refresh / new canonical state，不是 navigation。

---

Stage H — Cross-page Consistency
必須驗：市場／標的／持股：使用：同一份 market context。
不得：市場頁 = Risk-off、標的頁 = Risk-on、持股頁 = Neutral，除非：有明確不同 as_of。

38. Action Consistency
同一 Snapshot：Risk Cap blocked 則：市場、標的、持股、OneBrain：不得任何地方出現 unrestricted Add。

39. Terminology Consistency
全站統一：Regime、Risk Cap、Missing、Freshness、System Action、OneBrain、Strategy、Valuation。禁止每頁各叫不同名字。

---

Stage I — Real-data / Mobile Acceptance
此階段不能只靠 fixture。必須包含：
Desktop：真資料驗證。
Mobile：真機／正式 viewport。
Cold Start：沒有 cache。
Partial Data：某來源 missing。
Stale：某來源過期。
API Failure：來源失敗。
AI Failure：provider fail。
系統仍必須安全顯示 deterministic output。

40. Mobile 第一屏 Acceptance
市場 不用滑：市場狀態、Risk Cap、是否行動、refresh
標的 不用滑：mode、search、查詢摘要
持股 不用滑：portfolio status、Risk Cap、是否需要處理
我的 不用滑：connection state、primary management actions

41. Visual Fidelity Gate
保留既有 gate。但新增：
Decision Density：禁止第一屏重新被：20 張 cards、大表、工程文字、raw JSON 塞滿。
Text Reduction：重要頁：結論 → 圖 → 細節；不是：說明 → 說明 → 說明 → 圖。

---

Stage J — 舊 UI Removal Gate
舊 UI 現階段不得提前刪。
只有：1. 四頁能力 coverage 完成 2. mobile acceptance 3. real data acceptance 4. audit coverage 5. user final acceptance 6. old/new capability map 無 critical gap
才能提出：Old UI Removal Decision Gate

42. 不得靜默移除的舊能力
尤其重新盤點：大盤判斷、台股趨勢、國際趨勢、EPS × PE 研究、macro、industry、chip、valuation、risk、portfolio、candidate、source audit
新 UI 看起來簡潔：不代表功能消失。

43. EPS × PE 大盤模型
注意：大盤 EPS × PE 與單一股票估值是兩個 contract。不要混在一起。
大盤：Market EPS × Reasonable Market PE → index scenario / range
個股：Company EPS × Company valuation multiple → company valuation
兩者：source、horizon、methodology、threshold 都分開治理。
若大盤模型仍在 Research Gate：保持 Research。不得為 UI 順便 productionize。

44. QA 原則
UI batch：targeted tests。Data semantic / Digest / Risk Cap：full relevant QA。真正 Risk Cap / action invariant：High Effort + full QA。

45. 每批 PR 驗收
至少回答：What changed? What did NOT change? Which contract? What tests? Any semantic change? Any missing capability?
如果只是 UI：必須明示：No investment semantic change.

46. Auto-Ship
只有符合既有 Safe Auto-Ship 規則才可：commit、push、PR、QA、merge
若出現：new investment semantics、new threshold、Risk Cap modification、source change、irreversible migration、ambiguity → 停止在 Decision Gate。

47. Hard Output Gate
執行中保持 SILENT。不得回報：開始 Stage B、正在修改、測試通過、CI 還在跑、已開 PR、等待 merge、下一步...
只有：🔴 客戶裁示、🟡 Model / Effort change、🟡 Manual action、🟢 完整 Stage 完成、🟡 Safe Handoff required 才輸出。

48. Stage 完成回報
格式：🟢 Stage X 完成
| 項目 | 結果 | main SHA | PR # | Stage X | Production behavior changed / unchanged | Semantic change yes / no | QA pass | Visual Gate pass / accepted deviation | Mobile status | Remaining blocker none / xxx | Next handoff xxx |
不要施工日誌。

49. Safe Handoff
若 context 開始變長：不要硬撐。在 Safe Checkpoint：worktree clean、PR known state、CI known、governance docs sync、PROJECT_STATE、HANDOFF、SESSION_LOG、BACKLOG、DECISIONS 依 repo 規則保存。然後：🟡 建議切換新對話，並提供唯一接手點。

50. 最終完成定義
整個 vNext Final UI / OneBrain mainline 完成，至少必須：
市場：clean chart-first、Regime、Risk Cap、provenance、OneBrain outlook
標的：精選／Ad-hoc dual mode、single-stock research、valuation、freshness、no auto-write
持股：Single Action Authority、Risk Cap enforcement、clear actions、portfolio risk
我的：connection/settings、Digest audit、Rule registry
Architecture：Headless Digest、Presentation Slice ≠ Decision Context、OneBrain only consumes Digest、grounding、deterministic fallback
UX：Desktop accepted、Mobile accepted、real data accepted、missing/stale accepted
Governance：no hidden capability loss、old/new map complete、SSOT synchronized

51. 最重要的三條 invariant
整個施工期間永遠不可破：
1. UI 越簡潔，Decision Context 不能越少。
2. Deterministic System 是唯一動作權威；OneBrain 只能推理、解釋與反證。
3. Presentation Slice ≠ Decision Context ≠ AI Output。

52. 現在的唯一任務
若 Final UI Contract Freeze 已正式完成：先重新做 GitHub Verification Gate。然後只啟動：«Stage A — Shared Presentation Foundation»
一次最多 3 個安全項目。不要一次開始 Stage B～G。完成整個 Stage A 才回報。
```

- **客戶原文二：對總管 Decision Gate「Final UI Contract Freeze 尚不存在 → A／B／C」的裁示（逐字，fence 內未改一字；具約束力）**：

```
A。

先執行 Final UI Contract Freeze，僅做 docs-only，不開始 Stage A production implementation。

請把本輪新增方向正式整理成可追溯規格，至少包含：

- 四頁 Final UI Blueprint（市場／標的／持股／我的）
- 標的頁「市場精選／即時查一檔」雙模式
- Semantic Chip Contract
- Missing／Stale／Unavailable／Not evaluated 四態契約
- Single Action Authority
- No Uncalibrated Probability
- Risk Cap Enforcement
- Field-level Freshness / Provenance
- 單檔 Valuation Contract
- 大盤 EPS×PE 與單檔估值分離治理
- Decision Digest Viewer / 唯讀 Rule Registry
- Presentation Slice ≠ Decision Context
- Headless Decision Digest prerequisite
- OneBrain 僅解釋／反證，不產生第二套動作
- Desktop / Mobile L1 Blueprint
- Old UI Capability → New UI Location Map
- 與 DEC-107、DEC-121 及其他現行 DEC 的 Conflict / Supersede Map

重要：

1. 不要直接刪除或覆蓋舊 DEC；要明確記錄哪些內容被 supersede、哪些繼續有效。
2. 所有正式決策、未完成項目、目前狀態與 handoff 必須同步進 GitHub SSOT，至少涵蓋 DECISIONS／BACKLOG／PROJECT_STATE／HANDOFF 及 repo 現行要求的 session 紀錄。
3. 沒寫入 GitHub 的新規格，不視為正式完成。
4. 不修改 production UI、資料層、公式、Risk Cap、OneBrain runtime。
5. 若 Contract Freeze 中仍有真正需要我選擇的投資語意／門檻／版面衝突，再集中成最多 2–3 題 Decision Gate 給我，不要邊做邊問。
6. 完成並經裁示後，才能開始 Stage A。

建議模型：Claude Opus 5.5
Effort：High

過程維持 Silent Autonomous Cruise；只有真正需要我裁示，或整個 Freeze Stage 完成時才回報。
```

- **總管送審題幹（非客戶原文；供上下文）**：A（推薦）先做 Final UI Contract Freeze（docs-only）：四頁線框、Chip 契約、四態契約、與現行 DEC 的 supersede 表，送客戶拍板後才開工 Stage A；B 只凍結 Chip＋四態為新 DEC，Stage A 先開工，四頁版面稍後凍結；C 視本提示為 Freeze，直接開工 Stage A。**客戶選 A。**
- **裁示整理（撰寫組依原文歸納；與原文有出入以原文為準）**：
  1. **本輪只做 Final UI Contract Freeze（docs-only）**；⛔ Stage A production implementation；⛔ 修改 production UI、資料層、公式、Risk Cap、OneBrain runtime（原文二第 4 點）。
  2. 主線指示（原文一）的前置條件「Final UI Contract Freeze 已完成、已進 main、GitHub／DECISIONS／BACKLOG／PROJECT_STATE／HANDOFF 同步完成」**尚未滿足**；**本 DEC 所屬 PR 合併＋客戶拍板 Freeze＋裁示 Q1～Q3 後**，才能依原文一 §52 只啟動 Stage A（原文二第 6 點）。
  3. Freeze 必須涵蓋原文二列舉的 17 項（四頁 Blueprint、雙模式、Semantic Chip、四態、Single Action Authority、No Uncalibrated Probability、Risk Cap Enforcement、Field-level Freshness／Provenance、單檔 Valuation、大盤 EPS×PE 分離、Digest Viewer／唯讀 Rule Registry、Presentation Slice ≠ Decision Context、Headless Digest prerequisite、OneBrain 僅解釋／反證、Desktop／Mobile L1 Blueprint、Old→New Capability Map、Conflict／Supersede Map）→ 對照見契約 §0 表。
  4. **舊 DEC 不刪不覆蓋**：被 supersede 的只在原處加 📌，並寫明仍有效部分（原文二第 1 點）→ supersede map。
  5. **沒寫入 GitHub 的新規格不算正式完成**（原文二第 3 點）。
  6. 真正需要客戶選的投資語意／門檻／版面衝突集中成 ≤2～3 題（原文二第 5 點）→ **本輪送 3 題（Q1、Q2、Q3）**；OneBrain 詞彙值域（延後 Stage G Gate）、新版加入觀察是否啟用（延後 ME-P2／HI-5 Gate）不送題（理由見契約 §20 判題原則）。~~本輪送 2 題（Q1、Q2）；市場頁手機主要風險位置不送題~~（2026-11-02 同批獨立稽核後更正，有意識的更新，不是漏刪；決策者 AI 總管〔稽核補正〕：DEC-118 問題 1=A 為客戶知情選擇，與客戶 §40 相反，屬客戶裁示互撞，須送題）。
  7. **三條 invariant**（原文一 §51）自本 DEC 起為整個 Final UI 主線的最高施工約束（契約 §1）。
- **Supersede 摘要**（逐條「被取代部分／仍有效部分／依據」見 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1；**已加 📌**＝DEC-051（兩則）、DEC-053、DEC-054、DEC-117、DEC-060、DEC-083、DEC-089、DEC-099、DEC-107、DEC-109（兩則）、DEC-110、DEC-115、DEC-118、DEC-120、DEC-121、Presentation Contract §6／§8、Visual Fidelity Gate V 表後與 §8 例外表後、Digest 契約 §4、ONEBRAIN Arch §11、Brain 邊界 §3、BACKLOG `P5-CHIP-KIND-NAMES`；**未加 📌（只在 map 登記，原檔不改）**＝S13 Phase 5 線框、S18 d25 HTML、S19 MODEL_EFFORT_POLICY、DEC-074／075（字樣保留）、~~DEC-081／092／053／054／117（條件式或仍有效）~~ DEC-081／092（仍有效）；DEC-053／054／117 已於 2026-11-02 加 📌）：S1 DEC-107 1A 整頁順序→雙模式；S2 DEC-121 Q2「整頁順序不變」一句；S3 DEC-099 第 3 點終態讀法；S4 Presentation §6 R8-2／§8-3／Gate V8「🔴 只給系統真錯誤」→ 加確定性違規；S5 DEC-115 D3 末句（第四套視覺語言）；S6 `P5-CHIP-KIND-NAMES`「或維持」；S7 Presentation §6 `unavailable` 列語意；S8 D-3(a) L1 外露字樣；S9 Brain 邊界 §3（超限→禁止新增曝險一條）；S10 DEC-118 問題 1（手機 ⚡；~~**條件式待 Q3**~~ **Q3=A 正式取代，並含 DEC-117 Q1 手機 2＋1**）；S11 DEC-120 A10／A11（~~**條件式待 Q3**~~ **Q3=A 正式取代**）（2026-11-02 裁示後更新，有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留）；S12 DEC-089 G6 L1 欄位集；S13 Phase 5 線框單檔順序；S14 Digest 契約 §4「市場事實不帶 rule」；S15 ONEBRAIN Arch §11 schema；S16 DEC-109 三十一 Phase 編號 → Stage A–J；S17 DEC-060（只限 Stage 完成回報）；S18 d25 `target.html`／`holdings.html`；S19 MODEL_EFFORT_POLICY Rule 2（本主線）；S20 DEC-109 十一／十三／二十一 與客戶 §6／§19～§20／§35 的對映~~（十一、二十一不取代；十三「加／留／換／減」條件式待 Q2）~~ （十一、二十一不取代；十三「加／留／換／減」依 Q2=A 只作呈現分組）。~~**條件式（未取代）**：DEC-081 Q2-2／RC-VISIBILITY、DEC-051／PQ-C6-3（待 Q1）、DEC-092 Q4／DEC-053／DEC-054 動作名稱（待 Q2）、~~ **裁示前登記的待裁示項（皆已裁示）**：~~DEC-118 問題 1／DEC-120 A10／A11／DEC-117 Q1 手機 2＋1（待 Q3）~~。**裁示後**：Q1 相關＝維持（DEC-051／PQ-C6-3 區間維持；DEC-081 Q2-2 市場頁隱藏，數值另開 Gate）；Q2 相關＝繼續有效（DEC-053／054 加 📌）；Q3 相關＝正式取代（S10／S11）（2026-11-02 裁示後更新，有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留）。**仍有效、取聯集或字樣保留**：DEC-083 E 段 Removal Gate ∪ Stage J 六條件；DEC-074／075「⬜ 未評估／資料不足」保留~~為 Not evaluated 子原因~~字樣（📌 DEC-124：語意歸類改為 Unable to Determine，字樣不改（2026-11-02 Semantic Correction Gate 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-124）；原文刪除線保留））；DEC-110 R8 十態不另造；DEC-044／048／051 有效上限判定。
- ~~**PENDING 題（Customer Decision Gate；全文含理由見契約 §20）**~~ **已裁示題（Q1=A／Q2=A／Q3=A，客戶 2026-11-02；下列為送題當時的題文，保留作歷史；裁示要點見本條末）**（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留）：
  - **Q1｜Risk Cap 閘門**：「目前曝險」分母（持股資料目前無現金／總資產）、數值啟用時點（`RC-VISIBILITY` 仍未核准）、兩頁區間顯示（持股頁卡⑤依 DEC-051／PQ-C6-3〔客戶 2026-10-16 核准〕已外露建議持股區間 `range_text`、市場頁隱藏——請客戶一併決定是否保留）。**A（總管推薦）**：Freeze 只定規則形狀；目前曝險或有效上限任一不可得 → `⬜ 無法判定`，且加碼不得被當作無上限；數值啟用另開 RC Gate；兩頁區間維持現狀。**B**：現在就定分母＝持股市值合計（不含現金）並啟用超限判定。**C**：先補現金／總資產輸入再啟用（新增 Sheet 現金欄，或由 👤 我的 輸入總資產／現金；舊 UI 有 session 版總資金輸入可參考〔FACT，2026-11-02 grep：`src/ui/tabs/stock_sections/section_when_buy_sell.py` 的 `render_when_buy_sell_section` 內 `st.number_input`「💰 你的總資金（元）— 填了才會算『建議買幾張 + 真 ATR 停損』」，session key `_pos_capital`、跨股共用，供 `calculate_position_size` 算建議張數；只存 session、不寫 Sheet〕）。**裁示前暫行＝A 的較嚴讀法**（維持現狀：持股頁保留已核准區間、市場頁維持隱藏；⛔ 新增 Risk Cap 百分比顯示面；⛔ 改 Risk Cap 公式／門檻）。
  - **Q2｜持股動作詞彙**：客戶要的「加碼／持有／減碼 1/2／全出」 vs 現有 `action_branch` 七分支＋`swap_level`。**A（總管推薦）**：沿用既有分支原名對應顯示，無動作顯示「今日無需調整」，「減碼 1/2／全出」在走完 DEC-053 驗證回測前不產生。**B**：建立五詞彙對映表（既有分支→五詞，無對應者不顯示）。**C**：另開投資規則研究批。題文另說明 `swap_level` 🔴 換出、強制停利／分批停利、暫停加碼的呈現方式，以及 DEC-109 十三「加／留／換／減」與五詞的關係（A 以「加／留／換／減」分組顯示既有分支原名；分組為總管提案，待客戶裁示）。**裁示前暫行＝A 的較嚴讀法**。
  - **Q3｜📊 市場頁手機第一屏**：客戶 §40「不用滑：市場狀態、Risk Cap、是否行動、refresh」 vs DEC-118 問題 1=A（客戶 2026-10-30 看過「手機第一屏一定看得到是否需行動」選項後知情選 A，⚡ 放第一屏緊接之後；總管轉述）；且需改 DEC-117 Q1 手機 2＋1。**A（總管推薦）**：照 §40——「是否行動」進手機第一屏、今日主要風險卡緊接第一屏之後，正式改 DEC-117 Q1 手機排法與 DEC-118 問題 1（DEC-120 A10／A11 隨之重量）。**B**：維持 DEC-118 問題 1=A，§40 在市場頁改讀為「緊接第一屏」。**裁示前**：DEC-118 問題 1=A、DEC-117 Q1、DEC-120 照舊。
- **效力邊界**：docs-only；`src/`、`tests/`、`shared/`、`app.py`、`requirements.txt`、`tools/` 0 diff；不核准任何新資料源（含 Forward EPS）、schema、公式、門檻、投資語意、Risk Cap 顯示、rule id；HI-1～HI-6 狀態不變；舊 UI Removal Gate 不變（Stage J 六條件為加嚴）；~~本 DEC 不構成 Stage A 動工授權，直到客戶拍板 Freeze＋裁示 Q1～Q3。~~ 本 DEC 不構成 Stage A 動工授權，直到 **Freeze 獨立驗收（含必要 QA）PASS**（客戶已於 2026-11-02 拍板並裁示 Q1～Q3）（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留）。
- **與其他 DEC 的關係**：重申並升級 DEC-109 十五～十七（三條 invariant）；承 DEC-104（Hard Output Gate，原文一 §47 一字對齊）、DEC-084／DEC-106（Model×Effort）、DEC-118（GitHub Verification Gate 以當下 `origin/main` 為準）、DEC-019／020（舊 UI 不得提前刪）；落實 `PROJECT_RULES.md` 第 26 節 Durable Memory（原文二第 2、3 點）；`CLAUDE.md` v3 §03-2 ①（版面草稿先行）仍適用各頁 Stage 開工。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：整理、supersede 判讀、~~PENDING 題擬題~~ 送題擬題為撰寫組單組產出（底稿＝兩份單組調查 invA／invB），**未經第二組驗證**；~~「取代判讀只有 S1～S20 與條件式各項」~~ 「取代判讀只有 S1～S20 與 supersede map §2 各項」為單組結論（已經一輪獨立稽核補正），仍只能當待驗事項（BACKLOG `FUI-FREEZE-SECOND-AUDIT`）。
- **客戶裁示 Q1～Q3（2026-11-02；逐字，fence 內未改一字；具約束力）**（2026-11-02 追加；來源類別 D：客戶本輪對話原文，經總管轉交逐字檔 `customer_directive_2026-11-02.md` 第 (4) 段；撰寫組未見客戶原訊息本身，若有出入以原訊息為準）：

```
Q1：A
Q2：A
Q3：A

依此正式完成 Final UI Contract Freeze。

補充永久要求：

1. Q1 採 A

- 本次只凍結 Risk Cap 的規則形狀。
- 超限時必須「禁止新增曝險」。
- 目前曝險或有效 Risk Cap 任一資料不足時，一律顯示「⬜ 無法判定」。
- unavailable / not evaluated 不得解讀成 safe，也不得因此允許加碼。
- 不得自行發明曝險分母、現金、總資產或任何替代值。
- Risk Cap 數值正式啟用、曝險分母與現金／總資產來源另開正式 Decision Gate。
- 持股頁既有已核准的建議持股區間先維持，不因本次 Freeze 擅自修改。

2. Q2 採 A

- 第一版沿用現有 deterministic rule 的正式分支與原名稱。
- UI 可依「加／留／換／減」整理呈現，但不得藉分類創造新的投資語意。
- 沒有需要處理的正式動作時才可顯示「今日無需調整」。
- 資料不足／未評估不得算成「今日無需調整」。
- 「減碼 1/2」「全出」目前不得自行映射或產生。
- 未來只有在正式規則、驗證、必要回測／Shadow 與 Decision Gate 完成後才能啟用這類比例 Action。

3. Q3 採 A

- 市場頁 Mobile-first。
- 手機第一屏必須不用滑就看到：
  - 市場目前狀態
  - Risk Cap
  - 是否需要行動
  - 主 Update CTA
- 「今日主要風險」緊接第一屏之後，仍屬 L1，不得被 L2／L3 插隊。
- 正式 supersede 與此衝突的 DEC-117／DEC-118／相關 DEC-120 mobile exception，必須在 Conflict / Supersede Map 明確落盤，不得只靠聊天解讀。

產品方向再次確認並寫入正式契約：

「簡化 UI，但不簡化 Decision Context。」

前台只呈現真正需要決策的資訊；完整資料不得因 UI 精簡而裁掉。

正式架構維持：

Canonical Data
→ Deterministic Rules / Formulas
→ Risk Cap / Hard Constraints
→ System Action State
→ Decision Digest
→ OneBrain
→ UI

永久 invariant：

- UI 越簡潔，Decision Context 不能越少。
- Presentation Slice ≠ Decision Context ≠ AI Output。
- System Action State 是唯一正式動作權威。
- OneBrain 只負責 reasoning、summary、explanation、counter-evidence、limitations。
- OneBrain 不得創造第二套 portfolio action，不得覆寫 deterministic action，不得繞過 Risk Cap。
- OneBrain 應讀完整 Decision Digest，而不是只讀 UI 顯示的 Top-N／摘要資料。

請完成本次 Freeze 收斂與 GitHub 持久化，至少同步：

- Final UI Contract
- Conflict / Supersede Map
- Capability Map
- docs/DECISIONS.md
- docs/BACKLOG.md
- docs/PROJECT_STATE.md
- docs/HANDOFF.md
- repo 現行 session log

完成 Freeze 的獨立驗收與必要 QA 後，才可判斷是否進 Stage A；不得因本裁示直接跳過 Freeze 驗收。

工作模式維持 Silent Autonomous Cruise：

- 每批 ≤3 個安全工作項目。
- 過程保持 SILENT。
- CI running、CI green、QA running、commit、push、PR ready、merge ready、retry、agent activity 都不要回報。
- 只有真正需要客戶裁示、人工操作、Model/Effort change、Safe Handoff，或完整 Stage 完成時才輸出。

另外，若執行途中判斷目前 Model 或 Effort 不足、需要切換模型或提高／降低理解力：
「必須立即停下來通知我，說明建議的新 Model + Effort 與原因，等我修改後才能繼續。」
不得自行切換後繼續施工。

本輪建議執行設定：
Model：Opus 5.5
Effort：High

開始前仍須重新做 GitHub Verification Gate，以當下 origin/main、Open/Draft PR、CI/QA、formal docs 為準；不得引用舊 SHA 當最新狀態。
```

- **裁示要點（撰寫組依上方原文歸納；與原文有出入以原文為準；條文化落點＝契約 §0.1）**：
  - **Freeze 拍板**：「依此正式完成 Final UI Contract Freeze」→ 契約、supersede map、capability map 由「待客戶拍板」改為**客戶拍板版**；**Stage A 須待 Freeze 獨立驗收與必要 QA 後**才判斷能否開始（「不得因本裁示直接跳過 Freeze 驗收」）。
  - **Q1=A（Risk Cap）**：只凍結規則形狀；超限＝禁止新增曝險；目前曝險或有效 Risk Cap 任一資料不足 → `⬜ 無法判定`；unavailable／not evaluated ≠ safe、不得因此允許加碼；⛔ 自行發明曝險分母、現金、總資產或任何替代值；數值正式啟用、曝險分母、現金／總資產來源**另開正式 Decision Gate**（BACKLOG `FUI-RC-NUMERIC-GATE`）；持股頁既有已核准的建議持股區間（DEC-051／PQ-C6-3）**維持**。
  - **Q2=A（動作詞彙）**：第一版沿用現有 deterministic rule 正式分支與原名稱；「加／留／換／減」只作呈現分組，⛔ 藉分類創造新投資語意；只有沒有需處理的正式動作時才顯示「今日無需調整」；資料不足／未評估 ⛔ 算成「今日無需調整」；「減碼 1/2」「全出」⛔ 自行映射或產生；比例 Action 須正式規則＋驗證＋必要回測／Shadow＋Decision Gate 後才可啟用（BACKLOG `FUI-PROPORTIONAL-ACTION-RULES`）。
  - **Q3=A（市場頁手機）**：市場頁 Mobile-first；手機第一屏不用滑看到市場目前狀態、Risk Cap、是否需要行動、主 Update CTA；「今日主要風險」緊接第一屏之後、仍屬 L1、⛔ 被 L2／L3 插隊；**正式 supersede** DEC-117 Q1 手機 2＋1、DEC-118 問題 1=A、相關 DEC-120 mobile exception（A10／A11），落點＝supersede map S10／S11（原 📌 已改為正式取代，舊文字刪除線保留）。
  - **產品方向（再次確認、寫入正式契約）**：「簡化 UI，但不簡化 Decision Context。」前台只呈現真正需要決策的資訊；完整資料不得因 UI 精簡而裁掉。
  - **正式架構**：Canonical Data → Deterministic Rules／Formulas → Risk Cap／Hard Constraints → System Action State → Decision Digest → OneBrain → UI。
  - **永久 invariant（6 條，擴充原三條）**：UI 越簡潔，Decision Context 不能越少；Presentation Slice ≠ Decision Context ≠ AI Output；System Action State 是唯一正式動作權威；OneBrain 只負責 reasoning、summary、explanation、counter-evidence、limitations；OneBrain 不得創造第二套 portfolio action、不得覆寫 deterministic action、不得繞過 Risk Cap；OneBrain 應讀完整 Decision Digest，而不是只讀 UI 顯示的 Top-N／摘要資料。
  - **工作模式**：Silent Autonomous Cruise；每批 ≤3 項；只在客戶裁示、人工操作、Model／Effort change、Safe Handoff、完整 Stage 完成時輸出；判斷 Model／Effort 不足或需切換 → **立即停下通知客戶、等客戶修改後才能繼續，不得自行切換後繼續施工**；本輪建議 Opus 5.5＋High；開始前重做 GitHub Verification Gate。
- **Session 紀錄落點（F6）**：repo **沒有** `SESSION_LOG` 檔；依 `docs/governance/SESSION_CONTINUITY_RULES_2026-10-31.md` C1，session 紀錄（durable checkpoint）落在 `docs/HANDOFF.md` 的「Safe Handoff」區塊（`PROJECT_RULES.md` 第 20 節 Resume Checkpoint 同處）。根目錄 `STATE.md` 現為 cron 自動更新，**不作 session log**。
- **效力邊界（裁示後）**：仍為 docs-only 收斂；⛔ 改 production UI、資料層、公式、Risk Cap 數值、OneBrain runtime；Q1～Q3 裁示不核准任何新資料源、曝險分母、比例 Action、rule id。
- ⚠️ 揭露（裁示後收斂批）：條文化與 supersede 改判為撰寫組單組產出，待 Freeze 獨立驗收（BACKLOG `FUI-FREEZE-SECOND-AUDIT`）。

### DEC-123｜New UI2 Greenfield Presentation Layer：客戶 2026-11-02 裁示——立即停止原 Stage A／現有 New UI 延續路線，後續正式 UI 路線改為 New UI2（全新 Presentation Layer、沿用成熟底層）；本批只做 Architecture Gate（docs-only）；送客戶四題（G1／G3′／四頁線框／G2＋#996 合併確認）~~**PENDING**~~ **已裁示（Q1～Q4＋#996，客戶 2026-11-02）**（客戶 2026-11-02）

> 📌 **SUPERSEDED IN PART BY DEC-128（範圍：S41：A-3「mobile stack＋expander 層級（L1／L2／L3 摺疊層級）」；僅限 New UI2）** — 歷史證據保留、原文一字未改；現行讀法見 `docs/DECISIONS.md` DEC-128 與 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（2026-11-03 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）；其餘條文仍有效）。

> 2026-11-02 補登（ID 取下一個未用號；落盤前 `grep -rn "DEC-123" docs PROJECT_RULES.md` 0 命中，DEC-122 為上一號）。**來源類別 D：客戶 2026-11-02 本輪對話原文，經總管轉交逐字檔（`customer_directive_2026-11-02.md` 第 (5) 段）；下方 fence 內逐字收錄，未改一字**（撰寫組未見客戶原訊息本身，只見總管轉交之全文；若有出入以原訊息為準）。

- **決策者**：**客戶**（2026-11-02）。｜**效力日期**：2026-11-02 起。｜**範圍**：產品／UI 路線（Presentation Layer 重建）＋架構（View Model／Presentation Contract、consumer 邊界）＋治理（Architecture Gate、Model×Effort Change Gate、Silent Autonomous Cruise）。
- **狀態**：**客戶裁示生效**（停止原 Stage A／現有 New UI 延續路線；正式 UI 路線改為 New UI2）；**Architecture Gate 已由客戶裁示 Q1～Q4（2026-11-02，逐字見本條末「客戶裁示 Q1～Q4」）**——Q1=A（獨立 Streamlit Cloud Preview＋成本控制）、Q2=A 但修正分類（System Action Aggregator 屬新 runtime component，只凍結契約、⛔ 實作）、Q3 四頁線框核准（W-4／W-5=A／W-9／W-10／W-11 條件）、Q4=A（Cutover 鏈）；**#996 已合併**（main＝`acd1648c`）；本 Gate 已落盤為 commit `6d30dcea`、Draft PR #997；~~**待 #997 獨立稽核＋合併後凍結**，之後發 🟡 Model／Effort Change Gate 並停手~~ #997 獨立稽核兩輪完成（第一輪 PASS with fixes → 第二輪 PASS）；**#997 合併即凍結**（merge SHA 由下一位補記）（2026-11-02 #997 獨立稽核第二輪 PASS 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕；原文刪除線保留）；凍結後**下一個唯一安全工作**＝發 🟡 Model／Effort Change Gate，**客戶切換 Model×Effort 至 Sonnet 5.5＋Medium** 後，經 **implementation Gate** 開第一個 New UI2 批次（建議先 `NUI2-GUARD-REGISTRATION`／View Model boundary（`NUI2-VM-BOUNDARY`）／Preview 入口骨架（`NUI2-PREVIEW`），≤3 項，fake／snapshot 資料）；**未經客戶切換與 Gate 不得開始 implementation**；System Action Aggregator 實作另需 implementation Gate（`NUI2-AGGREGATOR-IMPL`）；⛔ production coding。（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）<br>原文：~~**客戶裁示生效**（停止原 Stage A／現有 New UI 延續路線；正式 UI 路線改為 New UI2）；**New UI2 Architecture Gate＝草案，待客戶裁示**——送客戶四題 **G1（Preview 方式）、G3′（System Action Aggregator（系統動作彙整層））、四頁線框核准（W-4、W-5 含計入範圍、W-9、W-10 ⚡ N 來源、W-11 持股桌機）、G2（Cutover＋#996 可否現在合併）PENDING**；⛔ production coding。⚠️ 三份 Gate 文件目前**只存在工作樹**（受「只能推指定分支」權限限制；#996 合併後以新 PR 落盤），落盤前依 DEC-122「沒寫入 GitHub 的新規格，不視為正式完成」**尚非正式文件**。2026-11-02 獨立稽核（單組）判 PASS with fixes，文件已依修正項改寫。~~
- **正式規格落點**：`docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md`（Architecture Proposal、VM／Migration 邊界、目錄、Preview／Cutover、Testing、Consumer 邊界、Gate 題、governance 清單）；`docs/vnext/NEWUI2_REUSE_MATRIX_2026-11-02.md`（88 列、六類）；`docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md`（四頁、手機 390×844 先、桌機 1440×900 後）。三份皆**草案、待客戶裁示／核准**。 📌 裁示整合批新增：`docs/vnext/NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md`、`docs/vnext/NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md`、`PROJECT_RULES.md` 第 27 節（永久收尾 Gate）；三份草案狀態改為客戶核准（待 #997 稽核＋合併後凍結）（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）。
- **客戶原文：New UI2 Greenfield Presentation Layer 裁示全文（逐字，fence 內未改一字；具約束力）**：

```
立即停止目前原本的 Stage A / 現有 New UI 延續路線。

新的客戶裁示如下：

「後續正式 UI 路線改為 New UI2 Greenfield Presentation Layer。」

現在開始，不再以「持續 patch 現有 New UI」作為主要 production 路線。

但這不是整套系統重寫。

---

1. 先停手

目前 #996 維持現狀。

禁止：

- 開始原 Stage A
- 修改 production UI
- 擴大 #996 範圍
- 因為改走 New UI2 就丟棄 #996
- 刪除現有 New UI
- 刪除 Old UI
- 新增 Risk Cap runtime
- 新增 OneBrain runtime
- 重寫既有 data / services / rules

目前 CI 可以自然跑完，但不要因 CI 綠燈就自行開始舊 Stage A。

---

2. #996 的定位不變

#996 仍是 Final UI Contract Freeze 的重要正式輸入。

其中已確定的：

- Q1=A
- Q2=A
- Q3=A
- 簡化 UI，但不簡化 Decision Context
- Risk Cap boundary
- Single Action Authority
- Missing semantics
- Freshness / Provenance
- Presentation Slice ≠ Decision Context ≠ AI Output
- Decision Digest
- OneBrain boundary
- Mobile-first
- 四頁 IA

全部保留。

New UI2 必須以這些 semantic contracts 為 input。

不要因為 New UI2 而重新發明投資語意。

---

3. 新正式方向

建立：

New UI2 Greenfield Presentation Architecture

定位：

「全新的 Presentation Layer，但沿用成熟的底層資料與投資邏輯。」

目標架構：

Canonical Data / Sources
↓
Normalization / Validation
↓
Deterministic Rules / Formulas
↓
Risk Cap / Hard Constraints
↓
System Action State
↓
View Model / Presentation Contract
↓
New UI2

未來：

System Action State
↓
Decision Digest
↓
OneBrain

New UI2 與 LINE 都是 consumer。

---

4. 三代 UI 邊界

Old UI：
只讀 Logic / Capability Reference。
禁止修改。

現有 New UI：
改為 Legacy New UI / Reuse Candidate。
停止把持續 patch 當正式主線。

New UI2：
未來唯一主要 Presentation Layer。

---

5. 本批只做 Architecture Gate

本批禁止 production coding。

只做：

1. New UI2 Architecture Proposal
2. Reuse Matrix
3. 四頁 textual wireframe
4. View Model boundary
5. Migration boundary
6. proposed directory structure
7. Preview strategy
8. Cutover strategy
9. Testing strategy
10. UI / LINE / Decision Digest / OneBrain consumer boundary
11. 真正需要客戶裁示的 Decision Gates
12. 必要 GitHub governance docs 同步

---

6. Reuse 原則

必須實查 repo 後分類：

KEEP AS-IS
WRAP
PORT
REIMPLEMENT
RETIRE LATER
DO NOT TOUCH

優先保留：

- canonical data
- services
- source adapters
- deterministic rules
- valuation logic
- Risk Cap logic
- freshness / provenance
- validated domain tests
- pure helpers

New UI2 主要重做：

- shell
- navigation
- card system
- layout
- chart container
- responsive
- status presentation
- source / freshness presentation
- empty / stale / unavailable states
- OneBrain summary container
- audit presentation

---

7. 四頁 IA 固定

只維持：

1. 📊 市場
2. 🎯 標的
3. 💼 持股
4. 👤 我的

禁止新增第五個主要頁面。

---

8. 永久產品方向

核心原則：

「簡化 UI，但不簡化 Decision Context。」

UI 可以少顯示。

底層資料不能因 UI 精簡而減少。

永久 invariant：

- UI 越簡潔，Decision Context 不能越少
- Presentation Slice ≠ Decision Context ≠ AI Output
- System Action State 是唯一正式動作權威
- OneBrain 只負責 reasoning / summary / explanation
- OneBrain 不得覆寫 deterministic action
- UI 不得自己創造正式投資規則

---

9. Mobile-first

每頁第一屏優先回答：

1. 現在狀態
2. 是否需要行動
3. 下一步
4. 主 CTA

禁止先做 desktop 再縮手機。

---

10. LINE 邊界

LINE 不得形成第二套投資大腦。

未來方向：

System Action State
↓
Decision Digest
↙        ↘
New UI2   LINE
↓
OneBrain summary

本批只定 interface / ownership。

不要修改 LINE production。

---

11. Silent Autonomous Cruise

從現在起完全靜默執行。

不要回報：

- 正在讀檔
- 正在盤點
- 正在跑 test
- CI running
- CI green
- commit
- push
- PR ready
- agent activity
- 中間研究結果

只有以下情況才輸出：

1. 真 Decision Gate
2. blocker
3. Model / Effort Change
4. Manual Action
5. 整個 Architecture Gate 完成
6. Safe Handoff

---

12. Model / Effort

本批使用：

Claude Opus 5.5
Effort：High

原因：

這是 Architecture Boundary / Reuse / Migration / Decision Contract 工作。

如果執行途中判斷應切換模型或 Effort：

必須立即停止，
告訴我：

- 建議 Model
- 建議 Effort
- 原因

等我修改後才能繼續。

不得自行切換後繼續。

---

13. 完成 Architecture Gate 後

只有在以下全部完成：

- architecture frozen
- reuse matrix frozen
- four-page wireframe approved
- migration boundary approved
- preview strategy approved
- cutover strategy approved
- no unresolved architecture blocker

才通知：

「🟡 Model / Effort Change Gate：New UI2 architecture 已凍結，後續 presentation implementation 可切 Claude Sonnet 5.5 + Medium。」

然後立即停手。

不得自行開始 production。
```

- **裁示要點（撰寫組依上方原文歸納；與原文有出入以原文為準）**：
  1. **停手**：立即停止原 Stage A／現有 New UI 延續路線；#996 維持現狀；⛔ 開始原 Stage A、⛔ 修改 production UI、⛔ 擴大 #996 範圍、⛔ 因改走 New UI2 丟棄 #996、⛔ 刪除現有 New UI、⛔ 刪除 Old UI、⛔ 新增 Risk Cap runtime、⛔ 新增 OneBrain runtime、⛔ 重寫既有 data／services／rules；CI 可自然跑完，但⛔ 因 CI 綠燈自行開始舊 Stage A（(5)-1）。
  2. **#996 定位不變**：Q1=A／Q2=A／Q3=A、「簡化 UI，但不簡化 Decision Context」、Risk Cap boundary、Single Action Authority、Missing semantics、Freshness／Provenance、Presentation Slice ≠ Decision Context ≠ AI Output、Decision Digest、OneBrain boundary、Mobile-first、四頁 IA **全部保留**；**New UI2 以這些 semantic contracts 為 input，⛔ 重新發明投資語意**（(5)-2）。
  3. **新正式方向**：New UI2 Greenfield Presentation Architecture＝「全新的 Presentation Layer，但沿用成熟的底層資料與投資邏輯」；目標鏈 Canonical Data／Sources → Normalization／Validation → Deterministic Rules／Formulas → Risk Cap／Hard Constraints → System Action State → View Model／Presentation Contract → New UI2；未來 System Action State → Decision Digest → OneBrain；**New UI2 與 LINE 都是 consumer**（(5)-3）。
  4. **三代 UI 邊界**：Old UI＝只讀 Logic／Capability Reference、禁止修改；現有 New UI＝Legacy New UI／Reuse Candidate、停止把持續 patch 當正式主線；New UI2＝未來唯一主要 Presentation Layer（(5)-4）。
  5. **本批只做 Architecture Gate**（12 項；禁止 production coding）（(5)-5）→ 落點見 Architecture Gate §0 表。
  6. **Reuse 原則**：實查 repo 後分六類；優先保留底層；New UI2 主要重做 presentation 各項（(5)-6）→ Reuse Matrix。
  7. **四頁 IA 固定**：📊 市場／🎯 標的／💼 持股／👤 我的；⛔ 第五個主要頁面（(5)-7）。
  8. **永久產品方向與 invariant**（6 條，含「UI 不得自己創造正式投資規則」）（(5)-8）——與 DEC-122 六條永久 invariant **同向並存**，⛔ 讀成取代。
  9. **Mobile-first**：每頁第一屏優先回答現在狀態／是否需要行動／下一步／主 CTA；⛔ 先做 desktop 再縮手機（(5)-9）。
  10. **LINE 邊界**：LINE ⛔ 形成第二套投資大腦；本批只定 interface／ownership；⛔ 修改 LINE production（(5)-10）。
  11. **Silent Autonomous Cruise**：只在真 Decision Gate、blocker、Model／Effort Change、Manual Action、整個 Architecture Gate 完成、Safe Handoff 時輸出（(5)-11）。
  12. **Model／Effort**：本批 Opus 5.5＋High；判斷應切換 → 立即停止並告知建議 Model、Effort、原因，等客戶修改後才繼續，⛔ 自行切換（(5)-12）。
  13. **完成條件**：architecture frozen、reuse matrix frozen、four-page wireframe approved、migration boundary approved、preview strategy approved、cutover strategy approved、no unresolved architecture blocker **全部完成**，才通知「🟡 Model / Effort Change Gate：New UI2 architecture 已凍結，後續 presentation implementation 可切 Claude Sonnet 5.5 + Medium。」然後**立即停手，⛔ 自行開始 production**（(5)-13）。
- **與 DEC-122 的關係（逐項；「停止原 Stage A／現有 New UI 延續路線」「semantic contracts 全保留」＝客戶原文明示；其餘 Stage 對映＝撰寫組讀法〔INFERENCE〕，客戶可推翻）**：
  - **Freeze semantic contracts（`docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md` §0.1、§1～§16、§18～§21）**：**全部保留，為 New UI2 的 input**；New UI2 文件只寫「怎麼承接」，⛔ 重定義（客戶 (5)-2）。DEC-122 已加之所有 📌 與 supersede map S1～S20 **不變**。
  - **Stage A（Shared Presentation Foundation；優先 reuse `src/ui_v2`）**：**暫停／被取代**——不在現有 New UI 上建 primitives；A-1～A-3 的**語意項**（Neutral／Info tone、四態語意層、`unavailable`→`unwired`、metric card 四欄、freshness／source tag、Risk Cap alert 兩態文字、L1／L2／L3 層級）**保留為 New UI2 components 的需求**；「優先 reuse `src/ui_v2`」改依 Reuse Matrix U1～U4 判定（BACKLOG `FUI-STAGE-A` paused／superseded）。
  - **Stage B～E（四頁 Final UI，原為在現有 New UI 上施工）**：**施工路線被取代**——改為 New UI2 四頁；各頁 Freeze 語意內容（§2、§3、§10、§12、§16）**全保留為 UI2 頁面需求**；Freeze §2.0「各頁開工前出逐頁細線框送客戶拍板」由 `NEWUI2_WIREFRAMES_2026-11-02.md` 承接。BACKLOG `FUI-STAGE-B`～`E` 的內容欄仍是需求來源，施工落點改為 New UI2。
  - **Stage F（Headless Decision Digest）**：**保留**；~~與 New UI2 的先後依 **G3′**（A′：先建 Stage F 的「System Action 彙整」最小切片〔單一 headless L3 System Action Aggregator（系統動作彙整層），只彙整既有正式分支＋Risk Cap 狀態、不新增規則與寫入〕，UI2 與日後 LINE／Digest 共用；其餘 Stage F 照舊；B：等 Stage F 完整 Headless Digest 後才開始 UI2）。~~ 📌 Q2 裁示：System Action Aggregator（共用 System Action Aggregation Layer）**屬新 runtime component**——本 Gate 只凍結契約（Architecture Gate §4.6），實作待 implementation Gate（`NUI2-AGGREGATOR-IMPL`）；Stage F 其餘照舊（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）。
  - **Stage G（OneBrain Runtime）**：**保留**；仍⛔ 在 Headless Digest 合格前開始；UI2 只提供 OneBrain summary container（`🤖 ⬜ 尚未提供`）。
  - **Stage H（Cross-page Consistency）**：**保留**；射程＝New UI2 四頁＋所有 Digest consumer（含 LINE）。
  - **Stage I（Real-data／Mobile Acceptance）**：**保留**；驗收對象改為 New UI2；真機條件依 **G1**。
  - **Stage J（Old UI Supersede／Removal Gate）**：**保留**；對象擴為 **Old UI** 與 **Legacy New UI** 兩個，各自走 Removal Gate（Freeze §19 六條件∪DEC-083 第 11 點 E 段）；Capability Map 擴 Old → Legacy New → UI2 三欄。
  - **Freeze §17.1「⛔ 一邊改 UI、一邊提前接 LLM、一邊重構資料層」**：**繼續有效**。**Freeze §17.2 Model×Effort 表**：對 New UI2 施工改讀為——純 presentation 批 Sonnet 5.5＋Medium（Architecture 凍結後，客戶 (5)-13）；Risk Cap／Action Authority／Data semantic／Digest／OneBrain 批仍 Opus 5.5＋High（客戶 §0 表，DEC-122 原文一）。
- **與其他 DEC 的關係**：承 DEC-019／020（舊 UI 不得提前刪）、DEC-097（`?legacy=1` 不放可見連結）、DEC-091／092／097（四頁 IA）、DEC-104（Hard Output Gate）、DEC-084／106（Model×Effort 已符合時靜默繼續、不符停手通知）、DEC-118（GitHub Verification Gate 以當下 `origin/main` 為準）、DEC-122（Freeze）；`CLAUDE.md` v3 §03-2 ①（版面草稿先行）適用 New UI2 四頁線框。
- **Decision Gate（~~PENDING~~ **已裁示**，見本條末「客戶裁示 Q1～Q4」；送客戶四題；全文含推薦與理由見 Architecture Gate §11）**：
  - **G1｜Preview 方式**：**A（總管推薦）**獨立入口 `app_ui2.py`＋獨立 Streamlit Cloud 預覽 app（production 0 diff、手機真機＋真登入；需客戶人工操作：建 Cloud app、複製 secrets、GCP 加 redirect URI；外部 API 呼叫約加倍）；**B** 現行 app 加 `?ui=2`（便宜但改 production 入口，登入後旗標會遺失）；**C** 只在沙箱預覽，不給真機。
  - **G3′｜System Action Aggregator（~~系統動作彙整層~~）**：**A′（總管推薦）**先建單一 headless L3「System Action Aggregator（~~系統動作彙整層~~）」（＝Freeze §6 第 6 點／Stage F 的 System Action 彙整切片提前做），**只彙整**現有正式分支＋Risk Cap 狀態（合併 ETF 七分支與個股四級、加／留／換／減分組計數、「沒事 vs 判不出」gate、加碼列 Risk Cap 標註、跨頁 ⚡ N），**不新增任何規則**；**不新增任何寫入，只觸發既有服務的既有副作用**（如 `get_allocation` cache key、`refresh_macro_now` 鏈）；UI2 與日後 LINE／Digest 共用，VM 不做聚合；**請客戶確認此層不算其禁止的「新增 runtime」**。**B** 等 Stage F 完整 Headless Digest 後才開始（期間 UI2 動作欄位 `⬜ 尚未提供`）。
  - **四頁線框核准**：W-4（標的頁第一屏一行市場 context）、**W-5（「今日需處理」計入哪幾組；「留」組＝巡航、續抱、暫停加碼、高溢價、🟡 留意；A〔推薦〕加／換／減＋暫停加碼計入〔暫停加碼是 `RULE_ID_ALLOWLIST` 正式行動 id `pause_add`〕，巡航／續抱／高溢價／🟡 留意只做分布；B 只計加／換／減〔則暫停加碼、留意的日子會顯示「今日無需調整」〕）**、W-9（覆蓋度標籤改名）、**W-10（市場頁 ⚡ N 來源：彙整層建好前維持既有 ⚡ 語意＝`_market_blocks.render_alerts_block` 的關鍵警示＋allocation conflicts，或顯示 `⬜ 尚未提供`；建好後改讀彙整層）**、**W-11（持股桌機第一屏；推薦對齊 Freeze §16.3）**。
  - **G2｜Cutover＋#996 合併確認**：(1) **A（總管推薦）**四頁逐頁在 preview 驗收，全數通過後一次切換預設；現行 New UI 改隱藏 `?ui=1`、Old UI 維持 `?legacy=1`，不刪程式，回滾一行；**B** 逐頁切換 production；**C** 其他。(2) **是／否**：「#996（Freeze 已兩輪驗收 PASS、CI 綠）可否現在合併？」**推薦：可**；合併後本 Architecture Gate 以新 PR 落盤（同一指定分支，重設到新 main）。在此之前本 Gate 只存在工作樹（受分支權限限制）。
  - **不送題**：LINE 維持現狀、不改 LINE production（客戶 (5)-10 已明說）；目錄名、層別、守衛、session／CSS 前綴＝內部自決（v3 §03-1）。
  - 📌 擬題沿革（本批內修正，DEC-123 尚未落盤，故直接改寫、不留刪除線）：初稿 G3「唯讀轉接層」→ 稽核後改為 G3′ System Action Aggregator（~~系統動作彙整層~~）；初稿 G4「落盤順序 A／B／C」→ 併入 G2 第 (2) 小題的是／否。
- **效力邊界**：docs-only；`src/`、`tests/`、`shared/`、`app.py`、`requirements.txt`、`tools/`、`scripts/`、`.github/` 0 diff；不核准任何新資料源、schema、公式、門檻、投資語意、Risk Cap 數值、rule id、System Action runtime、OneBrain runtime；HI-1～HI-6 不變；舊 UI 與 Legacy New UI 一律不刪；本 DEC **不構成** New UI2 動工授權（含System Action Aggregator（~~系統動作彙整層~~）），直到客戶 (5)-13 七項完成條件全部成立並經 Model／Effort Change Gate。 📌 Q2：System Action Aggregator runtime 另須 implementation Gate；Q1：Preview App／Secrets／OAuth 網址待需要時以 🟡 Manual Action Gate 通知，⛔ 提前要求（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）。
- **Session 紀錄落點**：同 DEC-122 F6——repo 無 `SESSION_LOG` 檔；session 紀錄＝`docs/HANDOFF.md`「Safe Handoff（2026-11-02 New UI2）」區塊。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：裁示要點、與 DEC-122 關係的 Stage 對映、Gate 擬題為撰寫組單組產出（底稿＝兩份單組調查 invC Reuse Matrix、invD 架構約束），**未經第二組驗證**（BACKLOG `NUI2-ARCH-SECOND-AUDIT`）。
- **客戶裁示 Q1～Q4＋#996（2026-11-02；逐字，fence 內未改一字；具約束力）**（2026-11-02 追加；來源類別 D：客戶本輪對話原文，經總管轉交逐字檔 `customer_directive_2026-11-02.md` 第 (6) 段；撰寫組未見客戶原訊息本身，若有出入以原訊息為準；題號對映：Q1＝G1、Q2＝G3′、Q3＝四頁線框、Q4＝G2，#996＝原 G4／G2 第 (2) 小題）：

```
Q1：A

採獨立 Streamlit Cloud New UI2 Preview。

正式網站維持不動。

但 Preview-first 仍遵守成本控制：

- 架構／UI 驗收優先使用 fake / snapshot / view-model scenario。
- 真實外部資料只在 real-data acceptance 階段或必要人工驗收時使用。
- 不得為了 Preview 建第二套 data/service/source pipeline。
- Preview 與 production 最終必須讀相同 canonical services / contracts。

需要我人工建立 Preview App、複製 Secrets、Google OAuth 新增網址時，再以 🟡 Manual Action Gate 通知我；不要提前要求。

---

Q2：A，但修正一點分類。

我核准：

「共用 System Action Aggregation Layer」

其責任只允許：

- 收集既有 deterministic rules 的正式結果
- 收集既有 Risk Cap state
- 區分 actionable / non-actionable / unavailable / not evaluated
- 加／留／換／減 presentation grouping
- 統一計數
- 區分「今日無需調整」與「無法判定」
- 提供 New UI2 / 未來 LINE / Decision Digest 共用的 canonical action-facing view

禁止：

- 新增投資規則
- 新門檻
- 新比例
- AI action
- 改寫既有 deterministic result
- 覆寫 Risk Cap
- 自行決定減碼 1/2／全出
- portfolio write
- Sheet write

但請注意：

它仍屬「新的 runtime component」。

因此目前 Architecture Gate：

只允許凍結 interface / ownership / input-output contract / tests / migration plan。

「本批不得實作 production runtime。」

請把它正式登錄為 New UI2 後續 prerequisite backlog，再經 implementation Gate 才施工。

它的定位必須是：

Existing Formal Rules + Risk Cap
→ System Action Aggregator
→ System Action State / action-facing canonical contract
→ Decision Digest / New UI2 / LINE

不是第二套規則引擎。

---

Q3：四頁 wireframe 核准。

其中：

W-4：核准。

🎯 標的頁第一屏可有「市場位階＋Risk Cap」的一行 context，但只能是輕量 context row / chip，不得搶過：

- 查一檔
- 標的基本面
- valuation / company-first research

不得把市場技術訊號變成單一股票的主要判斷。

W-5：A。

「今日需處理」包含：

- 加
- 換
- 減
- 暫停加碼

因「暫停加碼」本身是正式 action code，不得顯示成「今日無需調整」。

🟡 留意若只是資訊狀態、沒有正式 action code，仍不得自行升格成 portfolio action。

W-9：核准。

使用：

「可判定覆蓋度」

不要使用「訊號可信度」，避免被誤讀成 calibrated confidence / probability。

W-10：核准作為 transitional contract。

但在 System Action Aggregator 完成以前，市場頁沿用的舊警示必須：

- 清楚標 source / scope
- 不得假裝是新的 System Action State
- 不得形成第二套 Action Authority
- 不得與持股頁衝突時自行選一邊

Aggregator 完成後，市場與持股必須改成同一 canonical action source。

W-11：核准。

桌機版持股頁依 Freeze：

- 圖表
- 建議持股區間
- 後續表格

但建議持股區間不得被誤寫成已啟用的 Portfolio Risk Cap；兩者語意維持分離。

---

Q4：A。

Cutover：

New UI2
→ 獨立 Preview
→ 四頁逐頁驗收
→ mobile / desktop
→ missing / stale / source failure
→ real-data acceptance
→ cross-page consistency
→ 全部通過
→ 一次切成正式 default

現有 New UI 與 Old UI 在 Cutover 後先保留 rollback path。

不得先刪程式。

正式切換後，再另進 Removal Gate。

---

#996：

可以現在合併。

理由：

- docs-only
- Final UI Freeze 已完成兩輪驗收
- head CI 已 green
- mergeable
- 沒有 production code change

請先完成 #996 的既有收尾，不要把 New UI2 草案塞進 #996。

#996 合併後：

1. 重新 fetch main
2. 從最新 main 建新的 New UI2 docs branch
3. 把目前 scratchpad / working tree 的 New UI2 Architecture 草案搬到新 branch
4. 開獨立 PR
5. 做獨立稽核
6. 不得開始 production coding

---

非常重要：New UI2 新規則、稽核項目與待辦必須全部正式落 GitHub。

不能只存在：

- scratchpad
- 聊天
- PR 描述
- HANDOFF 一句話
- Claude memory

至少同步：

- PROJECT_RULES.md
- docs/DECISIONS.md
- docs/BACKLOG.md
- docs/PROJECT_STATE.md
- docs/HANDOFF.md
- session log
- New UI2 Architecture Proposal
- Reuse Matrix
- Wireframes
- Migration / Cutover Contract
- Audit / Acceptance checklist

BACKLOG 至少要獨立保留：

- New UI2 Preview
- View Model boundary
- System Action Aggregator implementation
- Risk Cap Numeric Gate
- proportional action rules
- Headless Decision Digest
- OneBrain runtime
- LINE / UI canonical action convergence
- mobile acceptance
- desktop acceptance
- missing / stale / failure acceptance
- real-data acceptance
- cross-page consistency
- cutover
- rollback
- Old / Legacy New UI Removal Gate

並新增永久收尾 Gate：

「每一批完成前，必須檢查是否出現新的 Rule / Decision / Audit finding / Limitation / Backlog / Migration debt；若有，必須同步 GitHub 正式文件後才能宣告該批完成。」

沒有寫進 GitHub的項目，不視為可靠專案狀態。

---

目前仍維持：

Claude Opus 5.5
Effort：High

Architecture Gate 尚未正式凍結，不得降模型。

如果判斷應切 Model / Effort，先停手通知我，等我修改後再繼續。

全程 Silent Autonomous Cruise。

只有：

- Decision Gate
- Model / Effort Change
- Manual Action
- blocker
- whole Architecture Stage complete
- Safe Handoff

才回報。
```

- **裁示要點（撰寫組依上方原文歸納；與原文有出入以原文為準；條文化落點見各項）**：
  1. **Q1=A**：獨立 Streamlit Cloud New UI2 Preview；正式網站不動；成本控制四點（fake／snapshot／VM scenario 優先、真實外部資料只在 real-data acceptance 或必要人工驗收、⛔ 第二套 data／service／source pipeline、Preview 與 production 讀相同 canonical services／contracts）；人工建 Preview App／Secrets／OAuth 網址→需要時以 🟡 Manual Action Gate 通知、⛔ 提前要求（Architecture Gate §7.3）。
  2. **Q2=A，但修正分類**：正式名稱 **System Action Aggregator（共用 System Action Aggregation Layer）**；允許責任 7 項、禁止 9 項（逐字落於 Architecture Gate §4.6.3／§4.6.4）；**屬新的 runtime component**——本 Gate 只凍結 interface／ownership／input-output contract／tests／migration plan，**本批不得實作 production runtime**；登錄為 New UI2 後續 prerequisite backlog（`NUI2-AGGREGATOR-IMPL`），經 implementation Gate 才施工；定位 Existing Formal Rules＋Risk Cap → System Action Aggregator → System Action State／action-facing canonical contract → Decision Digest／New UI2／LINE；**不是第二套規則引擎**。總管原讀法「不算新增 runtime」**被客戶推翻**（已於 Gate §4.5、§11 刪除線）。
  3. **Q3 四頁線框核准**：W-4 核准但限輕量 context row／chip（⛔ 搶過查一檔、標的基本面、valuation／company-first research；⛔ 市場技術訊號成為單一股票主要判斷）；W-5=A（加／換／減／暫停加碼計入「今日需處理」；暫停加碼是正式 action code，⛔ 顯示成「今日無需調整」；🟡 留意若無正式 action code ⛔ 升格成 portfolio action）；W-9「可判定覆蓋度」（⛔「訊號可信度」）；W-10 為 transitional contract（Aggregator 完成前舊警示標 source／scope、⛔ 冒充新 System Action State、⛔ 第二套 Action Authority、⛔ 與持股頁衝突時自行選一邊；完成後市場與持股同一 canonical action source）；W-11 持股桌機依 Freeze（圖表、建議持股區間、後續表格），建議持股區間 ⛔ 寫成已啟用 Portfolio Risk Cap、語意分離（線框 §9）。
  4. **Q4=A**：Cutover 鏈九步、Cutover 後保留現有 New UI 與 Old UI rollback path、⛔ 先刪程式、正式切換後另進 Removal Gate（`docs/vnext/NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md`）。
  5. **#996 可以現在合併**（已合併，main＝`acd1648c`）；New UI2 草案 ⛔ 塞進 #996；合併後從最新 main 建 New UI2 docs branch、開獨立 PR（＝#997）、做獨立稽核、⛔ 開始 production coding。
  6. **全部正式落 GitHub**：New UI2 新規則、稽核項目與待辦⛔ 只存在 scratchpad、聊天、PR 描述、HANDOFF 一句話、Claude memory；至少同步 `PROJECT_RULES.md`、DECISIONS、BACKLOG、PROJECT_STATE、HANDOFF、session log、Architecture Proposal、Reuse Matrix、Wireframes、Migration／Cutover Contract、Audit／Acceptance checklist；BACKLOG 獨立保留客戶點名 16 項（`docs/BACKLOG.md` §5.1.19）。
  7. **永久收尾 Gate**：「每一批完成前，必須檢查是否出現新的 Rule / Decision / Audit finding / Limitation / Backlog / Migration debt；若有，必須同步 GitHub 正式文件後才能宣告該批完成。」「沒有寫進 GitHub的項目，不視為可靠專案狀態。」→ `PROJECT_RULES.md` 第 27 節。
  8. **Model／Effort**：維持 Opus 5.5＋High；**Architecture Gate 尚未正式凍結，不得降模型**；判斷應切換 → 先停手通知客戶。Silent Autonomous Cruise。
- 📌 **警語解除**（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）：本條狀態與 HANDOFF／PROJECT_STATE 中「Gate 只存在工作樹」「GitHub 舊接手點仍寫開 Stage A-1」兩則警語**已解除**——#996 已合併、本 Gate 已落盤（commit `6d30dcea`／PR #997）；`main` 上的 HANDOFF 舊段仍保留其原文，以本條與 #997 HANDOFF 新 Safe Handoff 為準。
- ⚠️ 揭露（裁示整合批）：裁示要點、題號對映、Aggregator I／O 欄位名、Migration／Cutover 判準與 Audit 清單為撰寫組單組產出，待 #997 獨立稽核（`NUI2-ARCH-SECOND-AUDIT`）。

### DEC-124｜New UI2 Semantic Correction Gate：正式資料語意只有 OK／Missing／Stale／Unavailable／Not Evaluated 五個；「⬜ 尚未提供」＝Capability／Implementation Availability State（Preview-only、與資料語意正交，⛔ 稱第 6 個資料語意態）；Risk Cap「⬜ 無法判定」＝Unable to Determine，⛔ 等同 NOT_EVALUATED（客戶 2026-11-02）

> 2026-11-02 補登（ID 取下一個未用號；落盤前 `grep -rn "DEC-124" docs PROJECT_RULES.md CLAUDE.md` 0 命中，DEC-123 為上一號）。**來源類別 D：客戶 2026-11-02 本輪對話原文，經總管轉交逐字檔（`customer_directive_2026-11-02.md` 第 (8) 段）；下方 fence 內逐字收錄，未改一字**（撰寫組未見客戶原訊息本身，只見總管轉交之全文；若有出入以原訊息為準）。

- **決策者**：**客戶**（2026-11-02）。｜**效力日期**：2026-11-02 起。｜**範圍**：資料語意（永久）＋New UI2 View Model 契約（`shared/ui2_contract`）＋Risk Cap 呈現語意（不含數值）＋治理同步。
- **狀態**：**客戶指示生效**；Semantic Correction Gate 實作完成、**待總管複驗＋獨立 QA＋客戶驗收**；#998（New UI2 Batch 1）整體接受、⛔ 回退。驗收通過後若下一批只剩 navigation／cards／layout／responsive／fake-data presentation，回報「🟡 Model / Effort Change Gate：語意修正完成，可切 Claude Sonnet 5.5 + Medium。」並停手（客戶 (8)-7）。
- **客戶原文：Semantic Correction Gate 全文（逐字，fence 內未改一字；具約束力）**：

```
先不要開始 New UI2 下一個一般 UI Batch。

請先處理一個小型 Semantic Correction Gate。

建議 Model / Effort：

Claude Opus 5.5
Effort：High

原因：這次涉及 FieldState、Missing semantics、Risk Cap「無法判定」語意，不是純 presentation 修補。

---

1. #998 整體接受

#998 的：

- layering guards
- View Model skeleton
- fake Preview entrypoint
- production 0 diff
- System Action Aggregator / Risk Cap / Digest / OneBrain 未施工
- §27 GitHub 落盤

均接受。

不要回退 #998。

---

2. "⬜ 尚未提供" 可以保留，但重新定義邊界

允許：

"⬜ 尚未提供"

但它的正式意義只能是：

Capability / Implementation Availability State

例如：

- System Action Aggregator 尚未實作
- OneBrain 尚未實作
- 某 Preview 功能尚未接線

它不是 objective data quality state。

因此不要把它描述成：

「第 6 個正式資料語意態」。

正式資料語意仍維持：

- OK
- Missing
- Stale
- Unavailable
- Not Evaluated

而 "Not Provided" 是 orthogonal capability state / Preview-only implementation state。

請檢查目前 "FieldState.NOT_PROVIDED" 是否會造成資料語意與 capability 語意混層。

優先考慮：

A. 將 capability availability 與 data state 分開建模
或
B. 若本批不值得重構 enum，至少先把 contract、型別註解、guards、tests 明確限制為 Preview-only capability marker，並登記後續拆分 backlog。

請依最小必要變更選擇，不要為此大改架構。

---

3. Risk Cap "⬜ 無法判定" 不得等同 "NOT_EVALUATED"

這點必須修正。

永久語意：

Not Evaluated

代表：

「這項規則／計算尚未執行或不在本次評估範圍。」

Unable to Determine

代表：

「有進入判定流程，但因必要輸入 Missing / Unavailable / Invalid / insufficient，無法得到正式結果。」

兩者禁止合併。

因此：

Risk Cap 顯示：

"⬜ 無法判定"

時，不得自動等同：

"NOT_EVALUATED"

也不得因此推導：

- safe
- neutral
- no action
- 無需調整
- 可加碼

請先查目前正式 Risk Cap / Freeze contract，再決定 VM 最小正確表示方式。

不得自行新增 Risk Cap 計算規則或數值。

---

4. 導覽 W-1

目前 Streamlit 內建頂部 navigation 可暫時保留作 Preview skeleton。

但它只是：

temporary implementation gap

不是 W-1 amendment。

正式凍結規格仍是：

- mobile：底部固定 navigation
- desktop：左側 navigation

請維持 BACKLOG / Acceptance item。

下一個 presentation batch 再修。

不得因目前骨架方便而修改已凍結 W-1。

---

5. 本 Gate 範圍

最多處理：

1. FieldState / capability-state semantic boundary
2. Risk Cap "無法判定" vs "未評估" 修正
3. tests + GitHub governance sync

不要順便做：

- navigation implementation
- real data wiring
- Aggregator
- Risk Cap runtime
- Digest
- OneBrain
- LINE

---

6. GitHub 落盤

依 PROJECT_RULES §27：

若這次形成新的：

- Rule
- Decision
- Audit finding
- Limitation
- Backlog
- Migration debt

必須同步 GitHub 正式文件後才能完成。

至少核對：

- PROJECT_RULES
- DECISIONS
- BACKLOG
- PROJECT_STATE
- HANDOFF
- New UI2 contract / audit checklist

---

7. 完成後 Model Gate

這個 Semantic Correction Gate 完成並驗收通過後：

若下一批只剩 navigation / cards / layout / responsive / fake-data presentation，

回報：

「🟡 Model / Effort Change Gate：語意修正完成，可切 Claude Sonnet 5.5 + Medium。」

然後停手。

不得自行開始下一批。

維持 Silent Autonomous Cruise。
```

- **永久語意規則（撰寫組依上方原文條文化；與原文有出入以原文為準）**：
  1. **正式資料語意只有五個**：OK／Missing／Stale／Unavailable／Not Evaluated〔(8)-2〕。
  2. **「⬜ 尚未提供」**＝**Capability／Implementation Availability State**（例：System Action Aggregator 尚未實作、OneBrain 尚未實作、某 Preview 功能尚未接線）；**不是** objective data quality state；**⛔ 描述成「第 6 個正式資料語意態」**；與資料語意**正交**，屬 **Preview-only implementation state**〔(8)-2〕。
  3. **Not Evaluated**＝「這項規則／計算尚未執行或不在本次評估範圍。」〔(8)-3，逐字〕
  4. **Unable to Determine**＝「有進入判定流程，但因必要輸入 Missing / Unavailable / Invalid / insufficient，無法得到正式結果。」〔(8)-3，逐字〕
  5. **兩者禁止合併**；Risk Cap 顯示「⬜ 無法判定」時，**⛔ 自動等同 NOT_EVALUATED**，**⛔ 因此推導** safe／neutral／no action／無需調整／可加碼〔(8)-3〕。
  6. **⛔ 自行新增 Risk Cap 計算規則或數值**〔(8)-3〕（Freeze §0.1.4 第 5、6 點、BACKLOG `FUI-RC-NUMERIC-GATE` 不變）。
  7. **導覽 W-1**：Streamlit 內建頂部 navigation 只是 **temporary implementation gap**，**不是 W-1 amendment**；正式凍結規格仍是 mobile 底部固定 navigation、desktop 左側 navigation；維持 BACKLOG／Acceptance item；下一個 presentation batch 再修；⛔ 因骨架方便修改已凍結 W-1〔(8)-4〕。
- **落地（AI 總管內部自決，客戶可推翻；`CLAUDE.md` v3 §03-1）**：
  - **選項 A（capability 與資料語意分開建模）**，理由：(1) 客戶「優先考慮 A」，且 (8)-2 明言「正式資料語意仍維持」五個——B 保留 enum 成員就等於在型別層繼續把 capability 列為第六個資料態，與該句直接衝突；(2) 影響面小：`FieldState` 只在 `shared/ui2_contract`、`src/services/ui2`、`src/ui2`、`tests/test_ui2_*.py` 使用（grep 實查，New UI2 套件外 0 引用；單組），拆分不動任何 Legacy／production 檔；(3) 第 2 項（Unable to Determine）本來就需要在型別層新增一個非資料語意的值，同一批一起分軸比先 B 再拆少一次契約變更。**未大改架構**：`FieldVM` 仍是單一型別，只新增 `capability` 欄位與兩個小 enum。
  - **契約三軸**（`shared/ui2_contract/models.py`／`text.py`）：`FieldState`＝資料語意五態（恰五個；守衛釘死）；`JudgementState.UNDETERMINABLE`＝判定結果（非資料語意）；`CapabilityState.NOT_PROVIDED`＝capability marker（`FieldVM.capability`；該欄位 `state` 必為 None、⛔ 帶值）。三張字樣表互斥（`ALLOWED_STATUS_PREFIXES`／`JUDGEMENT_STATUS_PREFIXES`／`CAPABILITY_STATUS_PREFIXES`）。
  - **Risk Cap 表示**：依 Freeze §0.1.4 第 3 點（「目前曝險或有效 Risk Cap 任一資料不足 → 一律顯示 `⬜ 無法判定`」）、§8.2「曝險分母不存在」、Architecture Gate §4.6.6 O4b（`exposure_gate` 數值 Gate 前恆 `undeterminable`）——現況是**已進入判定（閘門形狀已凍結），但必要輸入「目前曝險」無正式來源** ⇒ **Unable to Determine**。VM 以 `JudgementState.UNDETERMINABLE`＋字樣 `⬜ 無法判定`（逐字不改）表示；⛔ 帶值、⛔ 綠色、⛔ 「今日無需調整」等 safe 讀法（守衛＋mutation）。⛔ 新增任何 Risk Cap 規則或數值。
  - **「⬜ 未評估／資料不足」（DEC-074／075 客戶逐字）語意歸類**：原始語境＝「受 breadth 影響且**無法依既有正式規則可靠計算**的健康分」「健康分**因缺少正式 breadth** 而未評估時……市場位階也顯示」——該健康分／位階**在正常評估範圍內**、計算因**必要輸入（正式 breadth）不足**而得不到正式結果 ⇒ 依本條第 4 點屬 **Unable to Determine**，**不是** Not Evaluated（規則並非未執行或不在範圍）。**字樣逐字保留不改**（含「未評估」三字），只修語意歸類。⚠️ 單組判讀；字樣含「未評估」易誤讀，登記待第二組覆核（BACKLOG `NUI2-DATA-SHORT-CLASSIFICATION-REVIEW`）。
  - **`⬜ 尚未核准／無法判定`**（Freeze §5.2 metadata `not_approved`）：規則／數值未核准 → 未執行 ⇒ 維持 Not Evaluated；但字樣尾綴含「無法判定」屬混合字樣，**逐字不改**；~~UI2 ⛔ 用它表示 Risk Cap~~ **New UI2 一律 ⛔ 使用此字樣**（已自 UI2 Not Evaluated 允許表移除，建構即 raise，守衛有 teeth）（2026-11-02 DEC-124 獨立稽核 PASS with fixes 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔稽核修正〕；原文刪除線保留）；登記待覆核（BACKLOG `NUI2-NOT-APPROVED-LITERAL-REVIEW`）。
  - **Aggregator 契約（docs-only，未實作）**：Architecture Gate §4.6.6 O1 原把 `holdings_data_short` 的 `unjudged`（`KEY_INSUFFICIENT`「⬜ 資料不足／無法判定」／`KEY_INVALID_INPUTS`／`KEY_INVALID_LIGHTS`）映射成 `action_class=not_evaluated`——依本條第 4、5 點屬 Unable to Determine 被併入 Not Evaluated；改為新增 `action_class=undeterminable`、`unjudged→undeterminable`、O2 加 `undeterminable_n`（刪除線保留原文；O3／O4b 既有 `undeterminable` 不變）。客戶 Q2 原文四類（actionable／non-actionable／unavailable／not evaluated）一字未改，`undeterminable` 為依本條加的第五類（AI 總管暫定，客戶可推翻）。
- **與其他 DEC 的關係**（append-only；撰寫組讀法，單組，⚠️ 待第二組 evidence audit）：
  - **DEC-122（Final UI Contract Freeze）§5.1／§5.3、DEC-122 Supersede 摘要「DEC-074／075『⬜ 未評估／資料不足』保留為 Not evaluated 子原因字樣」**：**部分取代**——該字樣與 Risk Cap `⬜ 無法判定` 自本條起歸 **Unable to Determine**（字樣不改）；§5.3 Batch 1 註記「第 6 態 `NOT_PROVIDED`」改為 capability state。四態定義、L1 字樣、「永遠」五條（missing ≠ 0……not evaluated ≠ safe）**全部仍有效**，並延伸：**無法判定 ≠ safe／neutral／no action／無需調整／可加碼**。
  - **DEC-122 Q1=A（Freeze §0.1.4）**：**同向、精確化**——「unavailable／not evaluated 不得解讀成 safe，也不得因此允許加碼」不變；本條補「無法判定」是獨立語意、同樣 ⛔ safe／加碼。
  - **DEC-123 Q2（Aggregator 允許責任 3「區分 actionable / non-actionable / unavailable / not evaluated」、責任 6「區分『今日無需調整』與『無法判定』」）**：**同向**；本條把責任 6 的「無法判定」與責任 3 的 not evaluated 明確分開（見上「Aggregator 契約」）。
  - **DEC-074／DEC-075**：**字樣保留、語意歸類精確化**（見上）；「不得因為產品希望『有結論』而補出投資結論」**同向**。
  - **DEC-110 R8「十態不另造」**：不衝突——本條未新增 `UI_STATE_META` 第 11 態；三軸是 New UI2 VM 契約的分類層。
  - **PROJECT_RULES 第 19.8 節（Missing 語意）**：同向；已加註本條為永久語意補充。
- **效力邊界**：⛔ navigation implementation、real data wiring、Aggregator runtime、Risk Cap runtime、Digest、OneBrain、LINE〔(8)-5〕；`app.py`、`requirements.txt`、`src/ui/**`、`src/ui_v2/**`、`src/data`、`src/compute`、`shared` 既有非 ui2 檔 0 diff；不核准任何新資料源、公式、門檻、Risk Cap 數值。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：選項 A 的理由、Risk Cap／DEC-074／075／`not_approved` 的語意歸類、Aggregator O1 修正均為實作組單組產出，**待總管複驗與獨立 QA**；「`FieldState` 在 New UI2 套件外 0 引用」為 grep 結果、非窮舉。
- 📌 **獨立稽核結果（2026-11-02，第二組，非實作組）**：判 **PASS with fixes**——選項 A、Risk Cap＝`UNDETERMINABLE`、DEC-074／075 歸 Unable to Determine、Aggregator O1 第五類 `undeterminable` **皆同意**（9 項 mutation 全紅）；修正項（`⬜ 尚未核准／無法判定` 自 UI2 移除、文件指標與措辭、CI 阻擋的既有脆弱測試決定化）已於同分支修正批處理。實作 commit＝`64e6fe2c`；修正批 SHA 由總管補記（2026-11-02 DEC-124 獨立稽核 PASS with fixes 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔稽核修正〕；原文刪除線保留）。

### DEC-125｜歷史脈絡遺失檢查與 GitHub 補落盤：台股趨勢／國際趨勢 Research Baseline、市場產品主軸只留兩條、中性命名永久規則、GitHub 落盤位置（客戶 2026-11-03）

> 2026-11-03 補登（ID 取下一個未用號；落盤前 `grep -n "DEC-125" docs/DECISIONS.md PROJECT_RULES.md docs/BACKLOG.md` 0 命中，DEC-124 為上一號）。**來源類別 D：客戶 2026-11-03 本輪指示 (10) A 節原文，經總管轉交逐字檔（`customer_directive_2026-11-02.md` 第 (10) 段）；下方 fence 內逐字收錄 A1～A5，未改一字**（撰寫組未見客戶原訊息本身，只見總管轉交之全文；若有出入以原訊息為準）。

- **決策者**：**客戶**（2026-11-03）。｜**效力日期**：2026-11-03 起。｜**範圍**：治理（落盤規則已有）＋市場趨勢 Research Baseline（docs-only）＋中性命名永久規則。
- **狀態**：**客戶指示生效**；A 段 docs／governance 落盤完成（撰寫組單組，待總管複驗）；**不新增任何 production investment logic**。B 段（New UI2 Batch 3）另行，不屬本 DEC。
- **客戶原文：A 節全文（A1～A5，逐字，fence 內未改一字；具約束力）**：

```
A. Historical Context Loss Check＋GitHub SSOT 補落盤

這段先做 docs / governance 收斂，不新增 production investment logic。

先確認 GitHub 是否已經有完整 SSOT 保存以下內容；已有就只 cross-reference，不建立第二份。

A1. 台股趨勢 Research Baseline

正式研究方向至少保存：

- EPS × 合理 PE 的加權指數情境估值
- 外資籌碼
- 融資
- 市場擁擠度
- 回撤／市場風險
- 市場廣度

永久語意：

EPS × PE 只是台股大盤情境估值方法之一，不等於完整市場趨勢判斷。

不得自行：

- 核准 EPS source
- 核准 PE multiple
- 發明 growth assumption
- 新增 production formula
- 由 EPS×PE 直接產生買賣 action

尚未正式核准的 source / formula / horizon / update frequency / PE rationale 保持 Pending／Decision Gate。

A2. 國際趨勢 Research Baseline

至少保存：

- 長債殖利率
- 殖利率曲線
- Leading Indicators
- PMI
- Inflation
- Fed / monetary policy
- Real Yield
- VIX
- Credit Spread
- USD
- Major Equity Markets

這些只能作：

- objective input
- research dimension
- context overlay

除非 repo 已有正式 validated deterministic contract，禁止自行重新組成：

- 多頭／空頭公式
- scoring model
- Risk Cap rule
- System Action
- probability

A3. 市場產品主軸

正式市場趨勢只保留：

1. 台股趨勢
2. 國際趨勢

Old UI / Legacy New UI 可以提供 capability / logic / source reference，但不得重新增加第三、第四套市場主軸。

A4. 中性命名永久規則

研究文件與 provenance 可以保存原始作者／來源人物。

但正式：

- UI
- navigation
- card title
- indicator name
- feature name
- OneBrain output
- LINE output
- production rule identifier

不得使用老師／個人姓名作為 production 功能或邏輯名稱。

使用中性產品語意，例如：

- 台股大盤情境估值
- EPS × PE 情境矩陣
- 台股趨勢
- 國際趨勢
- 市場估值區間

A5. GitHub 落盤

依 PROJECT_RULES §27：

- Rule → PROJECT_RULES / 正式 spec
- Decision → DECISIONS
- Pending → BACKLOG
- Current status → PROJECT_STATE
- Safe Handoff → HANDOFF
- Research baseline → 正式 vNext research / market spec

不得只留在：

- 聊天
- scratchpad
- PR body
- Claude memory

```

- **裁示要點（撰寫組條文化；與原文有出入以原文為準）**：
  1. **A1 台股趨勢 Research Baseline**：維度＝EPS×合理 PE 的加權指數情境估值／外資籌碼／融資／市場擁擠度／回撤與市場風險／市場廣度。永久語意：**EPS×PE 只是台股大盤情境估值方法之一，不等於完整市場趨勢判斷**。⛔ 不得自行核准 EPS source、核准 PE multiple、發明 growth assumption、新增 production formula、由 EPS×PE 直接產生買賣 action；未核准的 source／formula／horizon／update frequency／PE rationale 保持 Pending／Decision Gate。
  2. **A2 國際趨勢 Research Baseline**：維度＝長債殖利率／殖利率曲線／Leading Indicators／PMI／Inflation／Fed／monetary policy／Real Yield／VIX／Credit Spread／USD／Major Equity Markets，**只能**作 objective input／research dimension／context overlay；除非 repo 已有正式 validated deterministic contract，⛔ 不得自行組成多空公式、scoring model、Risk Cap rule、System Action、probability。
  3. **A3 市場產品主軸**：正式市場趨勢只保留 1. 台股趨勢、2. 國際趨勢；Old UI／Legacy New UI 只作 capability／logic／source reference，⛔ 不得新增第三、第四套市場主軸。
  4. **A4 中性命名**：研究文件與 provenance 可保存原始作者／來源人物；正式 UI／navigation／card title／indicator name／feature name／OneBrain output／LINE output／production rule identifier ⛔ 不得使用老師／個人姓名作為 production 功能或邏輯名稱。
  5. **A5 GitHub 落盤**：依 `PROJECT_RULES.md` 第 27 節（Rule→PROJECT_RULES／正式 spec；Decision→DECISIONS；Pending→BACKLOG；Current status→PROJECT_STATE；Safe Handoff→HANDOFF；Research baseline→正式 vNext research／market spec）；⛔ 不得只留在聊天、scratchpad、PR body、Claude memory。
- **落盤位置（本 DEC 的實作；A5）**：Rule → `PROJECT_RULES.md` 第 28 節；Research baseline／A3 規格 → `docs/vnext/MARKET_TREND_RESEARCH_BASELINE_2026-11-03.md`；Pending → `docs/BACKLOG.md` §5.1.23（`MKT-RB-*`）；Current status → `docs/PROJECT_STATE.md` §55；Safe Handoff → `docs/HANDOFF.md` 最末段。
- **與其他 DEC／契約的關係（append-only，撰寫組讀法，單組，⚠️ 待第二組 evidence audit）**：
  - **DEC-071**（兩主軸、研究框架非 Approved）：**同向、再確認**（A3 = DEC-071 第 5 點；A1／A2 清單與 PROJECT_STATE §22.2 取聯集，不取代）。
  - **DEC-091(g)／DEC-092／Freeze §11（客戶 §43）／`DEC092-EPSPE-HIGH-GATE`／`VN1-MT-VALUATION`**：**同向**；大盤 EPS×PE 維持 Research Gate、與單檔估值分開治理；本 DEC 不新增 EPS×PE Gate 列。
  - **DEC-123／DEC-124**（New UI2、三軸語意）：不衝突；A 段不動 UI2 code。
  - **DEC-122**（Final UI Freeze）：Freeze 全部 semantic contracts 不受影響。
  - **舊 DEC 衝突檢查**：以關鍵字（台股趨勢／國際趨勢／EPS×PE／老師／去識別）掃 `docs/DECISIONS.md` 與 `PROJECT_RULES.md`，**未發現需加刪除線或 📌 取代標記的衝突**（單組、未窮舉）。注意：`docs/DECISIONS.md` DEC-092（圖 C 條）與 `docs/PROJECT_STATE.md` §22.2／§32 等**文件內**含研究作者姓名，屬 A4 第一句允許的「研究文件與 provenance」，不構成違反。
- **效力邊界（⛔ 不是實作授權）**：不新增資料來源、公式、門檻、probability；不改 Risk Cap；不實作 Aggregator／Digest／OneBrain／LINE；不改任何 `src/`／`tests/`／`shared/`／`app.py`。A4 的命名違反盤點只**登記**不修（`CLAUDE.md` §-1）。
- **疑點（需客戶知悉／裁示，撰寫組不自決）**：(1) A3「不得第三、第四套市場主軸」與 DEC-091／092 Q5「產業趨勢先研究」（標的層研究線）的關係——撰寫組讀為兩者不衝突（產業趨勢屬標的層），若客戶意指不同請裁示（`MKT-RB-AXES-INDUSTRY-READING`）；**Mapping（獨立複驗補）**：`decision_digest` 的 industry 區段（`NOT_DEFINED`）屬標的層產業趨勢；市場頁 Macro mini／sparkline 區塊屬國際趨勢 context overlay、不構成第三主軸，併入該列請客戶一併確認；(2) A4 適用範圍（內部私有變數名、測試檔名、過渡 alias 是否算「production 邏輯名稱」）——撰寫組暫以「使用者可見／規則名稱流通處」為準（`PROJECT_RULES.md` 第 28 節第 3 點，INFERENCE）。

### DEC-126｜多元解法與最小成本決策規則（Multi-Path Decision & Minimum Cost Rule）：遇問題先評估 ≥3 方案、內部比較不輸出、僅 6 種情形回報（須附推薦）、禁止以更高模型／更多 Token 掩蓋錯誤路徑（客戶 2026-11-03）

> 2026-11-03 補登（ID 取下一個未用號；DEC-125 為上一號）。**來源類別 D：客戶 2026-11-03 指示原文，經總管轉交；下方 fence 內逐字收錄，未改一字**（撰寫組未見客戶原訊息本身，只見總管轉交之全文；若有出入以原訊息為準）。

- **決策者**：**客戶**（2026-11-03）。｜**效力日期**：2026-11-03 起。｜**範圍**：治理（永久規則）；docs-only，不新增任何 production code／資料邏輯／投資規則。
- **狀態**：**客戶指示生效**；條文化落盤為 `PROJECT_RULES.md` **第 29 節**（9.1 加 cross-reference）；撰寫組單組、待總管複驗。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：

```
多元解法與最小成本決策規則

遇到技術、資料、UI、架構、流程或除錯問題時，不得預設只有單一路徑，也不得在同一路徑持續原地試錯。

在進入實作前，應至少先評估 3 個可行方案。

若客觀上不足 3 個方案，必須明確說明原因。

每個方案至少比較：

- 正確性與資料語意風險
- 實作／修復速度
- Token 與模型成本
- 修改範圍與回歸風險
- 可逆性
- 是否可沿用既有模組、資料或流程
- 失敗後的降級／替代路徑

預設決策排序：

1. 正確性足夠且風險低
2. 完成最快
3. Token／成本最低
4. 修改範圍最小

不得因第一個方案已經開始，就持續投入 sunk cost。

如果出現以下任一情況：

- 同一路徑重複失敗
- 修改範圍持續擴大
- 需要新增不必要依賴
- Token 成本明顯升高
- 時間成本明顯高於替代方案
- 回歸風險持續增加

必須停止原路徑，重新比較 B／C 方案。

專案 AI 應主動比使用者更早發現替代方案，不得等使用者提出後才開始思考。

執行方式

這條規則不是要求每次都輸出長篇比較。

正常情況下：

- AI 可在內部完成 3 路徑比較
- 選出 Minimum Sufficient Path 後直接執行
- 不需為了展示比較而浪費 Token

只有以下情況才需要回報 3 方案給使用者：

1. 三個方案在風險／成本上差異顯著
2. 涉及不可逆變更
3. 涉及新 source／新依賴／新架構
4. 涉及 Risk Cap／Action Authority／正式投資語意
5. 需要使用者裁示
6. 原路徑已失敗一次以上且準備切換方案

與 Minimum Sufficient Effort 的關係

這條規則與既有 Minimum Sufficient Effort 綁定。

應同時優化：

- 解法路徑
- Model
- Effort
- Test Scope
- Token 成本

禁止：

「用更高模型／更多 Token 掩蓋錯誤架構或錯誤路徑。」

若更簡單的 B／C 方案可以以較低模型、較少修改、較少測試達成同等正確性，應優先採用較小方案。

GitHub 落盤：依 PROJECT_RULES §27 同步 PROJECT_RULES.md、docs/DECISIONS.md、docs/HANDOFF.md。完成後新 session 只讀 GitHub 就要能知道「遇到問題時必須先比較多路徑，而不是單一路徑原地試錯」。
```

- **落點**：規則 → `PROJECT_RULES.md` 第 29 節（條文化重述，與原文不一致以本 fence 為準）；`PROJECT_RULES.md` 第 9.1 節 cross-reference；索引 → `docs/HANDOFF.md` 頂部「新永久規則」指標。
- **與其他規則的關係（append-only，撰寫組讀法，單組，⚠️ 未經第二組驗證）**：Minimum Sufficient Model／Effort／Test Scope（DEC-059／078，第 9.1／17 節）**同向綁定**；Silent Autonomous Cruise／Hard Output Gate（DEC-104／118）**正交**（內部比較不輸出，僅 6 種情形回報）；`CLAUDE.md` §-2、§8.4 step 4、v3 §03「嚴禁拋選擇題」**併用**——回報 3 方案必須附 AI 總管推薦方案與原因；**不放寬**任何 Decision Gate／Model Change Gate／Stop Conditions。
- **衝突檢查**：撰寫組僅讀既有第 3、9、17 節相關條文，未發現與本 DEC 牴觸之處（單組、非窮舉）；無舊條文需加刪除線。
- **效力邊界（⛔ 不是實作授權）**：不改 `src/`／`tests/`／`shared/`／`app.py`；不新增資料來源、公式、門檻；不啟動任何 Batch。


### DEC-127｜New UI2 小型 presentation correction（#1001 整體接受）：📊 市場更新 CTA 依 frozen contract 修正順序（不開 Decision Gate）／W-4 Neutral／Info 收斂為 accepted／底部導覽餘裕 presentation-only 小修（客戶 2026-11-03）

> 2026-11-03 補登（ID 取下一個未用號；DEC-126 為上一號）。**來源類別 D：客戶 2026-11-03 指示原文，經總管轉交；下方 fence 內逐字收錄，未改一字**（實作組未見客戶原訊息本身，只見總管轉交之全文；若有出入以原訊息為準）。

- **決策者**：**客戶**（2026-11-03）。｜**效力日期**：2026-11-03 起。｜**範圍**：產品／UX（presentation-only；📊 市場頁更新 CTA 位置、🎯 W-4 驗收收斂、手機底部導覽餘裕）。
- **狀態**：**客戶指示生效**；落地＝本 PR（presentation correction 批）；實作組單組、待總管複驗。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：

```
#1001 整體接受。

1. Market Update CTA order
"NUI2-MARKET-REFRESH-CTA-ORDER" 不需要再開客戶 Decision Gate。
GitHub frozen contract 已有足夠依據：
頁首
→ 🚀 更新今日戰情 CTA
→ 今日結論
→ 3 個核心狀態 tile
目前 CTA 放在第一屏四問最後屬 implementation deviation，不是規格衝突。
請依 frozen wireframe 修正。
注意：
- 不改 VM investment semantics
- 不改 System Action
- 不改 Risk Cap
- 不重新定義「第一屏四問」
- 四問是資訊需求，不代表視覺 DOM 必須固定按 1→2→3→4 排列
- frozen visual contract 優先決定此頁 CTA 位置
修完後更新對應 acceptance / backlog 狀態。

2. W-4 context row
目前 Neutral / Info 的方向接受。
既有 New UI2 Architecture Gate 已定：
- W-4 只能是 lightweight context row / chip
- Neutral / Info 外觀
- 字級低於查詢摘要
- 放在查詢摘要之下
- 不得搶過查一檔
- 不得搶過基本面
- 不得搶過 valuation / company-first research
- 市場技術訊號不得成為單一股票主要判斷
因此不再列為待客戶覆核。
若目前實作符合上述 contract：
直接將相關 backlog / audit finding 收斂為 accepted / implemented。
不得藉此修改 investment semantics。

3. Mobile bottom-nav safety margin
"NUI2-MAIN-RISK-NAV-MARGIN" 請做 presentation-only 小修。
目前 stale / unavailable FAKE 場景僅剩約 2.5px 餘裕，真實字串可能更長，因此不應等 real-data wiring 才處理。
請先比較至少 3 個最小修法，例如：
A. 增加 content bottom padding / safe-area reserve
B. 壓縮非必要垂直 spacing
C. 調整主要風險區塊與下一內容區的 layout
依 PROJECT_RULES §29 選：正確性足夠且低風險 → 最快 → Token 成本最低 → 修改範圍最小
優先避免改字體過小或刪資訊來硬塞。
需要同時考慮：fixed bottom nav height、env(safe-area-inset-bottom) 可用性、390×844、長字串、stale、unavailable、capability-not-provided、judgement-undeterminable
保持目前 Chromium viewport regression。
Safari / Firefox / 真機 / iOS safe-area 尚未實測仍保留 acceptance backlog，不要假裝已驗證。

範圍限制：本批只做 presentation correction。不得碰：System Action Aggregator、Risk Cap runtime、Action Authority、Decision Digest、OneBrain、real-data canonical wiring、Google OAuth runtime、Sheet write、LINE production、production default、新公式、新 threshold、新 source。Old UI / Legacy New UI 不刪。

§27 收尾：所有新的 Rule / Decision / Audit Finding / Limitation / Backlog / Migration Debt / Acceptance Item 必須正式同步 GitHub。尤其：CTA order 從「待判定」改成已依 frozen contract 修正；W-4 從「待覆核」改成符合既有 Architecture Gate；mobile margin 更新實作與仍未驗證範圍。完整落盤。維持 Silent Autonomous Cruise。
```

- **落點**：項 1＝`src/ui2/components/html.py::first_screen_html(cta_first=)`／`market_l1_html`、`src/ui2/shell/css.py`（桌機 grid 列序）；項 2＝既有測試逐點對照（`tests/test_ui2_batch3.py::test_w4_contract_points_are_each_locked_by_a_test`）＋BACKLOG／Checklist 狀態收斂；項 3＝CSS（CTA 列原因與按鈕同列＋`@supports` safe-area 保留量）＋`tests/ui2_viewport/measure_viewport.py` 三條新判定；證據 `docs/vnext/newui2_batch3b/`；BACKLOG §5.1.24 補、PROJECT_STATE §57、Audit Checklist §18、HANDOFF 最末 Safe Handoff。
- **與其他規則的關係（append-only，實作組讀法，單組，⚠️ 未經第二組驗證）**：項 1 **不是**對 Wireframes／Freeze／DEC-117 Q5 的修訂——客戶明示只是確認既有 frozen contract、本批把實作改回該條文（`NEWUI2_WIREFRAMES_2026-11-02.md` §2.1／§2.2 條文**未改**）；項 2 **不是**新條文——W-4 條件早已在 Wireframes §9／Architecture Gate 核准（DEC-123 Q3），本 DEC 只是把「待覆核」登記收斂；項 3 依 PROJECT_RULES §29（DEC-126）多路徑比較。四問（Freeze §0.1.6／Wireframes §1）內容**不變**，只放寬「DOM 須按 ①→④」的讀法（客戶原文明示）；**其餘頁**（持股／我的）的 CTA 位置本批未動（客戶裁示只針對 📊 市場頁）。
- **衝突檢查**：實作組讀過 Wireframes §0.4／§1／§2／§9、Freeze §0.1.6／§16.1、DEC-117 Q5（`FINAL_UI_CONTRACT_FREEZE` 第 937／3132 列引文）、Architecture Gate W-4 條（§9 第 360 行）；未發現牴觸（單組、非窮舉）；無舊條文需加刪除線。
- **效力邊界（⛔ 不是實作授權）**：不授權 System Action Aggregator、Risk Cap runtime、Action Authority、Decision Digest、OneBrain、real-data wiring、OAuth／Sheet、LINE、production default、新公式／門檻／source；Old UI／Legacy New UI 不刪。

### DEC-128｜Presentation Compression ≠ Information Loss：New UI2 四頁 Human UI 不顯示完整 L2／L3、完整診斷集中 👤 我的·資料健康度、Human UI ViewModel ≠ Decision Digest（OneBrain）Context 雙 projection、Active Rule Supersede Cleanup（只留一套 Active Contract）（客戶 2026-11-03）

> 📌 **DEC-129 補（2026-11-03；客戶追加裁示 (14) 優先於 (13) 衝突處；本條原文一字未改）**：下文「0 行 `src/`…／0 條既有測試斷言變更」「不改既有測試」的限制已由 DEC-129 §一、§四取代——保護**已失效 Presentation Contract** 的舊測試斷言應移除／改寫並建立防復活 teeth（真正的資料／語意安全守衛不得降低）；另新增桌機 Account Area 與 Active interpretation 11 點。

> 2026-11-03 補登（ID 取下一個未用號；DEC-127 為上一號）。**來源類別 D：客戶 2026-11-03 指示 (13) 原文，經總管轉交；下方 fence 內逐字收錄，未改一字**（實作組未見客戶原訊息本身，只見總管轉交之全文；若有出入以原訊息為準）。前導指示 (12)（四頁 Gap Audit，Opus High）的原則 1～4 已被 (13) 第 1～8 點完整涵蓋並升格為正式 DEC，不另立。

- **決策者**：**客戶**（2026-11-03）。｜**效力日期**：2026-11-03 起。｜**範圍**：產品／UX／治理（presentation 與 SSOT 清理；**不含**任何資料契約、Digest schema、Risk Cap、System Action、公式、門檻、source）。
- **狀態**：**客戶指示生效**；落地＝本 PR（docs＋極小 docs-consistency 測試；**0 行 `src/`／`shared/`／`app.py` 變更、0 條既有測試斷言變更**）。**程式／既有測試的實際修正是後續 UI correction 批**（`docs/BACKLOG.md` §5.1.26），在那之前，現行 Preview 與下列「待更新測試」仍保留舊 presentation——**那是已登記的 implementation deviation，不是規格**。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：

```
請先重新執行 GitHub Verification Gate，以最新 origin/main 為準。

本批目標不是新增投資功能，而是：
把客戶最新 New UI2 設計方向正式寫入 GitHub，並清除／退役所有與最新方向衝突的現行規則，只留下單一有效 Active Contract。

1. 最新最高 Presentation 原則
正式採用：Presentation Compression ≠ Information Loss
UI 越簡潔，Decision Context 不能越少。簡單，但不能失去判讀能力。
New UI2 Human UI：簡潔、Chart-first、關鍵判斷優先、少量必要 evidence、source / as_of / freshness micro-tag、不堆完整資料清單
完整資料仍保存在 backend Evidence / Decision Context。

2. 四頁正式 Human UI
正式主頁只有：1. 📊 市場 2. 🎯 標的 3. 💼 持股 4. 👤 我的
每頁優先順序：1. 狀態／結論 2. 是否需注意／正式 Action State 3. 主要圖表 4. 關鍵 evidence 5. 必要數字 6. 簡短 source / as_of / limitation

3. 一般四頁不得再顯示完整 L2 / L3 資料
目前若存在下列 Human UI：「為什麼」完整 evidence expander、指標完整清單、raw data、完整 provenance、engineering diagnostic、provider diagnostic、raw JSON、debug dump、大量 Missing 清單、開發者資訊
若其用途主要是：OneBrain input、Audit、engineering / debugging
則從四個主要投資頁的 Human Presentation 移除。
注意：從 UI 移除 ≠ 刪除資料。不得刪：adapter、canonical data、deterministic result、health result、provenance、source、as_of、retrieved_at、freshness、Missing / Stale / Unavailable、tests、OneBrain 未來需要的 evidence

4. Chart-first + Chart SPEC
能用圖表清楚表達：趨勢、比較、強弱、歷史位置、配置、風險 時優先用圖表。
不得：為漂亮新增無正式語意圖、不同單位硬疊、用雙軸造成誤導、讓圖表自行產生 investment semantics
每個主要 chart 附精簡 SPEC，例如："SPEC｜日頻｜TWSE｜資料日 11/03｜缺值不補"
依需求可包含：標的、期間、normalized base、單位、頻率、最新資料日、Missing handling、comparison rule、source。SPEC 必須短。

5. 👤 我的 → 資料健康度
正式新增／預留：資料健康度。完整資料診斷集中至此，不再散落四個投資頁。
至少涵蓋適用的：台股大盤、國際市場、VIX、利率／殖利率／利差、DXY、PMI／景氣、市場廣度、產業、法人／籌碼／融資、個股價格、基本面、估值、持股／portfolio、Risk Cap inputs、System Action inputs、Sheet / settings、其他正式 canonical sources
每項可包含：資料名稱、status、是否取得、source、as_of、retrieved_at、freshness、Missing / failed reason、proxy / estimated、source health

6. 資料健康度分層
Level 1 使用者可讀摘要：✅ 正常、◷ 可能過期、◇ 資料未備、⛔ 來源不可用、⬜ 尚未接線
Level 2 來源／日期／provenance／freshness。
Level 3 developer diagnostics，預設收合。
不得一般曝光：API key、secret、env var 名、raw exception、traceback、module path、credential detail、internal stack

7. UI ViewModel 與 OneBrain Context 必須分離
正式架構：Data / Sources → Validation / Normalization → Domain / Deterministic Logic → Risk Cap / System Action → Complete Evidence Layer
之後分成兩個 projection：
Human UI ViewModel：簡化、Chart-first、關鍵 evidence、少量文字
Decision Digest / OneBrain Context：完整正式 evidence、Missing、provenance、source、as_of、freshness、deterministic results、Risk Cap、System Action、counter-evidence、limitations、cross-page context
永久 invariant：UI 沒顯示的資料，不代表 OneBrain 不得讀。OneBrain 能讀的資料，也不代表 UI 必須全部呈現。

8. OneBrain 不是 UI Summary Bot
OneBrain 未來必須讀完整 Decision Digest，而不是只摘要畫面。
它應整合：市場、標的、持股、portfolio、events、data health / freshness、deterministic rules、Risk Cap、System Action、counter-evidence、所有已核准正式 evidence
並遵守既有 Single Action Authority。

9. Active Rule Cleanup — 本次新增強制要求
這次不能只「新增一條最新規則」然後留下舊規則繼續有效。
請全 repo 搜尋與本次設計相關的舊規格，包括：L1 / L2 / L3 presentation、expander、detailed evidence、raw data、diagnostics、Audit placement、chart / text hierarchy、OneBrain context、Data Health、我的頁、Preview controls
對每一條分類：
KEEP：仍與最新裁示一致。
SUPERSEDE：歷史需要保存，但已不再是 active rule。
REMOVE FROM ACTIVE CONTRACT：與最新裁示衝突，從現行規格／線框／實作 guard 中移除。
MIGRATE：內容仍需要，但位置應改到「資料健康度」或 backend Evidence / Digest。

10. 只允許一套 Active SSOT
完成後："PROJECT_RULES"、New UI2 Architecture、Wireframes、Presentation Contract、tests / guards 不得同時存在兩套互相矛盾的有效規則。
如果舊文件因 audit / append-only 要保留歷史：必須明確標：SUPERSEDED / HISTORICAL — NOT ACTIVE，並指向最新 DEC / Contract。
不得要求新 session 自己猜「哪一段比較新」。

11. DECISIONS 歷史不得破壞
"docs/DECISIONS.md" 維持 append-only。不得刪除或改寫舊客戶 Decision。
正確方式：新增最新 Decision；舊 Decision 標示 superseded 關係；最新 Decision 明寫取代範圍。
歷史證據保留，但只能有一套現行有效讀法。

12. Tests / Guards 也要清理
若現有測試仍強制：L2 / L3 必須出現在一般 UI、expander 必須存在、舊 presentation hierarchy、舊 diagnostics placement
不得為了讓舊測試通過而保留錯誤 UI。
應：先確認是舊 contract test → 更新／移除過期 assertion → 新增最新 contract teeth test。
不得降低真正的資料／語意安全守衛。

13. 本批最多三項
1. 將最新 Presentation / Data Health / OneBrain Projection 原則正式落 GitHub。
2. 全 repo 做 Active Rule Supersede Cleanup，確保舊衝突規則退出 active SSOT。
3. 產出後續 UI correction backlog / Safe Handoff。
本批以 governance / contract cleanup 為主。不要順手大量重寫 UI。

14. Model Gate
若只是 docs、contract、wireframe、presentation rule、supersede cleanup、backlog、guard specification：維持 Claude Sonnet 5.5 + Medium。
若碰：Decision Digest schema、Risk Cap、System Action semantics、新資料 contract、新 external source、新公式／threshold、跨 domain investment semantics：立即 STOP。回報：🟡 Model / Effort Change Gate 建議 Claude Opus 5.5 + High。

15. Durable Persistence Gate
至少同步：PROJECT_RULES.md、docs/DECISIONS.md、docs/BACKLOG.md、docs/PROJECT_STATE.md、docs/HANDOFF.md、New UI2 Architecture、Wireframes / Presentation Contract、Data Health contract、OneBrain / Decision Digest cross-reference、relevant tests / guards contract
完成後必須證明：新 session 只讀 GitHub，就只能得到一套最新有效規則，不會重新照舊 L2 / L3 UI 施工。
全程 Silent Autonomous Cruise。完成整批後再回報。
```

#### 一、一句話（撰寫組濃縮；與客戶原文不一致時以 fence 為準）

**簡單，但不能失去判讀能力。** 四個正式投資頁（📊 市場／🎯 標的／💼 持股／👤 我的）的 Human UI 只放「結論／Action State → 主要圖表 → 關鍵 evidence → 必要數字 → 短 source／as_of／limitation micro-tag」；完整 L2／L3、raw、provenance、engineering／provider diagnostic 從 Human Presentation 移除，**但資料一筆不刪**，完整診斷集中到 👤 我的·資料健康度（三層），完整 evidence 留在 backend Evidence／Decision Digest 給 OneBrain／Audit／QA。UI ViewModel 與 Decision Digest 是同一份 Complete Evidence Layer 的**兩個 projection**，永久互不決定對方。

**唯一現行有效讀法**＝`docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`；與其他文件衝突時，以該文件與本 DEC 為準。

#### 二、取代範圍（逐條；S21 起接 `FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` §1 的 S1～S20；舊文原文一字不改，只加 📌）

> 分類碼：**SUPERSEDE**＝歷史保存、不再是 active rule｜**REMOVE**＝從現行規格／線框／guard 的 active 內容移除｜**MIGRATE**＝內容仍需要、落點改到「資料健康度」或 backend Evidence／Digest。實查（撰寫組，單組）：每列的條文位置皆已讀原文確認存在。

| # | 舊條文（DEC／契約＋章節） | 被取代的部分 | 分類 | 仍有效的部分 |
|---|---|---|---|---|
| **S21** | `PROJECT_RULES.md` §24.2「第一屏三層答不出＝FAIL」；`docs/governance/UI_VISUAL_FIDELITY_GATE.md` §1-3、V7、§8 報告格式「第三層＝_」；**DEC-109 四**（第一屏五問＋「第一眼／第二眼／第三層答不出＝FAIL」） | 「第三層＝頁內摺疊」的判準 | SUPERSEDE | 第一屏五問、「第一眼／第二眼」、Gate 其餘 V 項、Decision Density／Text Reduction（V1～V6、V8～V11） |
| **S22** | **DEC-091 §一** Level 3「查看依據」展開（原始數字、計算邏輯、來源、freshness、missing reason、門檻、工程診斷）；**§二**「📖憑什麼：每個重要判斷旁放『查看依據』，點開才顯示」；「🩺資料健康：小型狀態入口…點擊才展開」的**本體** | 頁內 Level 3／頁內憑什麼展開；資料健康本體 | SUPERSEDE（憑什麼）／MIGRATE（資料健康本體→👤 資料健康度） | Level 1／Level 2 定義；固定四主導航 |
| **S23** | **DEC-081 第 7 點** 📊 大盤「展開理由、問 AI／查看依據」之「展開理由」；**Q4=C** 🩺 資料中心分流；**DEC-072／DEC-076 §6**、`PROJECT_RULES.md` §19.2 的「資料中心」責任方向 | 「展開理由」頁內；「資料中心」作為獨立責任面 | SUPERSEDE（展開理由）／MIGRATE（資料中心責任→👤 我的·資料健康度） | 互動控制完整性其餘（更新、搜尋、Sheet 選擇／綁定、持股綁定、重新載入）全部維持；DEC-092 不設第五頁 |
| **S24** | **DEC-105 第 4 點**＋**DEC-117 Q2=A′**：「指標危險度」指路句必須指向「指標明細（16 項）」展開區 | 指路目標＝頁內 16 項 expander | SUPERSEDE | 能力不消失：16 項明細 MIGRATE→Evidence／資料健康度；指路句改指向 📊 內簡短 evidence 或 👤 資料健康度（⚠ PROVISIONAL (b)） |
| **S25** | **DEC-117 Q3=A**（圖「▸ 為什麼／來源／限制／去哪補」、tile「查看依據」摺疊）；**Q6**（主要風險完整原句保留在摺疊）；**Q8**（圖 C 原句→「為什麼」、⚡ 展開清單） | 摺疊標籤／落點 | SUPERSEDE（摺疊）／MIGRATE（完整原句、清單→Evidence） | Q6 退化句逐字外露；Q8「資訊只能下沉、不得刪」精神（＝不刪資料）；Q1、Q4、Q5 桌機順序、DEC-119 |
| **S26** | **DEC-109 五**（圖表標頭「▸ 為什麼／來源／限制／去哪補」）、**六**（詳細文字下沉＝頁內預設收合）、**七**（「現在／為什麼／去哪補」頁內 L3 可展開）；`PRESENTATION_CONTRACT_vNext_2026-10-29.md` §3 L3 列、§4 摺疊入口、§5 下沉清單位置、§7 資訊守恆（卡面∪摺疊∪expander）、§8 第 2／5 點的位置、§11 R7、§12.1 市場下沉列、§16 對應列、§17 落點欄 | 頁內收合／展開落點 | SUPERSEDE（位置）／MIGRATE（內容） | 「資訊必須存在、可追溯」「工程術語必須保留」；§2 Visual Budget；§8 Missing ≠ 0；§9 UI 簡化不得減少 context；§18 工程字樣＝0（擴及四頁全部 Human UI） |
| **S27** | **DEC-111／DEC-112**（三要素卡面「▸ 詳細」、完整原文不得只剩 hover）**對 New UI2** | 對 New UI2 的「▸ 詳細」機制 | SUPERSEDE（僅 New UI2） | Legacy 卡面凍結（DEC-019／020）；「不得藏在 hover」精神 |
| **S28** | **DEC-122 客戶 §9**（市場 L2／L3）、**§22**（持股 L2：fundamental、risk、chip、evidence、rule IDs）、**§25～§27**（Audit 區：Data Freshness／System Information；Digest Viewer L2 raw structured snapshot） | 頁內 L2／L3；Audit 區頁內 raw／Freshness／System Information | SUPERSEDE（頁內形態）／MIGRATE（Data Freshness、System Information、Digest raw → 👤 資料健康度；evidence／rule IDs → Evidence／Digest） | §7～§8、§11（Slice≠Context）、§14～§15、§19～§21、§23；§22 L1 八欄；§26 Registry 唯讀；§27 Viewer L1 句型與 secrets 禁令 |
| **S29** | `FINAL_UI_CONTRACT_FREEZE_2026-11-02.md` §2.0 三層、§2.1～§2.4 的 L2／L3 列、§10「必須外露（L2）」的完整 calculation、§12.2 Digest Viewer L2 raw、§16.1～§16.4 線框「↓ …L2／L3 摺疊」、§16.5 縮短字句後的「下沉」落點 | 同上 | SUPERSEDE／MIGRATE（§16.5 落點） | §0.1、§1、§5、§6～§9（field-level freshness 保留）、§13～§15、§16.5「⛔ 自行移出必要項→Decision Gate」 |
| **S30** | `NEWUI2_WIREFRAMES_2026-11-02.md` §0.1 三層定義；§2.1／§2.2 `▸ 為什麼（L2）`／`▸ 指標明細（16 項）（L3）`／`▸ 原始資料表／工程診斷（L3）`；§3.1 `▸ 完整 6 欄表／跨季趨勢（L3）`；§3.2 `▸ 完整分析（L3）`；§3.3；§4.1／§4.2 `▸ L2：…rule IDs…`／`▸ L3：原始明細`；§5.1／§5.2 `▸ L2／L3：Digest raw snapshot、Registry 明細、工程診斷` | 這些 ▸ 行與其頁面段落（**ASCII 線框的版面其餘部分仍有效**） | REMOVE（from active）／MIGRATE | §1 第一屏四問、§9 W-1～W-11、**DEC-127 的 CTA 順序與 W-4**、§6 狀態矩陣 |
| **S31** | `FINAL_UI_CAPABILITY_MAP_2026-11-02.md` 落點欄的「市 L2／L3」「標精 L2／L3」「標查 L2／L3」「持 L2／L3」「我A L2／L3」（含 M06、M11～M17、T、H、E 系列） | 落點欄 | MIGRATE | **能力一個都不消失**；Stage J 第 6 條計算不變（只換落點） |
| **S32** | `NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md` §15 C2「每頁 L1／L2／L3」、§17「⛔ L2／L3 插隊」、§19 第 2 點「L2 位階說明」；`NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md` C2「L1／L2／L3」 | 驗收口徑 | SUPERSEDE／MIGRATE | 「市場 L1 之前無 expander」→擴為「四頁整頁 0 個完整 evidence expander」；其餘驗收項 |
| **S33** | `NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` M1b／M15～M17（L2 落點）、E13／E14、§11-6（🎯 指引「說明見 📊『為什麼（L2）』」）、§11-9（expander「Preview 控制（資料來源）」） | 落點與指引 | MIGRATE／REMOVE／SUPERSEDE（Preview 控制位置） | 四頁 canonical 對映、跨頁一致性 teeth、no-write proof、白名單捏造守衛 |
| **S34** | `ME_PAGE_DRAFT_2026-10-25.md` 資料健康→🩺；BACKLOG `DH-DATA-CENTER`、`UIX-DATACENTER-CONTROLS`、`NEWUI-STAGE-D8-DATA-CENTER`、`NEWUI-STAGE-D10-SHARED-COMPONENTS`、`UIX-MKT-ENTRY-BUTTONS`（🩺 資料中心規格待辦）、`NUI2-REALFEED-REGIME-L1-BRIEF`（完整位階說明放 📊 L2） | 🩺 資料中心作為獨立面；位階說明放 📊 L2 | SUPERSEDE（HISTORICAL）／MIGRATE | 待辦能力併入 `NUI2-DATA-HEALTH-*`（BACKLOG §5.1.26） |
| **S35** | （新規則，非取代）**Preview 控制位置**：現行殼把「Preview 控制（資料來源／fake 場景）」畫成頁面 expander（`src/ui2/shell/app.py`），**無任何既有條文規定其位置**；依 (13) 與 (12)-3，視為 **implementation deviation** | — | 新增規則（見 Active Contract §6） | `ALLOWED_UI2_WRITES` ui2_ 前綴、NUI2-PREVIEW-CONTROL-AXES（cutover 前移除） |

#### 三、不被取代（明列；一律繼續有效）

- **資料語意**：DEC-124（五態 OK／Missing／Stale／Unavailable／Not Evaluated 與三軸〔資料語意／判定語意／能力可用性〕、`⬜ 尚未提供`＝capability、Risk Cap `⬜ 無法判定`＝Unable to Determine）、Freeze §5 全站字樣及 `shared/ui2_contract/text.py`、`tests/test_ui2_guards.py` 三軸字樣守衛：**一字未動**（資料健康度符號見下 PROVISIONAL (a)——**不外溢**）。
- **Single Action Authority**（Freeze §6）、Risk Cap Enforcement 規則形狀（§8）、No Uncalibrated Probability（§7）、Single 權威 System Action；OneBrain 不得覆寫 Action／Risk Cap（客戶第 8 點同向）。
- **Presentation Slice ≠ Decision Context**（Freeze §13）、Headless Digest（§14）、OneBrain 只讀 Digest（§15）：本 DEC 只是把它們命名為「雙 projection」並升格為永久 invariant。
- **DEC-127**（📊 CTA 順序＝今日結論之前、W-4 Neutral／Info、手機底部導覽餘裕）、Wireframes §1 四問、§9 W-1～W-11、W-4 全部條件。
- **DEC-109 十五～十七**（UI 簡化不得降低 AI Decision Context；Data View ≠ Decision Context ≠ AI Output）、Presentation Contract §9「UI 簡化不得減少的清單」。
- **field-level micro-tag**（Freeze §9：每卡 value／state／as_of／source）、Missing ≠ 0、工程字樣＝0（擴大）、Decision Density／Text Reduction、所有資料／語意安全 guards（G2／G2F／G4／G9、白名單 teeth、no-write proof、`test_vm_creates_no_actions_and_no_forbidden_terms`）。
- **DEC-121 Q2=B**（候選 Top 10＋查看全部＋CSV＝使用者功能）、**DEC-081 Q2-2** 卡面客戶措辭、**DEC-017 葉1 ②**（兩套刻度常駐揭露）、**DEC-125**（中性命名、市場主軸兩條）、**DEC-126／§29**（多元解法）。
- **Legacy New UI／Old UI**：不刪、不改（DEC-019／020／083）；其測試（`test_uim_market_page.py` 等）是 **Legacy-only，不是 New UI2 active contract**，本 DEC 不動。
- **DEC-123 Q1～Q4**（New UI2 路線、Preview 策略 Q1=A、Cutover Q4=A）：本 DEC 不改路線，只補 Preview 控制的**位置**規則。

#### 四、⚠️ PROVISIONAL 判讀（AI 總管暫定；**不是客戶裁示**；客戶可推翻）

> 📌 **已由 DEC-130 升為正式 Active（客戶 2026-11-03 (15) 覆核；(a) 為「有條件同意」——語意邊界以 DEC-130 §二為準，(b)(c) 同意並補客戶新增限制）**。下文 (a)(b)(c) 原文**一字未改**，保留為歷史（當時為 AI 總管暫定、非客戶裁示）；自 DEC-130 起**不再是 PROVISIONAL**，PR 描述不必再標 PROVISIONAL。(d) Re-open 模板仍保留作為日後推翻用格式。⚠ 若本段 (a) 的字面與 DEC-130 §二不一致，**以 DEC-130 fence 與 §二為準**（例：本段 (a)「`⬜ 尚未接線`＝capability」維持；新增「資料健康度同一列須拆兩欄」）。

> 以下四項是為了讓 Active Contract 能「只剩一套」而由 AI 總管暫定的**讀法**，其中 (a) 觸及資料語意字樣、(b)(c) 屬灰色地帶。**它們不得被引用為「客戶已核准」**；客戶覆核前，凡依據這些判讀的施工，PR 描述須標註「PROVISIONAL」。

- **(a) 資料健康度 Level 1 符號 ✅ ◷ ◇ ⛔ ⬜ 是「僅用於 👤 我的·資料健康度面」的別名**，對映既有資料語意：✅ 正常＝OK、◷ 可能過期＝Stale、◇ 資料未備＝Missing、⛔ 來源不可用＝Unavailable、⬜ 尚未接線＝capability 尚未接線。**不新增第 6 個資料語意態**；**不改**全站 DEC-124／Freeze §5.1 既有字樣、`text.py` 與其 guard；全站替換需客戶另裁示。**`⛔` 在 Freeze §5.3 舊義為「功能未接」**——**限定在資料健康度面內以新義（來源不可用）為準並於該面加註**，**不外溢**到其他頁（其他頁 `⛔ 未接線` 仍為舊義）。⚠ 另有張力：`CLAUDE.md` §1.A-4「紅＝系統真錯誤」與 `⛔ 來源不可用` 的色未在客戶原文指定——Active Contract 暫定「⛔ 來源不可用＝紅（沿 Freeze §5.1 Unavailable 紅）」。
- **(b) 灰色地帶**：① 👤 我的內的 **Audit／Decision Digest Viewer／Rule Registry 入口＝「稽核面」**，保留在 👤（不是四個主要投資頁的一般 Human Presentation）、預設收合、不外露工程字樣；Digest Viewer 的 **L2 raw structured snapshot** 移到資料健康度 Level 3（developer diagnostics，預設收合）。② 🎯「選股條件（一行摘要）」與「查看全部候選／CSV／查看此檔」是**使用者功能**、非 evidence，保留（DEC-121 Q2=B）。③ 「指標危險度」指路句改指向 📊 內簡短 evidence 或 👤 資料健康度（不再指向 16 項 expander）。④ 全站「一行資料狀態入口」（DEC-091 §二）可保留（點擊導向 👤 資料健康度），完整診斷本體不留在四個投資頁。
- **(c) Preview 控制**：移到**開發／測試專用面**（`?ui2_dev=1` 之類 query param 才顯示；明顯標示「非產品內容」；session key 維持 `ui2_` 前綴；**不用 sidebar**〔與桌機左導覽衝突〕；**不開第五導覽項**〔違 DEC-109 X／客戶 (5)-7〕）。FAKE／Real 切換保留供測試，不屬 production presentation contract。AppTest 對 query param 的支援（1.56／1.59）**未驗**，實作批須先實測；備案＝session_state 預設值。
- **(d) Decision Re-open Proposal 格式**：若 (a)～(c) 任一與客戶本意不符，客戶只需回覆 `Re-open DEC-128 (x)：改為 …`；總管將以新 DEC 取代該項（本 DEC 原文與其餘各項不動），並依下列模板開案——**Decision Re-open Proposal｜項＝(a/b/c)｜現行暫定讀法｜客戶覆核後可能的替代讀法｜受影響文件／測試（見 BACKLOG §5.1.26）｜AI 總管推薦（附理由）**。

#### 五、與其他規則的關係（撰寫組讀法，**單組、未經第二組獨立驗證**）

- `CLAUDE.md` §-1.5.D v3 §03-2 ①（UI 結構變更草稿先行）：**不受影響**。本 DEC 是客戶親自指示「移除」，且本批**不改任何 UI 程式**；後續 UI correction 批若涉及新版面（例如資料健康度的區塊版型、桌機兩欄），**仍須先出文字線框草稿**（BACKLOG P6）。把壞畫面修回 contract（A-8「修正錯誤 vs 改變設計」）不在此限。
- `PROJECT_RULES.md` §25 SSOT 位階：本 DEC 為最新客戶 DEC，依 §25.3 只在**明確點名或直接牴觸處**取代舊條文——上表即「點名」清單；單組窮舉，**「取代範圍只有 S21～S35」是單組結論**（見下「揭露」）。
- `PROJECT_RULES.md` §29（多元解法）：新增第 30 節（本 DEC 條文化）；A／B／C 路徑比較見 `docs/BACKLOG.md` §5.1.26。
- **ADR-OB-001／OneBrain 邊界**：第 7～8 點與 `ONEBRAIN_ARCHITECTURE_2026-10-31.md`、Freeze §15 同向；「OneBrain 讀完整 Digest 而非 UI」不新增任何 Digest schema 欄位（Digest 是否補 data health／freshness 區塊＝`NUI2-DIGEST-DATAHEALTH-XREF`，需另案 Opus High Gate，**本 DEC 不授權**）。

#### 六、揭露與效力邊界（⛔ 不是實作授權）

- **獨立稽核**：取代清單以兩份獨立稽核（組 A 從 contract 往下、組 B 從畫面往上）為輸入，撰寫組實查抽驗其引用位置；**兩組皆單組、非窮舉**；組 A 的 DEC-091 §一行號（966～970）實為 972，無實質影響。
- **掃描範圍（誠實揭露，單組）**：撰寫組以 `▸ 為什麼`／`指標明細（16 項）`／`原始資料表／工程診斷`／`查看依據` 反向 grep 全 `docs/`、`PROJECT_RULES.md`、`CLAUDE.md`、`PROCESS.md`：New UI2 主線文件已逐檔處理；Legacy New UI 時代的 Phase3／4／5 線框、`PRESENTATION_MIGRATION_PLAN`、`NEWUI_D25_A_FOUR_PAGE_SPEC`、`NEWUI_D25_UIT_WIREFRAME` 已加頂端橫幅；其餘 Legacy 時代文件與證據／量測檔（`d25_wireframes/*.html`、`phase4_market/`、`phase5_target/`、`visual_fidelity/` 等）**未逐檔加橫幅**，以 Active Contract §10 一列統一宣告「對 New UI2 不是 active rule」。**此掃描非窮舉、未經第二組獨立驗證**（`NUI2-ACTIVE-CONTRACT-INDEPENDENT-AUDIT`）。
- **不授權**：Decision Digest schema／runtime、OneBrain runtime、Risk Cap、System Action 語意與 Aggregator、新資料 contract／source／公式／threshold、real-data 擴大、切 production default、刪 Old UI／Legacy New UI；本批**不改任何 UI 程式與既有測試**。
- **已知偏離（登記，非規格）**：現行 Preview 仍有 L2／L3 expander、工程字樣、題號鷹架、Preview 控制 expander（見 BACKLOG §5.1.26 與 Active Contract §9）——以 Active Contract 為準的 UI correction 批處理。
- **舊 DEC 加註**：DEC-072／076／081／091／105／109／111／112／117／122 條頭已加 `📌 SUPERSEDED IN PART BY DEC-128` 行（原文一字未改）；`docs/vnext` 各文件加 `⛔ SUPERSEDED / HISTORICAL — NOT ACTIVE（DEC-128…）` 橫幅。

### DEC-129｜客戶追加裁示（併入 DEC-128 同批；優先於 (13) 衝突處）：桌機左側 Navigation Rail 加入 compact Account Area（登入／Authentication State）；強制移除不再適用的 Active Rules（含 guards／tests／renderer 假設）；Active interpretation 11 點（客戶 2026-11-03 (14)）

> 📌 **手機底部導覽規則（「手機仍固定四格底部導覽」）由 DEC-134 取代；桌機 Account Area、四頁 IA 不變（原文保留）**（2026-11-04 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-134）；其餘條文仍有效）。

> 2026-11-03 補登。**編號選擇（依 repo 慣例說明）**：repo 慣例是「每一則客戶指示訊息一個 DEC」（DEC-122／123／125／126／127 各自獨立），(14) 是 (13) 之後的**獨立追加訊息**且自述「優先於前一份提示語中任何衝突內容」，故另立 DEC-129，而非改寫 DEC-128（DEC-128 原文不動，僅在條頭加 📌）。**來源類別 D：客戶 2026-11-03 追加裁示 (14)，經總管轉交；下方 fence 逐字收錄，未改一字**（實作組未見客戶原訊息本身）。
- **決策者**：**客戶**（2026-11-03）。｜**效力日期**：2026-11-03 起。｜**範圍**：產品／UX／治理（導覽結構、Active Rule 清理、tests／guards 清理）。
- **狀態**：**客戶指示生效**；落地＝與 DEC-128 同批（docs＋測試清理）；UI 程式尚未改（後續 UI correction 批，`docs/BACKLOG.md` §5.1.26）。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：

```
追加裁示，請立即併入剛才的 New UI2 設計方向批次。

目前為安全停點；此追加裁示優先於前一份提示語中任何衝突內容。

1. Desktop 左側加入登入與狀態

New UI2 桌機左側 Navigation Rail 正式加入 compact Account Area。

未登入：
- "登入"
- "⬜ 尚未登入"

已登入：
- "✅ 已登入"
- 必要使用者識別
- 登出入口

若已有正式 Sheet / Portfolio selection contract，可顯示一行 compact status；不得自行增加新語意。

Account Area：
- 不算第五頁
- 不增加第五個主導航
- 不顯示 secret / credential
- Authentication State 必須來自正式 auth contract
- 不得從 URL/query parameter 猜登入狀態

桌機結構：
Product / Logo
→ Login / Auth Status
→ 📊 市場
→ 🎯 標的
→ 💼 持股
→ 👤 我的

手機仍固定四格導航；登入主要由「👤 我的」承接。

2. 強制移除不再適用的 Active Rules

本批不是只新增最新規則。

請全 repo 搜尋本次範圍的舊規則／舊 contract／舊 wireframe／舊 guards／舊 tests。

只要與客戶最新裁示：
- 不一致
- 已被取代
- 不再適用
- 會讓未來 AI 誤解
- 會讓實作重新長回舊 UI

就必須退出 Active SSOT。

可以直接移除／改寫的 Active 內容
包括適用的：
- PROJECT_RULES 現行條文
- New UI2 active contracts
- wireframes
- presentation specs
- navigation specs
- active backlog instructions
- guards
- tests assertions
- renderer assumptions

例如舊規則若仍要求：
- L2/L3 必須顯示於四個主要頁面
- expander 必須存在
- raw diagnostics 必須在主頁
- 完整 Missing list 必須在主頁
- OneBrain 只能讀 UI slice
- 登入位置與最新 Navigation Contract 衝突

這些不得繼續保留為有效規則。

3. 歷史 Decision 不直接刪除

"docs/DECISIONS.md" 維持 append-only。

舊 Decision 若已被最新裁示取代：
明確標記：
"SUPERSEDED / HISTORICAL — NOT ACTIVE"
並指向新的 Decision / Active Contract。

歷史可以保留作 audit evidence，但：
不得再參與現行實作判定。

4. 不要留下兩套有效讀法

完成後不得出現：
「舊規則還寫 L2/L3 要顯示，但新規則又說不要顯示」
這種狀態。

新 session 讀 GitHub 時，必須只能得到一套 Active interpretation：
1. Presentation Compression ≠ Information Loss
2. 簡單但不能失去判讀能力
3. Chart-first
4. 主要圖表提供精簡 SPEC
5. 四個主要投資頁不承載完整 L2/L3 diagnostics
6. 完整 Evidence 仍保留
7. 👤 我的 → 資料健康度
8. UI ViewModel ≠ Decision Digest
9. OneBrain 讀完整正式 Evidence
10. Desktop 左側有 Login + Auth Status
11. Mobile 仍只有四格導航

5. Tests / Guards 同步清除舊假設

若舊 test / guard 是為了保護已失效的 Presentation Contract：
不得為了讓測試綠而保留錯誤 UI。

應：
舊 assertion 移除／改寫
→ 建立最新 contract assertion
→ 加 teeth test 防止舊行為復活。

不得降低資料完整性、missing semantics、Risk Cap、System Action 等真正安全守衛。

6. 本批仍不要大規模施工 UI

本批優先完成：
1. 最新規則 Durable Persistence
2. 不適用 Active Rules Cleanup
3. 最新 UI Correction Backlog / Safe Handoff

完成後再進 UI correction implementation。

Model / Effort：Claude Sonnet 5.5 Medium

若碰到：OAuth/auth architecture 本體、Decision Digest schema、Risk Cap、System Action、新資料 contract、新 source、新公式／threshold
立即 STOP → Opus 5.5 + High Model / Effort Gate。

全程 Silent Autonomous Cruise。
```

#### 一、與 DEC-128 的關係（優先序與取代）

- **(14) 優先於 (13) 的衝突處**。唯一實質衝突：DEC-128／我先前的「本批不改既有測試斷言」限制——(14) 第 2、5 點明確要求**移除或改寫**「保護已失效 Presentation Contract」的舊斷言並建立最新 contract assertion＋防復活 teeth，故該限制**作廢**（DEC-128 條頭已加 📌；其餘原文不動）。
- **新增（非取代）**：桌機左側 Navigation Rail 的 **compact Account Area**（見 §二）；**Active interpretation 11 點**（客戶 (14) §4，已置於 Active Contract 開頭）。
- **取代（S36）**：`NEWUI2_WIREFRAMES_2026-11-02.md` §0.4「桌機：左側欄 4 項…UI2 只重做元件，不改導覽結構」中「桌機左側只有 4 項、不改導覽結構」的部分——改為「Product／Logo → Login／Auth Status（compact Account Area）→ 📊🎯💼👤」；手機底部固定四格**不變**。DEC-097／DEC-123 的固定四頁 IA 不變（Account Area **不是第五頁、不是第五個主導航**）。
- **Active 退出（S37）**：凡要求「L2／L3 必須顯示於四主頁」「expander 必須存在」「raw diagnostics／完整 Missing list 必須在主頁」「OneBrain 只能讀 UI slice」或與本導覽衝突的登入位置之敘述，一律 `SUPERSEDED / HISTORICAL — NOT ACTIVE`。實查：「OneBrain 只能讀 UI slice」字面在 repo 現行文件 **0 命中**（Freeze §0.1.3-6／§15 的現行寫法本來就是「OneBrain 只讀完整 Digest」，與 DEC-128 同向）；**不存在需移除的該句**，防復活由 Active Contract §7～§8 與測試 teeth 承擔（單組 grep 結論）。

#### 二、桌機 Account Area 規格（客戶原文的條文化；與 fence 不一致以 fence 為準）

| 項目 | 規格 |
|---|---|
| 桌機結構（1440） | Product／Logo → Login／Auth Status → 📊 市場 → 🎯 標的 → 💼 持股 → 👤 我的 |
| 未登入 | 「登入」＋「⬜ 尚未登入」（**客戶明示採用此字面**） |
| 已登入 | 「✅ 已登入」＋必要使用者識別＋登出入口 |
| 可選一行 | Sheet／Portfolio selection compact status——**僅限已有正式 Sheet／Portfolio selection contract**，⛔ 自行增加新語意 |
| 禁止 | 算第五頁／增第五個主導航／顯示 secret／credential／從 URL／query parameter 猜登入狀態 |
| 狀態來源 | Authentication State 必須來自**正式 auth contract**。⚠ **目前 repo 尚無 New UI2 用的正式 auth contract**：Preview 殼的「帳戶狀態」`ui2_account` selectbox 只是**開發面 FAKE 場景**（signed_out／signed_in／unavailable），**不是 auth contract**，不得被讀成登入狀態來源。真實 auth 架構（OAuth 本體、session、token）屬 **Opus 5.5＋High Gate**——本 DEC 只記「未來需正式 auth contract」（`NUI2-AUTH-CONTRACT-GATE`），**不設計它** |
| 手機 | 仍固定四格底部導覽；登入主要由 👤 我的承接 |

#### 三、`⬜ 尚未登入` 字樣與既有 BACKLOG 項的處理

`NUI2-ME-SIGNEDOUT-CLASSIFICATION-REVIEW`（BACKLOG §5.1.24）曾記載「Wireframes §5.1 例示的 `⬜ 尚未登入` 字面未採用——既有 Missing 字樣表守衛要求含『資料未／資料日』，擴充屬放寬守衛」。**客戶 (14) 明示採用該字面**：該項**標為已由客戶裁示收斂**（BACKLOG 該列加 📌）。**字樣表守衛（`shared/ui2_contract/text.py`、`test_ui2_guards.py` DEC-124 段）本批不放寬、不改**；擴充（為此字樣建立明列的許可項並維持三軸互斥與「未知字樣 raise」）留給 UI 批（`NUI2-AUTH-STATUS-TEXT-GUARD`），且須維持 DEC-124 三軸語意——`⬜ 尚未登入` 的語意歸類（確定的連線事實 vs capability）由該批沿用 `NUI2-ME-SIGNEDOUT-CLASSIFICATION-REVIEW` 的判讀處理，**不新增第 6 個資料語意態**。

#### 四、tests／guards 清理原則（客戶 (14) §2、§5）

- 只動「**保護已失效 Presentation Contract**」的斷言（強制 L2／L3 expander 存在、①～④ 題號可見、Preview 控制 expander 標題、完整 Missing list 在主頁、登入位置舊假設）：**移除或改寫為不強制舊行為**，並建立最新 contract assertion。
- UI 尚未改、無法即時通過的**新 UI 行為斷言**寫成 `pytest.mark.xfail(strict=True, reason="待 UI correction 批 P#，DEC-128")`——strict 使 UI 修好（XPASS）時測試轉紅、**必須移除 xfail**。
- ⛔ 不得用 skip／xfail 隱藏任何現有資料／語意安全測試；⛔ 不放寬 DEC-124 三軸、G2／G2F／G4／G9、no-write proof、白名單不變量、禁用字樣等守衛。
- 被改的舊測試逐一列於 `docs/BACKLOG.md` §5.1.26「已改／移除的舊測試」（含理由）與 `docs/PROJECT_STATE.md` §59；新 strict xfail teeth 列於同處。

#### 五、揭露與效力邊界（⛔ 不是實作授權）

單組撰寫、未經第二組獨立驗證。不授權：auth／OAuth 架構本體、Decision Digest schema、Risk Cap、System Action、新資料 contract／source／公式／threshold、production default、刪 Old UI／Legacy New UI。Account Area 的**實作**（UI 版型）仍須先出文字線框（v3 §03-2 ①；BACKLOG P7）。

#### 七、補充取代範圍（獨立稽核 `ca6209c8` 後增補，S38～S44；2026-11-03；append；以上各節原文不動）

| # | 舊條文 | 被取代／更正的部分 | 分類 | 仍有效 |
|---|---|---|---|---|
| **S38** | `NEWUI2_ARCHITECTURE_GATE` §4.2-6、§9.2 G3、§9.4：「VM `context`（將來＝Digest）」 | 讀法更正：`context` 是 Human UI 全量，**不是** Decision Context／Digest（Active Contract §8） | SUPERSEDE（讀法） | 四情境等價測試的判準與 mutation |
| **S39** | `UI_VISUAL_FIDELITY_GATE` A8「下沉清單全在 L3」、V11「所有 L3 內容在手機可點開」 | 對 New UI2 不得再逼出頁內 L3；落點改 Evidence／資料健康度 | SUPERSEDE／MIGRATE | A8 其餘（外露層 0 段 > 32 字非客戶原句）、V11「0 項資訊只活在 title」、Legacy 判準 |
| **S40** | `PRESENTATION_CONTRACT_vNext` §12.2／§12.3 的頁內 L2／L3 落點、§9 判準 (a) 的「L3」 | 同上 | SUPERSEDE／MIGRATE | 「不得全部第一層外露」清單、Top-N、查看全部 |
| **S41** | DEC-123 A-3「expander 層級（L1／L2／L3 摺疊層級）」；`ARCHITECTURE_GATE` §6.1 目錄註解；BACKLOG `NUI2-COMPONENT-GAP`「expander 層級規範」 | New UI2 元件不再需要 L1／L2／L3 expander 層級規範 | SUPERSEDE | 其餘元件缺口（chart container、mobile stack、Risk Cap alert、Semantic Chip…） |
| **S42** | DEC-092 Q3 等、DEC-108、DEC-101 的「收合到『查看依據』」通則 | 頁內收合落點（僅 New UI2） | SUPERSEDE／MIGRATE | 各 DEC 的實質裁示（第一層 3–5 項、視覺原則其餘、XV-H3） |
| **S43** | Wireframes §7 W-1 表列「桌機左側欄 4 項」、§4 W-6「其餘欄下沉 L2」；Freeze §5.1／§5.3 表中「留 L2」 | 桌機 Account Area（DEC-129）；L2 落點→資料健康度 Level 2 | SUPERSEDE／MIGRATE | 手機四格、W-6 欄位集、子原因符號本身 |
| **S44** | Legacy 時代未加橫幅的文件：`INTERACTION_COVERAGE_MATRIX`、`NEWUI_STAGE_B_DRAFT`、`MARKET_PAGE_DECISION_GATE`、`NEWUI_D25_B_COVERAGE`、`VNEXT_PRODUCT_BLUEPRINT` | 對 New UI2 非 active（頁內 L2／L3、查看依據） | SUPERSEDE（HISTORICAL） | Legacy 凍結 |

- **S32 用語澄清（消除與 PROVISIONAL (b)① 的張力）**：S32 的「四頁整頁 0 個完整 evidence expander」改讀為「**📊🎯💼 三個投資頁整頁 0 個完整 evidence expander；👤 的稽核面入口（Digest Viewer L1、Rule Registry，預設收合）為明列例外**，但 👤 同樣不得有「為什麼／指標明細／原始資料／工程診斷」類 evidence expander；Digest raw 與工程診斷屬資料健康度 Level 3」。


### DEC-130｜客戶覆核 DEC-128 PROVISIONAL (a)(b)(c)：(a) 有條件同意（Data State 五態與 Capability／Implementation Availability 兩軸分離，`⬜ 尚未接線` 不是 Data State，同列須拆欄）、(b) 同意（稽核面預設收合；🎯 使用者功能維持 Presentation Compression）、(c) 同意（`?ui2_dev=1` 開發面；不得當登入證據）——三項由 PROVISIONAL 升為正式 Active interpretation（客戶 2026-11-03 (15)）

> 2026-11-03 補登。**編號**：DEC-129 為上一號。repo 慣例是「每一則客戶指示訊息一個 DEC」，(15) 是 (13)(14) 之後的**獨立覆核訊息**，故另立 DEC-130；DEC-128／DEC-129 原文不動（DEC-128 §四 加 📌 指向本條）。**來源類別 D：客戶 2026-11-03 覆核 (15)，經總管轉交；下方 fence 逐字收錄，未改一字**（實作組未見客戶原訊息本身；若有出入以原訊息為準）。

- **決策者**：**客戶**（2026-11-03）。｜**效力日期**：2026-11-03 起。｜**範圍**：產品／UX／治理（資料健康度語意邊界、稽核面、開發面）；**docs＋tests 落盤，0 行 `src/`／`shared/`／`app.py` 變更**（src 過時註解仍走 `NUI2-COMMENT-DOCSTRING-SYNC`）。
- **狀態**：**客戶指示生效**；DEC-128 §四 (a)(b)(c) 自本條起為正式 Active interpretation；UI 程式尚未改（後續 UI correction 批，`docs/BACKLOG.md` §5.1.26）。
- **客戶原文（逐字，fence 內未改一字；具約束力；sha256 釘住於 `tests/test_ui2_active_contract_docs.py`）**：

```
覆核 PROVISIONAL (a)(b)(c)：

(a) 有條件同意，需修正語意邊界

資料健康度可使用：

- ✅ 正常
- ◷ 可能過期
- ◇ 資料未備
- ⛔ 來源不可用
- ⬜ 尚未接線

但必須明確維持既有三軸語意：

Data State 仍只有五態

- OK
- Missing
- Stale
- Unavailable
- Not Evaluated

不得新增第六態。

其中：

- ✅ 正常 → OK
- ◷ 可能過期 → Stale
- ◇ 資料未備 → Missing
- ⛔ 來源不可用 → Unavailable

而：

⬜ 尚未接線不是 Data State。

它屬於：

Capability / Implementation Availability

不得映射成 Not Evaluated、Missing、Unavailable 或任何第六態。

如果資料健康度同一列同時需要表達「尚未接線」與 Data State，必須拆成不同欄位／不同軸，不得混成單一 status。

"Not Evaluated" 仍保留原有正式語意。

請把這個修正同步進 Active Contract / tests / guards，避免未來再把 Capability 與 Data State 混回去。

---

(b) 同意

保留：

- 👤 我的 → Audit
- Decision Digest Viewer
- Rule Registry

但預設收合，不得搶主 UI。

🎯 標的頁保留：

- 選股條件
- 查看全部候選
- CSV
- 查看此檔

這些屬使用者功能，不是 raw evidence。

但必須維持 Presentation Compression 原則：

- 選股條件只顯示精簡、人類可讀版本
- 完整 rule detail / engineering detail 不直接塞主頁
- 全部候選／CSV 作為次層操作
- 不得讓這些功能把 🎯 主頁重新做成資料牆

---

(c) 同意

Preview / FAKE / scenario 控制移至：

"?ui2_dev=1"

或等價的 developer-only surface。

要求：

- 一般使用者 UI 不顯示
- 不放 sidebar
- 不增加正式導航
- production presentation 不依賴它
- 不曝光 secret / credential / raw developer diagnostics
- 不得將 "ui2_dev" query parameter 與正式 auth state 混用
- query parameter 只能控制 developer preview surface，不能被當成登入證據

---

以上三項請從 PROVISIONAL 升為正式 Active interpretation。

另外：

"NUI2-ACTIVE-CONTRACT-INDEPENDENT-AUDIT"

仍保留，後續適當批次補獨立複驗即可，不阻擋目前純 presentation correction。

下一批仍依既定 P1～P7 進行；純 presentation 優先使用：

Claude Sonnet 5.5
Effort：Medium

若碰到 auth contract、Decision Digest schema、Risk Cap、System Action、新 canonical data contract，再 STOP → Opus 5.5 + High。
```

#### 一、效力與優先序

- 客戶明示「以上三項請從 PROVISIONAL 升為正式 Active interpretation」：DEC-128 §四 (a)(b)(c) **不再是 PROVISIONAL**。**(a) 是「有條件同意」**——升為 Active 的是**經客戶修正後的語意邊界（§二）**，不是 DEC-128 §四 (a) 的原字面；二者衝突處以本條為準。(b)(c) 同意，並附客戶新增限制（§三、§四）。
- `NUI2-ACTIVE-CONTRACT-INDEPENDENT-AUDIT` **仍保留**（客戶：「後續適當批次補獨立複驗即可，不阻擋目前純 presentation correction」）；本批不執行它，也不得以本批宣稱「已無牴觸」。
- 下一批仍依既定 P1～P7；純 presentation 用 Sonnet 5.5＋Medium，碰 auth contract／Decision Digest schema／Risk Cap／System Action／新 canonical data contract 即 STOP → Opus 5.5＋High（BACKLOG 各批 Gate 欄不變）。

#### 二、(a) 的語意邊界（⛔ 不得簡化）

**兩條互相獨立的軸，資料健康度每列都要分得開：**

| 軸 | 成員 | 說明 |
|---|---|---|
| **Data State**（DEC-124 資料語意軸） | **只有五態**：OK／Missing／Stale／Unavailable／Not Evaluated | **不得新增第六態**。`Not Evaluated` 保留原有正式語意（規則／計算尚未執行或不在本次評估範圍），**不是**「尚未接線」的別名 |
| **Capability／Implementation Availability**（能力可用性軸） | 尚未接線（`⬜ 尚未接線`；全站同源字樣 `⬜ 尚未提供`）／已接線 | **不是 Data State**；⛔ 映射成 Not Evaluated、Missing、Unavailable 或任何第六態 |

Level 1 符號對映（客戶逐項列出；**僅 Data State 四項有對映**）：

| 符號 | 軸 | 對映 |
|---|---|---|
| `✅ 正常` | Data State | OK |
| `◷ 可能過期` | Data State | Stale |
| `◇ 資料未備` | Data State | Missing |
| `⛔ 來源不可用` | Data State | Unavailable |
| `⬜ 尚未接線` | **Capability／Implementation Availability** | **無 Data State 對映**（⛔ Not Evaluated／Missing／Unavailable／第六態） |

- **同一列同時需要「尚未接線」與 Data State → 必須拆成不同欄位／不同軸，⛔ 混成單一 status。** 條文化：資料健康度表格每列至少有 `狀態(Data State)` 與 `接線(Capability)` 兩個分離欄位；`⬜ 尚未接線` 只准出現在後者。尚未接線的項目其 Data State 欄不得填五態中的任何一個來冒充（無資料可評＝該欄留空／不適用，⛔ 填 Missing 或 Not Evaluated）。
- **`Not Evaluated` 的呈現**：Level 1 符號集（客戶列的五個符號）**不含 Not Evaluated 的專用符號**；Not Evaluated 另以既有字樣（`⬜ 尚未評估` 等 DEC-124／Freeze §5 全站字樣）呈現，**不併入 `⬜`（尚未接線）**，也不另造符號。
- 與 DEC-124 的關係：本條是 DEC-124 三軸（資料語意／判定語意／能力可用性）在資料健康度面的**落地約束**，不改 DEC-124、不改全站字樣與 `shared/ui2_contract/text.py`、不放寬任一既有守衛。`⛔` 在 Freeze §5.3 舊義（功能未接）在其他頁不變；資料健康度面 `⛔`＝來源不可用（Data State: Unavailable）。`⛔ 來源不可用` 的顏色客戶未指定，**沿 Freeze §5.1 Unavailable 紅**（`CLAUDE.md` §1.A-4「紅＝真錯誤」與之一致：來源不可用＝真錯誤；`⬜ 尚未接線` 灰）——此為撰寫組讀法，非客戶原文。
- 客戶要求「同步進 Active Contract／tests／guards，避免未來再把 Capability 與 Data State 混回去」：見 §六。

#### 三、(b) 的 Active 條文（客戶新增限制）

- **稽核面**：👤 我的 → Audit、Decision Digest Viewer、Rule Registry **保留，預設收合，不得搶主 UI**。
- **🎯 標的頁保留**選股條件、查看全部候選、CSV、查看此檔——**屬使用者功能，不是 raw evidence**；但必須維持 Presentation Compression：選股條件**只顯示精簡、人類可讀版本**；完整 rule detail／engineering detail **不直接塞主頁**；全部候選／CSV 是**次層操作**；**不得讓這些功能把 🎯 主頁重新做成資料牆**。
- 其餘 DEC-128 §四 (b)③（「指標危險度」指路改向）與 (b)④（全站一行資料狀態入口）：客戶 (15) 對 (b) 整體「同意」，一併升 Active（入口點擊導向 👤 資料健康度，完整診斷本體不留在四個投資頁）。

#### 四、(c) 的 Active 條文（客戶新增限制）

Preview／FAKE／scenario 控制移至 `?ui2_dev=1` 或等價 developer-only surface，且：

1. 一般使用者 UI 不顯示；2. 不放 sidebar；3. 不增加正式導航；4. production presentation 不依賴它；5. 不曝光 secret／credential／raw developer diagnostics；6. **`ui2_dev` query parameter 不得與正式 auth state 混用；只能控制 developer preview surface，不能被當成登入證據**（與 DEC-129「不得從 URL／query parameter 猜登入狀態」同向、更具體）。

AppTest `query_params` 支援：本批實測 Streamlit 1.59.2 的 `AppTest.query_params["ui2_dev"]="1"` 可設定並跑完（1.56 未驗；BACKLOG `NUI2-PREVIEW-DEV-SURFACE` 實作批須在 `requirements.txt` floor 版本複測）。

#### 五、取代／影響範圍（單組實查，非窮舉）

- **DEC-128 §四 (a)(b)(c)**：升 Active（📌 已加；原文不動）。(a) 的字面以本條 §二 為準。
- **Active Contract**：§5 資料健康度改寫為兩軸分離；§6／§3.4／§3.2 的 PROVISIONAL (b)(c) 標示改 Active；§11 清單更新。**資料健康度表格每列兩欄**。
- **BACKLOG／PROJECT_STATE／HANDOFF／Audit Checklist／PROJECT_RULES §30／Wireframes・Freeze・Architecture Gate・Supersede Map 的橫幅與註記**：凡寫 PROVISIONAL (a)(b)(c) 處改為 Active（舊字加刪除線＋📌）；`NUI2-DATA-HEALTH-SYMBOLS-CONFIRM`／`NUI2-AUDIT-SURFACE-CONFIRM` 結案；`NUI2-PREVIEW-DEV-SURFACE` 去掉 PROVISIONAL。
- **BACKLOG 批次表**：涉及資料健康度的 P6（及 P3③ 過渡）新增驗收條件「兩軸欄位分離」；新增待 UI 批 teeth `T_new_8`（資料健康度每列 Data State／Capability 欄位分離）、`T_new_9`（`ui2_dev=1` 才顯示 Preview 控制且不影響 Account Area）。
- **仍保留的「撰寫組暫定」（非 (a)(b)(c)，客戶 (15) 未涵蓋）**：Level 1／2 預設展開或收合、「Level 3 只准遮罩後診斷代碼」嚴於客戶原文、`⛔ 來源不可用` 的顏色、🎯 跨季趨勢是否保留為「完整分析」使用者功能。這些**不是**客戶已核准項；Active Contract §11 逐項標明為「撰寫組暫定」。

#### 六、tests／guards（本批新增；皆附 mutation）

- `tests/test_ui2_active_contract_docs.py`：DEC-130 fence sha256 與關鍵句、DEC-128 §四 📌、Active Contract 不再把 (a)(b)(c) 當 PROVISIONAL 現行用法、資料健康度節含兩軸分離與四對映／「不是 Data State」句／`ui2_dev` 不得當登入證據句。
- `tests/test_ui2_guards.py`：`check_axis_separation`（FieldState 恰五態、CapabilityState 不共用成員、UI2 程式碼不得把 capability 標記用於 Data State 欄或反之、Data State 欄不得含「尚未接線／尚未提供」字樣）、`check_ui2_dev_not_auth`（`ui2_dev`／`query_params` 與 auth／account 不得同函式共現、污染傳播不得流入 account／auth 變數或 session key）——**defense-in-depth，AST 不窮舉所有繞過**；主要保證仍是 `FieldVM` 建構期驗證與 DEC-124 字樣表守衛。
- `tests/test_ui2_contract_teeth_pending.py`：`xfail(strict=True)` 的 `T_new_8`、`T_new_9`（reason 含 DEC-130）。

#### 七、揭露與效力邊界（⛔ 不是實作授權）

單組撰寫、未經第二組獨立驗證（`NUI2-ACTIVE-CONTRACT-INDEPENDENT-AUDIT` 仍待）。不授權：auth／OAuth 架構本體、Decision Digest schema、Risk Cap、System Action、新資料 contract／source／公式／threshold、production default、刪 Old UI／Legacy New UI；資料健康度的**實作**（版型）仍須先出文字線框草稿（`CLAUDE.md` §-1.5.D v3 §03-2 ①；BACKLOG P6）。T_new_8 的 DOM 標記名（`data-ui2-col`）是撰寫組暫擬，P6 定案時同步改測試。


### DEC-131｜客戶正式裁示 (17)：選 A，開始 New UI2 P3——A2「完整 VM／Evidence 保留、只禁止 Human UI 渲染 L2／L3 evidence expander」；T_new_1b 為測試規格錯誤、改驗證正確對象；P3 僅三項（客戶 2026-11-03）

> 2026-11-03 補登。**編號**：DEC-130 為上一號；repo 慣例是「每一則客戶指示訊息一個 DEC」，(17) 是 (16)（P1）之後的**獨立正式裁示**，故另立 DEC-131；DEC-128／129／130 原文不動。**來源類別 D：客戶 2026-11-03 正式裁示 (17)，經總管轉交；下方 fence 逐字收錄，未改一字**（實作組未見客戶原訊息本身；若有出入以原訊息為準）。

- **決策者**：**客戶**（2026-11-03）。｜**效力日期**：2026-11-03 起。｜**範圍**：New UI2 UI Correction P3（`src/ui2/views`、測試、docs）；0 行資料層／公式／Action Authority／Risk Cap／System Action／Decision Digest schema／OAuth 變更。
- **狀態**：**客戶指示生效**；P3 已實作（見 `docs/BACKLOG.md` §5.1.26「P3 完成補記」）。
- **客戶原文（逐字，fence 內未改一字；具約束力；sha256 釘住於 `tests/test_ui2_active_contract_docs.py`）**：

```
正式裁示：選 A，開始 New UI2 P3。

先重新執行 GitHub Verification Gate（main、Open/Draft PR、diff、CI、branches、Active Contract、BACKLOG）。基準已知 #1008 合併後 main "d73c43e8"，以重新取得的實況為準。

1. 先修正測試契約矛盾

採用方案 A2：

完整 VM / Evidence 保留，只禁止 Human UI 渲染 L2/L3 evidence expander。

"T_new_1b" 目前要求 VM sections 沒有 L2/L3，與 Active Contract §8 相衝突。

請依 DEC-128～130 修正測試，讓它驗證：

- 三個投資主頁不得渲染 L2/L3 evidence expander。
- "PageVM"、"PageContext.sections"、lookup sections 仍完整保存原始 evidence。
- canonical、source、as_of、provenance、RuleIDs、Missing、Risk Cap evidence 不得遺失。
- OneBrain 未來仍可從正式 headless Digest 取得完整 evidence，不依賴 UI 可見區塊。

修正測試不代表放寬驗收，而是改成正確的驗收對象。必要時新增反向測試防止 evidence 遺失。

2. P3 僅施工三項

1. 四頁 Human UI 不再顯示過時的 L2/L3 evidence expander；保留 👤 我的已核准的次層稽核入口。
2. 更新對應測試與 strict xfail；真正修好才移除 xfail，不得 skip 隱藏失敗。
3. L0 市場位階完整說明繼續保留於既有正式資料／VM；待 P6 資料健康度承接前，明確記錄過渡期限制。

不得修改資料層、公式、Action Authority、Risk Cap、System Action、Decision Digest schema 或 OAuth。

3. 驗收及落盤

- 手機 390px、桌機 1440px 實際截圖。
- FAKE／Real／Missing／Stale／Unavailable／Not Evaluated 回歸。
- P3 對應 tests 轉綠，且 evidence preservation tests 通過。
- 獨立 QA、CI、Visual Fidelity Gate。
- 將 T_new_1b 原本的規格錯誤、修正依據與影響記入正式 GitHub 文件。
- BACKLOG、PROJECT_STATE、HANDOFF 同步。
- 通過既有 Auto-Ship Gate 後合併 PR。

P1 已完成，不重做。P2、P6、P7 不在本批實作範圍。

Model：Claude Sonnet 5.5  Effort：Medium
Silent Autonomous Cruise；只有真正需要客戶裁示或整批完成才回報。
```

#### 一、A2 裁示與效力

採方案 **A2**：完整 VM／Evidence 保留，只禁止 Human UI 渲染 L2／L3 evidence expander。與 Active Contract §8（UI VM＝全量、「從 UI 移除 ≠ 刪資料」）同向；`PageVM`／`PageContext.sections`／lookup sections 一字不動。

#### 二、T_new_1b 規格錯誤（客戶要求記入正式文件）

- **舊規格（錯）**：`tests/test_ui2_contract_teeth_pending.py::test_T_new_1b_human_vm_sections_are_not_l2_l3`（strict xfail）斷言三個投資頁 `[s.section_id for s in vm.context.sections if s.level in ("L2","L3")] == []`。
- **錯誤依據**：把「Human UI 不渲染 L2／L3」誤寫成「VM 不得含 L2／L3」。要讓它轉綠只能刪／改寫 VM sections（＝刪 evidence，違反 Active Contract §1／§8、DEC-129 §四「從 UI 移除 ≠ 刪資料」）或改 `level` 語意（VM schema 變更，須 Gate）。BACKLOG `NUI2-PLAN1007-P3-T1B-TENSION` 即此張力。
- **修正依據**：Active Contract §8 清單（adapter／canonical／deterministic result／provenance／source／as_of／freshness／Missing·Stale·Unavailable／RuleIDs／Risk Cap evidence／Decision Context／未來 Digest input 皆不得刪）＋客戶 (17) A2。
- **修正內容（不是放寬）**：舊斷言由兩個正確驗收對象取代，缺一不可——(A) 渲染層：三個投資頁不渲染 L2／L3 evidence expander（`T_new_1`，並以 AppTest 全場景×Real＋真瀏覽器 DOM 判定器 `p3_no_evidence_expander` 覆蓋）；(B) VM 層：`test_T_new_1b_vm_keeps_evidence_while_human_ui_hides_it` 與 `tests/test_ui2_p3_evidence_preservation.py`（FAKE 六場景×四頁〔👤 三帳戶〕＋Real 固定 snapshot 九態×四頁的 evidence 指紋 baseline；section 被刪空／拿掉 detail／拿掉 freshness／刪 lookup sections／Risk Cap 換語意皆 mutation 轉紅）；(C) Digest 輸入不依賴 UI2（import 傳遞閉包守衛）。舊斷言原文保留於測試檔 docstring，不得復活。
- **影響**：strict xfail 由 10 降為 4（餘 T_new_3／6／7／8）；`GRADUATED_TEETH` 新增 `T_new_1`、`T_new_1b`（新名）；P1 的 VM 層測試不受影響。

#### 三、P3 實作的內部自決（CLAUDE.md v3 §03-1；不新增客戶裁示）

1. 渲染政策在 `src/ui2/views/_page.py`：L1 照畫；L2／L3 **預設不渲染**（fail closed），僅 `SHOWN_FOLDS` 白名單（🎯 `conditions`「選股條件」；👤 `digest`／`registry` 稽核入口）以預設收合 expander 呈現。不改 `SectionVM`／canonical。
2. 隱藏項（VM 仍有）：📊 為什麼／指標明細／原始資料表；🎯 完整 6 欄表／跨季趨勢（Active Contract §3.2：evidence）、查一檔的基本面／估值／研究解釋（P2 以精簡卡承接）；💼 明細／原始明細；👤 Data Freshness／System Information（Contract §3.4 → P6 資料健康度，非核准稽核入口）。「查看全部候選／CSV／查看此檔」**目前 UI 尚未存在**（P2 範圍），本批不新增。
3. 以上第 2 點的 👤 Fresh／Sysinfo 隱藏、🎯 完整表隱藏是**總管可推翻的讀法**（見 BACKLOG `NUI2-P3-FRESH-SYSINFO-HIDDEN`／`NUI2-P3-FULL-TABLE-HIDDEN`）。

#### 四、L0 位階完整說明過渡期限制（客戶 (17) §2 第 3 項）

`regime_arbiter.*_EXPLAIN` 逐字常數與 VM `位階說明` 列保留；Human UI 因 P3 不渲染 L2，**過渡期使用者看不到完整說明**：L1 保留 `REGIME_SEE_WHY` 一句簡短原因，完整說明由 P6 資料健康度承接；~~此期間仍可由 VM／Digest 取得~~ 📌 QA 更正（2026-11-04；過度宣稱已更正，有意識的更正，不是漏刪；決策者 AI 總管〔QA 修正〕）：**保留於 VM**（`regime_arbiter.*_EXPLAIN` 逐字常數與 VM `why` 等 sections）；**Decision Digest 是否涵蓋未驗**（實測 Digest builder 不含位階完整說明、指標明細、lookup 基本面／估值；`NUI2-P3-DIGEST-CLOSURE-STATIC-ONLY`），未來 OneBrain 批須先核對 Digest 缺欄。

#### 五、揭露與效力邊界

單組實作、待獨立 QA。不授權：資料層／公式／Action Authority／Risk Cap／System Action／Digest schema／OAuth 變更；P2／P6／P7 不在本批。四項撰寫組暫定判讀維持 Pending。

#### 六、QA 修正補記（2026-11-04；兩組獨立 QA 無 P0／P1；fence 未動）

- **指紋擴大鎖定（不是縮小）**：baseline 指紋原只記 `bool(detail)`／`bool(value_text)`，evidence 內文被偷換測不到；現加記 `sha1(detail)`／`sha1(value_text)`／`sha1(status_text)`，並納入 `first_screen`／`cards`；section title／欄位 label 以明文逐字鎖定。重新產生 baseline 後其 sha256 釘於 `tests/test_ui2_active_contract_docs.py::_P3_BASELINE_SHA256`（防無聲洗白；重產流程見該檔註解與 BACKLOG）。
- **RuleID 現況鎖定**：VM **尚無獨立 RuleID 欄位**；實際承載治理參照者是 `why` section 位階說明 detail（L0 `*_EXPLAIN` 逐字，含 DEC-074／DEC-075）。已加具名測試鎖定該參照仍在 VM，並鎖 `RULE_ID_ALLOWLIST` 六個 id（`risk_cap`、`cut`、`take_profit_force`、`take_profit_partial`、`pause_add`、`add`）仍存在且 `shared/decision_digest_rules.py` 不依賴 UI2。這是**現況鎖定**；日後 VM 新增 RuleID 欄位須納入。
- **Digest 宣稱更正**：§四「此期間仍可由 VM／Digest 取得」過度宣稱，已以刪除線＋📌 更正（實測 Digest builder 不含位階完整說明、指標明細、lookup 基本面／估值；是否涵蓋未驗）。
- viewport 判定器：真瀏覽器量測 dict 缺 `expanders` 鍵改判紅；允許標題改為判定器自有常數（與 pytest `EXPECTED_SHOWN_FOLDS` 的一致性由單元測試守）。



---

### DEC-132｜客戶正式覆核 (18)：#1009 兩灰區裁定（👤 Data Freshness／System Information 維持不在四頁一般 Human UI；🎯 跨季趨勢與完整分析暫不恢復舊 L3 expander、保留為設計候選）＋Digest 缺口維持登記＋P2 採「文字線框先行」、本輪不授權實作（客戶 2026-11-04）

> 2026-11-04 補登（ID 取下一個未用號；落盤前 `grep -rn "DEC-132" docs PROJECT_RULES.md tests` 0 命中，DEC-131 為上一號）。**編號**：repo 慣例是「每一則客戶指示訊息一個 DEC」，(18) 是 (17)（P3）之後的**獨立正式覆核**，故另立 DEC-132；DEC-128～131 原文不動（append-only）。**來源類別 D：客戶 2026-11-04 正式覆核 (18)，經總管轉交；下方 fence 逐字收錄，未改一字**（docs 組未見客戶原訊息本身，只見總管轉交之全文；若有出入以原訊息為準）。

- **決策者**：**客戶**（2026-11-04）。｜**效力日期**：2026-11-04 起。｜**範圍**：治理＋文件（兩項灰區裁定落盤、P2 文字線框交付）；**0 行 src／shared／app／tests 行為變更**（僅 docs 一致性測試加性擴充）。
- **狀態**：**客戶裁示生效**（兩項裁定、Digest 缺口維持、P2 採文字線框先行）；**P2 線框待客戶驗收，本 DEC 不授權任何實作**。
- **客戶原文（逐字，fence 內未改一字；具約束力；sha256 釘住於 `tests/test_ui2_active_contract_docs.py`）**：

```
正式覆核 #1009 後，下一批選 P2，但採「文字線框先行」方式。

先完成 GitHub Verification Gate，以最新 main／PR／CI／正式規格為準。

一、兩項裁定

1. 👤 Data Freshness、System Information 維持不在四頁一般 Human UI 顯示，未來由 P6「資料健康度」承接。不得刪 VM、資料來源、provenance 或其他 Evidence。

2. 🎯 跨季趨勢與完整分析暫不恢復舊 L3 expander。保留為後續使用者分析能力的設計候選，以精簡圖卡為優先；資料來源、EPS 口徑、版型先另行驗證，不自行開工或新增公式。

重要：VM 保存不等於 Digest 已有。 請維持 Digest evidence coverage 缺口登記，未證實之前不得宣稱 OneBrain 可讀完整資料。

二、P2 文字線框先行

依既有已核准 New UI2 草稿，提出手機 390px、桌機 1440px 的最小差異文字線框。

本次只規劃：

1. 🤖 OneBrain Outlook 位置調整。
2. 台股 Primary 主圖區塊及短 SPEC 的誠實空槽。

要求保留：

- 已核准的市場頁首屏順序及主 CTA。
- 市場狀態、Risk Cap、是否需要行動、今日主要風險。
- 既有圖表、卡片與資訊層級。
- 手機四格導航、桌機原有布局。
- 沒有正式歷史圖表資料時，不繪製假走勢線。

請特別核對 Active Contract §3.1 與 Wireframes §2.1 的「今日主要風險／是否需要行動」排序差異，以最新客戶裁示及已核准視覺契約為準，不自行變更頁面責任。

完成文字線框與資料位置對照後，先回報供我驗收。

本輪只授權提出線框與驗證資料欄位，不授權直接實作新版面。

若線框已符合既有核准版型、無需新裁示，再由我確認後進入 P2 程式施工。

三、資料串接邊界

對照已合併 #1007 的 UI × Data × Evidence 規劃：

- TWII 最新收盤值不等於歷史圖表資料。
- 不新增資料來源、MA 公式或未核准的圖表判斷。
- 不修改 Risk Cap、System Action、Digest schema、OAuth。
- 不以 UI ViewModel 取代完整 Decision Digest。

將此次兩個灰區及 P2 線框依既有治理要求寫進 GitHub 正式紀錄，歷史 Decision 維持 append-only。

完成後一次精簡回報，無需中途反覆說明。

Model：Claude Sonnet 5.5  Effort：Medium
```

#### 一、裁定 1：👤 Data Freshness／System Information（客戶 (18) 一.1）

- **客戶裁示**：維持**不在四頁一般 Human UI 顯示**，**未來由 P6「資料健康度」承接**；**不得刪 VM、資料來源、provenance 或其他 Evidence**。
- **對 #1009 登記的影響**：BACKLOG `NUI2-P3-FRESH-SYSINFO-HIDDEN` 原寫「實作組讀法，可由總管／客戶推翻」＝**可推翻的讀法**；DEC-131 §三第 3 點同。自本 DEC 起該讀法**升為客戶裁示**（BACKLOG 該列以刪除線＋📌 保留原文，不刪；DEC-131 原文**不改**，以本 DEC 為準）。
- **實作意涵（不是新施工）**：`SHOWN_FOLDS` 維持現狀（不含 `("p4_me","fresh")`／`("p4_me","sysinfo")`）；VM `fresh`／`sysinfo` sections、`first_screen`／freshness／source／as_of／provenance 一字不動。這兩區的**可見落點**＝P6 資料健康度 Level 1／2（Active Contract §3.4／§5），P6 到位前使用者看不到它們（過渡期限制，同 DEC-131 §四）。
- **仍 Pending（不因本 DEC 升格）**：資料健康度 Level 1／2 預設展開或收合、Level 3 是否限遮罩後診斷碼、`⛔ 來源不可用` 顏色（Active Contract §11 撰寫組暫定）。

#### 二、裁定 2：🎯 跨季趨勢與完整分析（客戶 (18) 一.2）

- **客戶裁示**：**暫不恢復舊 L3 expander**；**保留為後續使用者分析能力的設計候選**，**以精簡圖卡為優先**；**資料來源、EPS 口徑、版型先另行驗證，不自行開工或新增公式**。
- **狀態寫準確（⛔ 不得寫成核准功能）**：「🎯 跨季趨勢使用者功能」＝**仍 Pending／設計候選，不是核准功能**。本 DEC **不是**「核准恢復」、**不是**「核准新增功能入口」、**不是**開工授權；Active Contract §11 撰寫組暫定四項因此由「是否保留為使用者功能」改為「設計候選（客戶 (18)：暫不恢復舊 L3 expander）」，其餘三項（Level 1／2 預設、Level 3 遮罩、`⛔` 顏色）**維持 Pending**。
- **BACKLOG `NUI2-P3-FULL-TABLE-HIDDEN`** 同步：🎯 `完整 6 欄表／跨季趨勢` 維持不渲染（客戶裁示）；VM 保留；該項由「P2 新增使用者功能入口時另行分類」改為「**不在 P2 範圍**；設計候選待資料來源／EPS 口徑／版型另行驗證後由客戶決定」。
- **邊界**：不新增公式、不新增資料來源、不新增 Human UI expander；EPS 口徑與資料來源驗證屬**另案**（需客戶另行授權，且涉口徑者依 PROJECT_RULES 第 29 節多路徑比較）。

#### 三、重申：VM 保存 ≠ Digest 已有（客戶 (18) 一 末段）

- **客戶原文**：「**VM 保存不等於 Digest 已有。請維持 Digest evidence coverage 缺口登記，未證實之前不得宣稱 OneBrain 可讀完整資料。**」
- **落盤**：`NUI2-P3-DIGEST-CLOSURE-STATIC-ONLY`（AST 靜態閉包只證明「Digest 輸入不依賴 UI2 渲染」，**未**證明 Digest 內容涵蓋 UI evidence）**維持 open（未驗）**，不因本 DEC 或 P2 線框結案；實測 Digest builder 不含位階完整說明、指標明細、lookup 基本面／估值（QA 2026-11-04）仍為最新已知事實。
- **文件措辭規則（新增、自本 DEC 起）**：任何文件、PR、回報**不得**寫「OneBrain 可讀完整資料／evidence 已在 Digest」；只能寫「evidence 保留於 VM／canonical；Digest 是否涵蓋＝未驗」。P2 線框中的 OneBrain 槽只是**位置調整的誠實佔位**，**不是** Digest／OneBrain 已存在的證據。

#### 四、P2 採「文字線框先行」；本輪不授權實作（客戶 (18) 二、三）

- **客戶裁示**：下一批選 P2，**但文字線框先行**；本次只規劃①🤖 OneBrain Outlook 位置調整、②台股 Primary 主圖區塊＋短 SPEC 的**誠實空槽**；**只授權提出線框與驗證資料欄位，不授權直接實作新版面**；線框完成後**先回報供客戶驗收**，「若線框已符合既有核准版型、無需新裁示」再由客戶確認後進入 P2 程式施工。
- **交付**：`docs/vnext/NEWUI2_P2_TEXT_WIREFRAME_2026-11-04.md`（A 現況首屏／B 風險順序核對／C P2 最小差異／D 保留清單／E 資料位置對照／F 驗收準則與施工邊界／G 待客戶確認項）。**狀態＝待客戶驗收**。
- **「今日主要風險／是否需要行動」排序差異核對**（客戶要求「以最新客戶裁示及已核准視覺契約為準，不自行變更頁面責任」）：結論與證據見該文件 §B；摘要＝**以 Wireframes §2.1／§2.2（客戶 Q3 核准）＋DEC-122 Q3=A＋DEC-127 為準**（手機：是否需要行動 → 今日主要風險；桌機：三 tile〔狀態／Risk Cap／今日主要風險〕→ 是否需要行動）；Active Contract §3.1 該格是桌機三 tile 排法的**扁平轉述**，其表頭自述「順序依 Wireframes §2.1／§2.2 與 DEC-127」，**頁面責任不因整理而變**。最小勘誤僅提案、未套用。
- **資料串接邊界（客戶 (18) 三，逐字見 fence）**：TWII 最新收盤值**不等於**歷史圖表資料；不新增資料來源、MA 公式或未核准的圖表判斷；不修改 Risk Cap、System Action、Digest schema、OAuth；不以 UI ViewModel 取代完整 Decision Digest。
- **回報格式**：客戶要求「完成後一次精簡回報，無需中途反覆說明」；需客戶一句話確認的點集中於線框文件 §G（≤3 題、每題 A／B 加推薦）。

#### 五、揭露與效力邊界

docs 組單組撰寫、待總管複驗。**不授權**：任何 `src/`／`shared/`／`app*.py`／既有 tests 的變更；P2 程式施工（待客戶驗收線框）；P6／P7；OneBrain／Digest runtime；Digest schema／Risk Cap／System Action／OAuth／資料層／公式／門檻／來源；新增 Human UI expander；把「設計候選」當核准功能。舊 DEC（DEC-081／117／118／122／127～131）**一字不改**。

### DEC-133｜客戶正式裁示 (19)：P2 線框有條件通過（G-1＝A、G-2＝B、G-3＝A），開始 P2 程式施工——僅兩項（OneBrain Outlook 移至核准位置、台股 Primary 空槽＋短 SPEC）；SPEC 須標示「最新收盤參考」（客戶 2026-11-04）

> 2026-11-04 補登（ID 取下一個未用號；落盤前 `grep -rn "DEC-133" docs PROJECT_RULES.md` 0 命中，DEC-132 為上一號）。repo 慣例「每一則客戶指示訊息一個 DEC」，(19) 是 (18) 之後的**獨立正式裁示**，故另立 DEC-133；DEC-128～132 原文不動（append-only）。**來源類別 D：客戶 2026-11-04 正式裁示 (19)，經總管轉交；下方 fence 逐字收錄，未改一字**（施工組未見客戶原訊息本身，只見總管轉交之全文；若有出入以原訊息為準）。

- **決策者**：**客戶**（2026-11-04）。｜**效力日期**：2026-11-04 起。｜**範圍**：📊 市場頁 presentation 兩項（`src/ui2/views/market.py`／`_page.py`、`src/ui2/components/html.py`、`src/ui2/shell/css.py`）＋測試／判定器／治理文件；**0 行 `shared`／`src/services`／`app.py`／`src/data`／`src/compute`／`src/ui`／`src/ui_v2` 變更**。
- **狀態**：**客戶裁示生效**；P2 線框有條件通過、**授權 P2 程式施工（僅兩項）**。
- **客戶原文（逐字，fence 內未改一字；具約束力；sha256 釘住於 `tests/test_ui2_active_contract_docs.py`）**：

```
正式裁示：P2 線框有條件通過，開始 P2 程式施工。

G-1＝A：空槽依內容高度，不預留 220px 灰框。

G-2＝B：SPEC 省略頻率，僅使用已存在且可驗證的來源／資料日／缺值政策。不自行寫「日頻」。來源缺值省略來源欄，日期沿用既有 ISO 格式。

G-3＝A：接受手機指標卡移至第一屏下方，維持已核准草稿順序：
今日主要風險 → OneBrain Outlook → 台股 Primary 空槽 → 核心指標卡。

同時確認順序差異的判斷：

- 手機：是否需要行動 → 下一步 → 今日主要風險。
- 桌機：三個狀態 tile（含今日主要風險）→ 是否需要行動 → 下一步。
- 以 Wireframes §2.1／§2.2、DEC-122、DEC-127 的正式客戶裁示為準。
- 將 Active Contract §3.1 的扁平轉述歧義作最小文字勘誤，不改原本已核准的視覺順序。

新增資料誠實性要求：

台股 Primary 主圖目前只有空槽，尚無正式歷史圖表資料。SPEC 引用的 TWII 最新收盤 source/as_of 必須明確標示為「最新收盤參考」，不得讓使用者誤以為主圖已有正式歷史序列。

不接歷史資料、不畫假走勢、不新增 MA、不修改 canonical 或 VM schema。

P2 僅施工兩項：

1. OneBrain Outlook 移至核准位置，內容不變。
2. 台股 Primary 空槽及短 SPEC，依內容高度呈現。

施工驗收：

- 手機 390px、桌機 1440px 真實截圖。
- FAKE／Real／Missing／Stale／Unavailable 場景。
- 手機首屏必要項不變。
- 導覽餘裕維持既有 ≥160px 的驗收門檻；未達就停止，不擅自更改設計。
- 圖槽不得出現假線圖。
- SPEC 來源與資料日必須與正式 TWII 卡一致。
- T_new_6 真正修好後轉綠，移除對應 xfail。
- P3 VM／Evidence preservation、Risk Cap、System Action、Digest、Auth 等守衛不得退化。
- 獨立 QA、CI 全綠後依既有 Auto-Ship Gate 合併。
- BACKLOG、PROJECT_STATE、HANDOFF、DECISIONS 依治理規則同步。

全程靜默處理，只有真正阻塞或整批完成才回報。
Model：Claude Sonnet 5.5  Effort：Medium
```

#### 一、三個灰區裁定（落盤）

- **G-1＝A**：Primary 空槽**依內容高度**（標題＋一行說明＋SPEC 行），**不預留 220px 灰框**（真圖接線批再採約 220px，DEC-119）。
- **G-2＝B**：SPEC **省略頻率欄**，只用「已存在且可驗證」的來源／資料日／缺值政策；**不自行寫「日頻」**；來源缺值＝**省略來源欄**；資料日沿用既有 ISO 格式原樣。
- **G-3＝A**：接受手機指標卡移至第一屏下方；維持已核准草稿順序「今日主要風險 → OneBrain Outlook → 台股 Primary 空槽 → 核心指標卡」（手機四必要項與今日結論不變）。

#### 二、順序差異確認（客戶確認；原「單組判斷、待客戶確認」升為客戶確認）

- 手機：是否需要行動 → 下一步 → 今日主要風險。桌機：三個狀態 tile（含今日主要風險）→ 是否需要行動 → 下一步。以 Wireframes §2.1／§2.2、DEC-122、DEC-127 的正式客戶裁示為準。
- Active Contract §3.1 的扁平轉述歧義已做**最小文字勘誤**（原文刪除線＋📌 保留；見該檔 §3.1），**不改已核准視覺順序**；BACKLOG `NUI2-ACTIVE-CONTRACT-VS-WIREFRAME-RISK-ORDER` 標**客戶已確認（DEC-133）**。

#### 三、資料誠實性要求（客戶 (19) 新增；本 DEC 新增 Rule 的唯一來源）

- 台股 Primary 主圖目前**只有空槽、尚無正式歷史圖表資料**。SPEC 引用的 TWII 最新收盤 source／as_of **必須明確標示為「最新收盤參考」**，不得讓使用者誤以為主圖已有正式歷史序列。
- **落地**：SPEC 行格式 `SPEC｜最新收盤參考｜<來源>｜資料日 <as_of>｜缺值不補`（來源缺值→省略該欄；as_of 缺→既有字樣 `⬜ 資料日未提供`；⛔ 補日期／寫死來源／手寫頻率）；來源與資料日**逐字取自正式 TWII 卡 `freshness`**（`tests/test_ui2_p2_primary_slot.py` 鎖定，FAKE 六場景＋Real 固定 snapshot 九態）。
- **文件措辭規則（承 DEC-132 §三，不變）**：不得寫「主圖已有歷史資料」「OneBrain 可讀完整資料」；只能寫「SPEC 引用 TWII 最新收盤的來源／資料日（最新收盤參考）；歷史序列／MA 未接」。

#### 四、施工範圍與不做（客戶 (19) 逐字範圍）

- **做（僅兩項）**：(1) OneBrain Outlook 移至核准位置、內容不變（手機＝今日主要風險之後、Primary 空槽之前、指標卡之前；桌機＝是否需要行動／下一步之後、單行）；(2) 台股 Primary 空槽（`🇹🇼 台股趨勢`、`⬜ 尚未提供`、「此項目尚未開放」、灰底、0 個 svg／polyline／canvas／img）＋一行 SPEC。
- **不做**：不接歷史資料、不畫假走勢、不新增 MA、不修改 canonical 或 VM schema；不改 Risk Cap／System Action／Digest／OAuth；第一屏順序、主 CTA、既有卡片、手機四格導航、桌機布局不動。
- **驗收門檻**：手機導覽餘裕維持 ≥160px（未達停止、不擅自改設計）；P3 evidence preservation、白名單、P1 工程字樣、DEC-124 三軸（空槽是 Capability）、G2／G2F／G4／G9、no-write 守衛不得退化；T_new_6 真正修好後移除 xfail（strict xfail 4→3）。實作形態與實測見 BACKLOG §5.1.26「P2 完成補記」。
- **不是**：Real Feed／OneBrain／Digest 授權；**不是**歷史序列接線授權（`NUI2-TWII-TWO-PATHS` 仍待擇一）；**不是** P6／P7 授權（下一批須由客戶從 P6／P7 選）。


### DEC-134｜手機導航改為可展開左側抽屜、保留 Google 登入入口（客戶 2026-11-04）

- **客戶原始需求**：「左邊是現在的右邊是以前的，但是下方的會被manage app擋住了 所以我想維持左邊仍然有選項以及登入按鈕」；在 ChatGPT 比較三案、推薦「手機 ☰ 左側抽屜選單＋登入，桌機維持左側固定導航」後，客戶原文答覆：「好」。
- **客戶同意的範圍**：選 B 可收合左側抽屜（四主頁及 Google 帳號入口），而非舊式常駐側欄或雙導航。先前「手機只有底部固定四格」的**導航位置與顯示方式**在 New UI2 中由本較新指示取代；四個主頁與桌機 rail 保留。
- **未授權**：沒有核准抽屜像素尺寸、真 Google OAuth 接線、正式 auth state、資料來源、VM schema 或投資語意；必須先提供詳細文字線框與獨立 Gate。
- **正式設計附件**：docs/vnext/NEWUI2_MOBILE_DRAWER_NAV_CONTRACT_2026-11-04.md。舊 DEC 原文 append-only 不刪，既有測試與 CSS 的底部四格規則需在施工批明確更換，不得默默降測試。
- **證據限制**：使用者截圖可見 Streamlit Manage app 覆蓋底部，但尚未在本端真機／Cloud 重現；此為已確認的使用者體驗需求，不聲稱平台浮層一定可由 CSS 控制。
- **不取代**：DEC-129 桌機 Account Area、DEC-127 順序、DEC-130 誠實規則（ui2_dev／query／FAKE account 不得當登入證據）、四頁 IA。
- **決策者**：**客戶**（2026-11-04）。｜**效力日期**：2026-11-04 起。｜**範圍**：產品／UX（New UI2 手機導航位置與登入入口）。
- **狀態**：**裁示已記錄、線框待驗收、不授權實作**。

### DEC-135｜New UI2 四頁視覺參考與頁數彈性（客戶 2026-11-04）

- **客戶原文（視覺方向）**：「聽你的建議，另外我覺得附檔目前這儀表版設計很棒，能盡量朝這方向執行嗎？」客戶提供四個畫面設計參考（市場、標的、持股、設定）。
- **客戶原文（新增頁面）**：「如果四個頁面不夠，可以多加頁面」。
- **核准方向**：採附圖的視覺資訊層級作為 New UI2 後續設計參考，既有四頁是核心、非永久硬上限；當使用者任務確有獨立需求，可考慮額外主頁或次層頁面。這一較新客戶指示在頁數上限方面取代舊「不得新增第五頁」的限制；不代表已選定新頁數、頁名、導航位置或可直接施工。
- **新 UX 候選（未核准施工）**：主要比較圖可自選標的與期間、整併重複大小圖；不得將示意數值、估值目標、OneBrain 結論、Risk Cap 或 action 當真實資料。先完成 UI 對照／資料契約／去重設計再過 Gate。
- **施工邊界**：不改 canonical、資料來源、正式公式、RuleIDs、Risk Cap、System Action、OAuth、Digest；保持 P6 與 DEC-134 已有派工分離。正式文字規格：docs/vnext/NEWUI2_VISUAL_REFERENCE_AND_PAGE_EXPANSION_2026-11-04.md。
- **附圖證據**：使用者在當前對話提供之參考圖片；本文僅記錄由其判讀出的佈局，**未把圖片本身上傳 GitHub**，故非 pixel-perfect 圖像 SSOT。


### DEC-136｜UI 視覺主模板與 OneBrain 完整資料雙軌驗收重申（客戶 2026-11-04）

- **客戶原文**：「UI設計我想以這為模板為主，但內容部份以完整的給Onebrian，我們說好了 UI簡化，但Onebrian需要吃全部資料給出建議」。確認追述：「沒錯，這也是我們之前討論過的」。
- **裁示效力**：重申既有 DEC-128／129 的 Presentation Compression ≠ Information Loss 和雙投影，並將客戶上傳的四面板圖片確立為 UI 主要視覺模板方向。Human UI 用精簡卡片／圖表呈現，OneBrain 經完整正式 Decision Digest 取得全部已核准、有效、可追溯的決策相關證據與反證；**不是**讀 UI ViewModel／卡片／可見 Top N。
- **執行護欄**：缺值／資料時間／source／limitation 須保存；VM 保存不等於 Digest coverage 已完成，啟用前須逐欄驗證。OneBrain 應產出有依據的分析與建議，但不能自造事實、重寫 Risk Cap／System Action 或代替唯一動作權威，也不授權啟用 OneBrain runtime／新 API／交易動作。
- **分軌驗收**：Visual Fidelity 和 Complete Evidence／Digest Coverage 必須分別查核；UI 隱藏不許縮減資料，Digest 補齊不許在 UI 恢復 raw evidence wall。詳細實作驗收附件見 `docs/vnext/NEWUI2_VISUAL_REFERENCE_AND_PAGE_EXPANSION_2026-11-04.md` §7。
- **證據範圍**：圖片本體為對話附件，不是 GitHub 已存圖片；示意數值不能當正式來源。DEC-128～135 歷史保持 append-only。


### DEC-137｜手機抽屜受控施工授權（使用者 2026-11-04）

- **使用者原話（摘錄）**：「本輪由使用者授權恢復受控施工。優先完成 New UI2 手機抽屜導航」；手機左上角 ☰、預設收合不佔主畫面寬度、展開顯示四頁（📊 市場／🎯 標的／💼 持股／👤 我的）及 Google 登入入口、「點擊目前頁或其他頁都要收合」、支援 Esc／遮罩關閉／鍵盤操作／焦點進入與返回、「抽屜展開時背景不得被操作」、「關閉時抽屜內容不得殘留在可操作或無障礙導覽中」、☰ 佔既有 44px 頂部保留帶、首屏 ≥160px 守衛維持、「Google 登入正式接線前顯示 Capability『⬜ 尚未提供』，按鈕 disabled；不可用 FAKE 或 query 假裝登入」；桌機「保留既有固定左側導覽」「不額外建立第二個主導航」。「C+JS（JS_V3）為首選候選，不代表既有原文已免審核」；「☰ 的 Enter／Space 操作須明確驗證」；「不能讓背景 inert 誤傷抽屜或選單控制」；「任何 JS 原文修改，都重新執行安全 Gate 與獨立 QA」；「既有守衛只能改為等價或更嚴格，不得刪除降級」。
- **採用的路線**：C+JS（CSS checkbox 抽屜＋一段固定常數 JS）。JS 由 JS_V3 **最小修補為 JS_V4**（只新增「焦點在 ☰ 時按 Enter → `click()`」兩行；白名單新增成員 `click`），其餘關閉態 a11y 殘留以零 JS CSS 修法處理。詳見 JS 安全設計 §15。
- **J-6 採 B**：抽屜／rail 帳戶摘要固定占位，歸 **Capability 軸**（`⬜ 尚未提供`，`TEXT_NOT_PROVIDED`）；登入鈕 disabled；原因句「登入與 Sheet 操作尚未開放」；不讀 `ui2_account`／`ui2_dev`／query。**不撤銷 DEC-129**：其「⬜ 尚未登入」字面待正式 auth contract 具備後適用。
- **範圍外（未動）**：P6 資料健康度、四頁視覺重排、OAuth／Sheet、OneBrain runtime、Digest schema、Risk Cap／System Action、投資公式、新資料來源、P7 Account Area；✕ 關閉鈕未加（S-14 待線框定案）。
- **決策者**：**使用者**（2026-11-04）。｜**效力日期**：2026-11-04 起。｜**範圍**：New UI2 手機導航施工。
- **狀態**：施工 PR 為 draft；Visual Fidelity／獨立 QA／真機項未驗；`ui2-browser-gate` 需 user 在 GitHub 設為 required check 後才算強制。

### DEC-138｜#1020 視覺完善 Batch 1：維持 Dark-only、不新增 Light 支援；W-11 未完成部分不得宣稱 UI 完成（客戶 2026-11-05）
- **裁示**：(1) New UI2 **維持 Dark-only**；PR #1020（`ui2/visual-batch1`）**不新增 Light Theme 支援**。(2) 若日後 Light 變成使用者可達，且 chip 新三色（`#3fb950／#d29922／#ff7b72`）疊 tint 後對比不合格（獨立 QA 估約 2.1～2.2，未達 4.5:1），**須停手回報**，不得自行調色或硬上 Light。(3) 💼 持股頁 W-11 的 **Primary 圖、⑤ 建議持股區間、持股表** 尚未完成，**不得宣稱整頁 UI 完成**；其餘限制保留於 BACKLOG／HANDOFF，**不得自行關閉**。
- **背景**：獨立 QA（限定範圍複驗）結論 0 個 FAIL、可合併；3 項輕微偏離與未驗項目已登記於 BACKLOG `NUI2-VISUAL-BATCH1`。
- **決策者**：**客戶**（2026-11-05）。｜**效力日期**：2026-11-05 起。｜**範圍**：New UI2 視覺完善 Batch 1（#1020）。
- **狀態**：PR 維持 draft；本裁示不核准任何 B／C 類項目；💼 完整 W-11 與 🎯 精選須先出線框草稿裁示。

### DEC-139｜ChatGPT 文件／治理與 Claude Code 程式施工分工（客戶 2026-11-05）

- **使用者裁示（本次對話）**：「簡單來說是這樣嗎?文書交給我，程式交給 Claude Code」；經確認後要求「請寫進記憶中」「那就開始吧」。其中「我」依前後文指 ChatGPT。
- **分工**：ChatGPT 直接負責產品設計、UI／UX 草稿、文件撰寫與維護、正式規格整理、GitHub 唯讀驗證、文件型 PR 與合併治理、獨立驗收；Claude Code 負責應用程式、測試與自動化的實作／除錯／執行 QA，依明確核准的規格施工。使用者保留新 Layout、重大風險、付費、權限及不可逆操作最終裁示。
- **最小重工**：ChatGPT 已產出可驗證的正式文件／決策／設計時，不再要求 Claude Code 重寫或重做相同研究。Claude 因程式施工需同步修改測試、技術文件或交接時，可在原施工 PR 一併處理；禁止為形式化分工拆出無意義 PR。
- **不改安全治理**：GitHub Verification Gate、既有 CLAUDE.md／PROCESS.md 的程式施工協作與獨立 QA、CI、branch protection、不得直接改 main、Auto-Ship Gate、Data／AI 分離與正式 Decision 權威均不放寬。ChatGPT 直接提交文件仍須符合既有 PR／CI／QA 流程；此裁示不構成任何 UI、OAuth 或 OneBrain 程式施工授權。
- **衝突處理**：本裁示是 ChatGPT／Claude 之間的工作責任分配，不等於取消 Claude Code 執行程式任務時其內部 subagent 派工及獨立 QA 義務；若上位程序對 ChatGPT 直接撰文有不同解釋，須明確標示差異、依既有治理處理，不得默默宣稱已修改上位憲法。
- **決策者**：使用者。**效力**：2026-11-05 起的跨對話協作偏好；**落盤**：本 docs-only PR，合併後才成為 main 上正式紀錄。


### DEC-140｜資料分層與死碼清理改由 ChatGPT 主責；與 Claude 工作衝突時 Claude 優先（客戶 2026-11-05）

- **客戶原話**：「這部分能有你執行嗎? 不由專案AI，那如果跟專案AI有衝突時，請先以專案AI工作為主」。
- **範圍**：對本次 `my-stock-dashboard` 的資料分層剝離、確認死碼與安全清理，**ChatGPT 可直接負責程式修改、文件、PR 與獨立驗收協調**；不再預設必交給 Claude Code。屬 DEC-139「Claude 原則上主責程式」的**明確特定任務例外**，不是全面推翻分工。
- **衝突規則**：Claude Code 目前／後續已授權工作**優先**；ChatGPT 每批修改前重新確認 GitHub main、Open/Draft PR、head/diff、branches、CI 與預定檔案 owner。若同檔或同資料契約／同測試／同 workflow／同 SSOT 有重疊，ChatGPT **停止或縮小自己的批次**，不可覆蓋、推擠或重設 Claude 分支；不要求 Claude 為本次清理讓路。
- **落地要求**：安全小批、獨立 branch／PR、必要 tests／CI／獨立 QA；無法取得完整工作樹或執行足夠驗證時僅能唯讀探勘／文件化，不得將未驗證刪碼合併或宣稱已完成。對不可逆資料、Risk Cap、來源／公式與 UI Layout 仍適用原有客戶 Gate。
- **決策者**：使用者；**範圍**：本次資料架構與死碼清理特例；**日期**：2026-11-05。此 DEC 合併到 main 前僅存在於 PR 分支。


## 2026-11-07｜未合併 Draft 已有客戶裁示之正式索引收斂

> **治理說明**：下列 DEC-141～145 是從 #1027、#1030、#1034 的既有客戶裁示紀錄遷入，而非新增客戶授權。各 DEC 內「本 PR 尚未合併」、2026-11-06 舊 main/PR 及過期工作狀態，均為**原始提案時點的歷史註記**，不能作為 2026-11-07 現況；其衝突 PR 仍需另行收斂。五頁頂部導航為已確認的**產品方向**，不等於視覺、Auth、Schema、OneBrain runtime 及程式施工核准；保留舊歷史 DEC，依最新 Gate 分批取代舊呈現條文。

### DEC-141｜💼 持股 W-11 未完成部分：客戶核准 Q1~Q8，授權純版面／空槽施工（客戶 2026-11-05）

- **裁示**：Q1=A（Primary 與 ⑤ 在上、持股表在下；手機沿用已核准順序）；Q2=產業曝險／集中度為 Primary 主圖，績效／benchmark 在次要區不取代；Q3=手機無資料 Primary 收成一行明確空槽、桌機維持預定高度、施工後重測手機首屏；Q4=資料日沿用 DEC-102「多數＋例外分組」，不得以最舊一檔／今日／抓取時間冒充，未接線前顯示「⬜ 資料日未提供」，不授權新增組合層日期計算或來源；Q5=⑤「建議持股水位（市場端）」僅空槽，不讀 Risk Cap 數值、不呼叫會寫 session 的服務、不得暗示已有投資上限；Q6=「今日需處理」合為一行，Aggregator 前維持「⬜ 尚未提供」，不計算動作、不顯示「今日無需調整」；Q7=欄名＋原因，桌機八欄／手機四欄加展開，無登入資料不顯示假列／假成本／假報酬、不把未登入判為持股 0 檔；Q8=不開放 `gsheet_sa_reader`／cron 快照／Service Account 接入 UI2。
- **授權範圍**：**僅**版面／欄位結構／空槽。**不授權**正式資料接線、Auth、Risk Cap、System Action、OneBrain、Digest、投資公式。W-11 須通過施工與獨立 QA 驗收才能標完成。詳見 `docs/vnext/NEWUI2_HOLD_W11_REMAINING_DRAFT_2026-11-05.md` §8。
- **決策者**：客戶（2026-11-05）。｜**效力日期**：2026-11-05 起。｜**範圍**：New UI2 💼 持股頁 W-11。｜**不推翻** DEC-138（Dark-only；未完成部分不得宣稱整頁完成）。
- **狀態**：本 DEC 位於 docs PR #1027（draft，未合併）；合併到 main 前僅存在於 PR 分支。


### DEC-142｜New UI2 五頁頂部導航＋六領域 OneBrain 整合與規則清理（客戶 2026-11-06）

- **客戶本對話明確確認**：「Sheet 的分頁選單可以改成上方嗎 左側的收縮板可以不用了」；「這張是參考圖」；「記得把新的規則寫進GitHub 中，移除不適用的規則，避免專案AI看錯，做錯」；「還有稍早談的都要喔」；提供基金專案唯一資料層/Evidence/Digest/分域 OneBrain＋全域整合的架構圖片，並確認「記得新增規則，移除不適用規則」。
- **產品方向**：採台股 New UI2 五頁（市場、標的、持股、我的、資料）＋手機與桌機頂部導航、頂部 Active Sheet 選擇器、右上帳號入口，不再以左 rail 或手機抽屜作新版正式呈現方向。Dark-only、Mobile-first、登入安全不變；基金截圖僅作 UX／AI 架構參考，不得移植基金公式。
- **OneBrain 方向**：單一核准資料層／Evidence Registry／確定性 Domain／UI ViewModel 與完整 Decision Digest 分離；**一套 OneBrain 協調六個台股研究單元**（市場、籌碼、財報、產業、持股、資料稽核），分頁 scoped 啟動，另以全域複查回查證據與反證，所有報告使用白話文。短／中／長（非固定 3/6/9）；AI 嚴格禁止自行取外部事實或寫入，Token 超限不能靜默漏料，依必要證據清單與確定性 coverage Gate 降級 partial。
- **已討論的承接**：第一版財報體檢、法人／集保、國際市場、持股與 ETF 曝險能力保留；C 級只主動研究使用者提供的 2026/10 市場 PDF 有關大盤 EPS×PE、外資融資、國際利率與 AI 產業／FCF，其他 C 級候選此次不研究；正式介面用中性名稱。
- **取代範圍**：舊四頁上限、👤我的內建完整資料健康度、桌機左 rail、手機 drawer 等**舊布局要求不再是新 UI2 的下一輪施工依據**，並於 PROJECT_RULES/Active Contract/Drawer Contract 標為 superseded；**不刪歷史裁示、正式程式/guards**。Single Action Authority、Risk Cap、資料狀態及缺值/來源有效性保留。
- **施工限制**：這是已確認方向及設計規範，**不代表新 UI2 Layout/路由/Sheet OAuth/AI runtime/投資公式已獲准直接修改**；須先完成五頁視覺、資料契約、跨模組安全及測試 Gate，特別是 JS_V4 退場必須等價測試替代。PR #1030 為 Draft，合併與獨立 QA 前不能宣稱 main 已採用。
- **決策者**：使用者；**日期**：2026-11-06；**來源**：本次對話客戶訊息（直接原文部分引文如上），詳細建議與未授權事項為 ChatGPT 設計解讀。


### DEC-143｜GitHub 對話記憶與正式治理同步、第一版資料資格審查列為 New UI2 前置 Gate（客戶 2026-11-06）

- **客戶原話／釐清**：「抱歉我說的記憶不是gpt的記憶，是存放在github中的我跟你的對話」；「對了 我們的對話還有包含判斷那些資料是不可用，要加以篩選，以及判斷產業是否缺貨，財報變化那些，所以要看第一版UI的資料哪些可以用，這個執行了嗎？」；「還有要更新的是 GitHub 內的對話記憶與正式治理文件。」
- **裁示範圍**：所謂「記憶」是 GitHub 中對話提煉出的**有效專案知識／設計／裁示／接手點**，不是 ChatGPT 帳戶 Memory；須同步落在既有五治理文件，**不建立平行聊天 SSOT、也不把所有聊天逐字存進 repo**。對過期資訊採標記 SUPERSEDED／HISTORICAL 並修正有效摘要，歷史 DEC 原文保留。
- **資料資格前置 Gate**：第一版 Old UI／Legacy New UI 的資料、公式、缺貨／訂單研究、財報跨季與籌碼服務，**有程式≠已驗證可用≠New UI2 已接線≠OneBrain 已讀到完整 Evidence**。先逐項審查「來源存在／端到端實取／資料語意與口徑／新鮮度與缺值／計算正確性／Digest 覆蓋／UI2 接線」，不可用與不可信資料不得流入正式投資建議；用原始狀態與原因揭露，不能以 0／neutral／safe／未觸發代替。
- **特定模型風險列入驗收**（2026-11-06 main 源碼讀取，屬**稽核發現、非修改既有算法授權**）：① `shortage_screener_service`／`shortage_screener` 使用合約負債、毛利率、存貨天數、月營收 YoY 辨識**疑似**缺貨足跡；月營收缺值 C4 記 0 分，其他三項仍可 rankable，不能說已證實缺貨／大型訂單。② `fin_trend_score` 65% 月營收＋35% 季財報缺腿可能以 0 分形成「中性」總標籤；需測試 coverage 與降級，不得把缺資料說成沒有變化。③ `financial_health_engine` 需複核現金流累計／單季與缺科目 0。詳見 PR #1033 的 `NEWUI2_SUPERSESSION_AND_DATA_GAP_AUDIT_2026-11-06.md` §G。
- **處理路線**：優先修復／承接已存在的核准來源，其次薄 L3 adapter；確無正式來源時才提出官方 API／授權或研究用 Sheet 候選。**未完成 live API probe 時只能標 NOT_VERIFIED；不能把「repo 無 fetcher」當成「外部數據永不可取得」。**
- **與既有產品裁示的關係**：New UI2 五頁＋頂部導航、六領域協調 OneBrain 與 UI ViewModel／Decision Digest 雙投影，依 PR #1030 中 DEC-142 草案對照；保留 Risk Cap／Single Action Authority／缺值規則；本裁示**不自動核准**新資料來源、新 Sheet schema、行情推估公式、OneBrain runtime、布局施工或交易指令。
- **治理處理**：`PROJECT_STATE` 保存有效知識、`DECISIONS` 保存本裁示與 supersession、`BACKLOG` 保存待做 Gate、`HANDOFF` 保存最新可恢復接手點、`PROJECT_RULES` 保存工作流程與權限限制；與 #1027/#1030/#1032 相關文件並行修改**必須先協調順序、重新比對 diff／CI／獨立 QA**，不能覆寫其他工作。
- **決策者**：使用者。**日期**：2026-11-06。**證據限制**：本 session 原文，A/B/C 資料來源判定須逐案測試；本治理 PR 與 #1030/#1033 尚未合併前，**main 未生效**。**實作狀態**：僅 docs-only Gate；未作 live probe、產品實作或正式數據篩除。


### DEC-144｜三方案比較、推薦、最小人工介入與避免原地試錯（客戶 2026-11-07）

- **客戶原話（來源 D，本次對話）**：「我給你新的想法，以後你要問我之前先給三種方法，然後評估哪種方法比較，你推薦的，所以你這問題再一次」；後續指示「請繼續」。此前亦授權「這些你能做 我授權你繼續」。
- **正式裁示**：處理尚待解決的問題，尤其請客戶操作前，先查最新 GitHub 實況，主動提出三條實際可行方案，逐項比較正確性／風險、速度、Token／成本、可逆性、人工操作量，並明確推薦最適方法。優先自主執行已授權、安全可逆且工具支援的工作，不堅持單一路徑、不重複原地試錯、不重跑已在執行的 CI、不無意義依賴客戶手動操作。若權限或工具不支援，須透明揭露，並提出最小必要人工操作與備選方案。
- **案例（狀態非最終結果）**：2026-11-07 GitHub 查核時 #1036 head 905def98、#1037 head dfbc8559、#1038 head 9e7014c7 的原生 PR CI 已從 action_required 轉為 in_progress，應沿用既有 CI 而非重複要求客戶批准。舊 head 綠燈不得套用新 head；必要檢查與 parquet、metadata、觀測日期仍須獨立複驗，不能宣告三 PR 已可合併。
- **安全邊界**：不改上位 CLAUDE.md／PROCESS.md 與既有授權 Gate；不得跳過 required CI／獨立 QA、偽造資料來源證據、變更 Risk Cap／公式或未經核准的新 UI Layout；只能執行 GitHub 工具確實提供的動作，不得聲稱可用不存在的 workflow-approval 操作。
- **決策者**：使用者。**日期**：2026-11-07。**範圍**：my-stock-dashboard 跨 AI 協作、請示與問題解決。**落盤**：#1034 docs-only Draft PR，合併前不視為 main 生效。


### DEC-145｜每小時 GitHub 巡檢留下可恢復紀錄；非必要靜默，直到需給 Claude 提示語（客戶 2026-11-07）

- **客戶原話（來源 D，本次對話）**：「記得每一次巡檢 要去難GITHUB裡面的內容，進度，未完成項目還有需要處理的事項，工作項目就根據之前談的 專案AI負責寫CODE，需要他的時候 你貼出來 我會再貼給她處理，有回覆會再跟你說」；「對了 你也需要做紀錄喔 我怕對話太長中斷，你也能靜默處理嗎? 直到要給專案AI提示語在提供」。
- **裁示**：既有每小時巡檢應真正讀 GitHub 最新 main、PR/diff/head、CI/QA、branch、規格及五治理文件。需持久保存的有效進度、未完成事項、風險、決策與下一步走既有文件 checkpoint，不能依賴 ChatGPT 長對話；在工作不衝突且符合 CI／PR 治理下，ChatGPT 可自主處理文書，Claude Code 主責寫 CODE，只有需要 Claude 的明確工程工作時才向使用者提供完整可複製提示語（附模型、Effort、範圍、驗收與停止條件），使用者轉貼並回報。原則上**靜默**，例行狀態、無變化與文書中間進度不通知；真正客戶 Gate、Claude 新提示語、必要交接例外。
- **長對話恢復**：ChatGPT 應在關鍵階段先把正式紀錄保存到 GitHub，再給可複製的新對話交接摘要；不得宣稱能在使用者離線時測量剩餘 token、自動遷移對話或無限背景施工。定期任務每小時只在支持的工具／權限／既有授權內行動；Draft 仍非 main 生效。
- **決策者**：使用者。**日期**：2026-11-07。**落盤**：#1034 docs-only Draft PR，合併前未生效於 main。


### DEC-146｜五頁頂部導覽視覺方向核准；不做臨時五頁 Drawer B0（客戶 2026-11-07）

- **客戶原文**：「我核准方案 B 作為五頁頂部導覽的視覺方向，不做臨時 B0 五頁抽屜。請將裁示寫入 GitHub，收斂正式線框與安全驗收條件，再安排 Claude Sonnet＋Medium 最小施工；未通過安全 Gate 不得合併。」
- **方案標籤／來源分界（ChatGPT 設計解讀，非客戶逐字）**：客戶**已明確確認**「方案 B 作為五頁頂部導覽的視覺方向」及「不做臨時 B0 五頁抽屜」（見上方客戶原文）。依本次對話中 GPT 所提供的流程比較，這裡的「方案 B」是**直接以正式頂部五頁為目標、先完成視覺與安全 Gate、再最小施工**，**不是** #1048 提案 §A 另列的「方案 B：手機所有內容擠單一列」。GPT **進一步將**客戶核准方向具體對映到 #1048 §A 的**方案 A（兩列）**：第一列 Active Sheet/帳號、第二列五頁導航、🗂資料第五，手機橫向捲動，桌機不留 rail，手機不留 Drawer；Dark-only、Mobile-first。客戶**沒有逐字使用「#1048 §A」或「A1」這些對映代號**；此處對映為 GPT 的設計詮釋，不得記成客戶明示逐字核准該代號或固定像素。**不允許先將舊 Drawer/rail 做成五頁作臨時 B0 合併。**
- **實作授權邊界**：准許依上述設計收斂最小 UI2 五頁路由、🗂誠實 Preview 空殼、頂部雙列導覽及相依測試；施工/交付須遵循獨立正式 Visual/Safety Gate 文件 `docs/vnext/NEWUI2_TOP_FIVE_APPROVED_VISUAL_AND_SAFETY_GATE_2026-11-07.md`，同一完整可合併工程 PR 不得留下臨時五頁 Drawer。現行 `shared/ia_nav4` 舊 UI 契約不得直接擴充；現有資料/Action/JS/a11y 守衛不能偷刪或降級。
- **硬限制**：新導航須真實 390×844／1440×900、Streamlit 1.56/1.59.2 測試；保住 `p2_nav_margin_160` ≥160px 與首屏 CTA，既有 JS_V4/focus/keyboard/inert/ESC 的等價守衛及有效 Evidence、正式 CI/QA。未通過真瀏覽器、安全、最新 head CI、獨立 QA 不得 merge，應回到設計 Gate 修正。核准的是**方向**，不是未實測的具體像素或已完成工程。
- **不包含**：正式 Auth/Sheet 與持續登入、真資料健康度欄位/分母與來源、Digest/OneBrain runtime、Schema、新 API/財報與投資公式、Risk Cap/System Action、production switch 或 Old UI 刪除，均須各自 Gate；欠缺資料只能顯示誠實未接線／無法判定。
- **決策者**：客戶｜**日期**：2026-11-07｜**來源**：本次對話客戶直接原文（D）｜**狀態**：方向已裁示；工程尚未完成，安全驗收待證｜**取代關係**：細化 DEC-142 下一版布局；舊四頁 Drawer/rail 僅是現有 runtime 的回歸基線，非下一版施工目標。此決策進 main 前屬本 docs PR 待合併內容，不得宣稱已生效於 main。


### DEC-147｜ChatGPT／Claude Code 角色分工更新：Claude Code 負責施工、獨立 QA、PR Merge、Branch 清理與正式治理文件同步（客戶 2026-11-07）

- **客戶逐字**（來源：使用者對話訊息，2026-11-07；來源類別 D；原樣引用，不得改字）：
  > 使用者已決定：
  > * ChatGPT：產品規劃、UI/UX、架構、投資語意、需求與 Decision Gate。
  > * Claude Code：CODE 施工、修復、獨立 QA、CI 驗證、PR Merge、Branch 清理、正式治理文件同步。
  > * Claude Code 可在既有核准範圍及安全 Gate 內自主完成 PR 合併，不需每次回 ChatGPT 等待 Merge 裁示。
  > * 施工組與獨立 QA 組必須分離，作者不能自行宣稱完成非作者驗收。
  > * 遇到需要使用者裁示的高風險事項，仍須停止。
  > 請將本次分工變更寫入本 repo 正式治理文件，採最小必要差異，以 PR 流程入庫，不直接修改 main。
- **客戶逐字（同訊息，Branch 清理與批次條件）**：「分支只有在確認沒有其他使用者或工作流程依賴、獨有內容已保存後才清理。」「不強制合併過時 Draft。」「#1038 的 PIT 問題維持阻塞，未通過來源時間與資料資格驗證前禁止合併。」「同一時間最多三項安全工作。」
- **撰寫組整理（非客戶逐字，單組產出、未經第二組驗證）**：
  1. **取代關係**（有意識的政策變更，不是漏刪；決策者：使用者）：
     - 取代 DEC-139 中「ChatGPT 直接負責…文件撰寫與維護、正式規格整理、…文件型 PR 與合併治理、獨立驗收」的**正式治理文件同步、合併治理、獨立驗收歸屬**，改歸 Claude Code；
     - 取代 DEC-140「ChatGPT 可直接改程式」對**未來批次**的效力（DEC-140 已完成批次，以及「與 Claude 衝突時 Claude 優先」維持有效）〔撰寫組推論，待使用者確認〕；
     - PROJECT_RULES 第 31 節表中「GitHub 狀態、Diff、PR／CI／QA 複驗與文件 PR 治理」改歸 Claude Code 獨立 QA 組＋PR Merge；「文字文件與 Decision 記錄」中的**正式治理文件同步**改歸 Claude Code；ChatGPT 保留產品規劃、UI／UX、架構、投資語意、需求、Decision Gate 與文件草稿〔「文件草稿」為撰寫組推論，待使用者確認〕。
     - **兩邊理由並陳**：舊條文理由（讓 ChatGPT 承擔文書以減少 Claude 重工）仍然成立；被權衡掉的是「Merge、QA 與正式文件同步須落在可實測 CI 的環境」。
  2. **不取代**：DEC-001、DEC-004（merge 常設授權）、DEC-009、`PROCESS.md` §4、`CLAUDE.md` §-2 均繼續有效。
  3. **自主 merge 前置條件**＝PROJECT_RULES 第 10 節三項（獨立稽核無必修、CI 綠、改動範圍與派工相符）＋**本決策新增（收緊）**：最新 head 原生 CI 綠（含 required `ui2-browser-gate`）；mergeable；無未解 review thread；合併前後重新查 main SHA；以 GitHub 實際 merged 狀態為完成證據；squash merge。不得 force push、admin bypass、關閉或繞過 branch protection、以 `workflow_dispatch` 冒充 required check。
  4. **Branch 清理**：單一條件——僅在確認無其他使用者或工作流程依賴、且獨有內容已保存（已入 main 或另存）後才清理；「已 merge」只是可能符合條件的情形之一，不是免查依賴的理由。DEC-147 為使用者對 DEC-012「分支刪除不得自主」及第 10 節同名條文的**有條件授權**，以此條件為準；**不得清理**：`main`、`data`、`v2`、`auto/recalibrate-20261001`（遠端現已不存在，仍列入保留名單）、`claude/stock-dashboard-handoff-g9dtm0`、含未保存獨有內容者、仍有開啟 PR 者。清理前須列出 unique commit 並確認已入 main 或另存。
  5. **作者≠QA**：施工組與獨立 QA 組分離；QA 結論須由非作者的獨立組產出並可追溯（PR 描述／評論）。ChatGPT 審閱意見可作輸入，但不取代 repo 要求的獨立 QA；Claude Code 總管不得自驗自己動手寫的內容（`CLAUDE.md` §-2）。
  6. **仍須停止並請使用者裁示**：新 Layout／欄位／動線；付費；權限；不可逆操作（刪生產資料、清單外刪分支、production switch、舊 UI 實體刪除）；新資料來源／公式／Risk Cap／OneBrain 正式行為；文件無法證明已核准的範圍。#1038 的 PIT 阻塞維持：未通過來源時間與資料資格驗證前禁止合併。不強制合併過時 Draft；同一時間最多三項安全工作。
- **決策者**：使用者｜**日期**：2026-11-07｜**來源**：使用者對話訊息（D）｜**狀態**：進 main 前屬本 docs PR 待合併內容，不得宣稱已生效於 main。


### DEC-148｜D1 以實際來源觀測日判斷新鮮度、D3 空抓取三態分類（客戶 2026-11-08）

- **客戶逐字裁示**（來源：使用者對話訊息，2026-11-08；來源類別 D；原樣引用，不得改字）：
  > 我正式核准 D1 以實際來源觀測日判斷新鮮度、D3 採 NO_NEW_DATA／FETCH_FAILED／UNDETERMINED 三態分類。請依最新 GitHub 狀態更新 Claude Code 提示語，分批施工並遵守資料語意及安全 Gate。
- **決策者**：使用者（客戶）｜**日期**：2026-11-08｜**來源**：使用者對話訊息（D）｜**狀態**：進 main 前屬本 docs PR 待合併內容，不得宣稱已生效於 main；Batch A／B／C 待施工。本裁示把 BACKLOG `NUI2-DATA-1054-REVIEW` 中原記為「ChatGPT 建議、提案待客戶直接確認」的 D1／D3 轉為**客戶已核准**。
- **授權範圍**（以下為依客戶裁示與 D1／D3 提案整理的資料語意，授權僅限 D1／D3 的資料語意與**必要最小施工**）：
  1. **D1（新鮮度以實際來源觀測日判斷）**：
     - 新鮮度取**可信的實際來源觀測日**；cron 執行時間、`fetched_at`、`cached_at`、`metadata.updated_at` 只代表各自的時間，**不得覆蓋資料觀測日**。
     - UI「資料日」只顯示**可信來源觀測日**。
     - 缺可信資料日／資料日晚於合法決策時點／來源時點矛盾 → **不得判 fresh**，須誠實降級並**保留診斷原因**。
     - **保留 `SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS` 現行門檻**（不改數值）。
  2. **D3（空抓取三態分類）**：
     - `NO_NEW_DATA`：有**正面證據**證明請求與來源讀取成功，且在可確認範圍內無新觀測；**不是失敗，也不保證舊資料 fresh**。
     - `FETCH_FAILED`：明確的網路／API／認證／解析／欄位驗證錯誤；**保留錯誤證據**。
     - `UNDETERMINED`：空回應或證據不足；採保守處理，**不得以週末推論成功**。
     - 三態與 freshness **分離**、**不取代 Last Good 觀測日**、**不把空抓取寫成 0／neutral**、**不吞例外**。
- **未授權**（維持需另行裁示）：新資料來源；任意修改新鮮度門檻；投資公式；Risk Cap；OneBrain runtime；正式 UI Layout；付費或不可逆操作；**不得擴充到其他資料契約**。
- **施工順序與流程**：Batch A（D1）→ Batch B（D3）→ Batch C（財報跨期 `src/compute/health/fin_trend_score.py` 與產業缺貨 `shortage_screener` 資料資格**唯讀稽核**，**不改正式分數**）。D1／D3 **分開工程 PR**。每批：GitHub Gate → 最小施工 → targeted tests → 非作者獨立 QA → 最新 head 原生 CI → squash merge → 文件同步。涉及正式公式／權重／排名資格／Risk Cap 變更時**必須停止並走 Decision Gate**。
- **與既有決策的關係（引用，不改寫）**：
  - **DEC-143**：第一版資料資格審查為前置 Gate（有程式≠已驗證可用；缺資料不得以 0／neutral／safe 代替；`fin_trend_score` 缺腿以 0 分形成「中性」、`shortage_screener` 缺值計 0 分仍 rankable 等為**稽核風險**）。本裁示僅授權 D1／D3 與 Batch C 的**唯讀**稽核，DEC-143 其餘 Gate 維持；不自動核准新來源、公式或 OneBrain runtime。
  - **DEC-147**：Claude Code 負責施工、獨立 QA、PR Merge、Branch 清理與正式治理文件同步；自主 merge 前置條件、作者≠QA、「仍須停止並請使用者裁示」清單、「同一時間最多三項安全工作」均**原樣適用**於本裁示的 Batch A／B／C。本裁示是**在其框架內**對 D1／D3 的資料語意核准，不放寬 DEC-147 任何條件。
- **證據限制**：本條為客戶裁示的入庫紀錄；「授權範圍」逐點為依提案整理，非客戶逐字（逐字僅上方引文）。**實作狀態**：本條僅 docs；Batch A／B／C 尚未施工；發布端到端與 Cloud 部署仍 NOT VERIFIED。


### DEC-149｜財報跨期 65/35 不重配且資料不足不產正式評級、缺貨排名至少兩項有效獨立證據、四項全缺排除正式排名（客戶 2026-11-08）

- **客戶逐字裁示**（來源：使用者對話訊息，2026-11-08；來源類別 D；原樣引用，不得改字）：
  > 我正式核准：財報維持65%／35%原始權重，必要資料不足不得產生正式綜合評級；缺貨排名採至少兩項有效獨立證據的資格方向，證據不完整的強缺貨訊號先研究降級或封頂，正式門檻經歷史案例與負測驗證；四項全缺排除正式排名，但保留無法評估診斷。
- **決策者**：使用者（客戶）｜**日期**：2026-11-08｜**來源**：使用者對話訊息（D）｜**狀態**：進 main 前屬本 docs PR 待合併內容，不得宣稱已生效於 main；施工分批進行，尚未完成任何一批。本裁示是客戶對 BACKLOG `NUI2-FIN-CHANGE-QUALIFICATION`、`NUI2-SHORTAGE-VERIFIED-EVIDENCE` 中 Batch C 稽核所提「需 Decision Gate」項的**方向核准**（DEC-148 後的客戶第二個直接裁示）。
- **已核准邊界**（以下為依客戶裁示整理，授權僅限所列方向）：
  1. **財報跨期**：維持 `fin_trend_score` 月營收 **65%**／季財報 **35%** 原始權重，**不重配權**；**必要資料不足時不得產生正式雙頻率綜合評級**；兩腿資料足夠且合法時**維持現有計算**（不改正式公式與權重）〔**整理／推論（非客戶原文）**：客戶原句未明寫此點，由「維持 65%／35% 原始權重」推得，待客戶確認〕。
  2. **缺貨排名**：採「**至少兩項有效、獨立證據**」的資格方向。
  3. **四項全缺**：排除正式排名，但**保留可回查的「無法評估」診斷**。
  4. **證據不完整的強缺貨訊號**：**先研究降級或封頂**；**正式門檻須經歷史案例與負測驗證**後才可定案。
- **尚未裁定（明列，維持需另行裁示或另有既有定義可判定者才可施工）**：
  - 具體**封頂級別／分數**（「研究降級或封頂」**不得被解讀為已核准任何具體封頂分數**）；
  - 「**有效**」與「**獨立**」的正式定義細節——若無法由既有正式定義判定，須另行裁示；
  - 資料充分門檻的**例外**；
  - **新計分權重**；
  - **重大排序策略**。
- **未授權**（維持需另行裁示）：Risk Cap；投資門檻；新資料來源；UI2 Layout／Auth／Sheet／OneBrain runtime；付費或不可逆操作。D1／D3 的範圍**仍受 DEC-148 拘束**，不因本裁示擴大。
- **施工分批**（每批獨立 PR＋非作者 QA＋最新 head 原生 CI＋squash merge＋文件同步，沿用 DEC-147 流程）：
  1. **D3 B2 消費端一致性**（`macro_cache_reader`、`real_canonical`、`_market_blocks`、`calibrate_health_weights.check_inputs_fresh` 對 `FETCH_FAILED` 不放行；範圍受 DEC-148 拘束）。
  2. **財報缺值資格修復**（優先重用既有 `is_trend_scorable`；**不改正式公式與權重**；單股 Tab／AI prompt 缺值不得顯示或送出「中性 +0.00」）。
  3. **缺貨資格 Gate**：Phase 3A＝證據與歷史案例比較（唯讀研究，含降級／封頂候選與負測）；Phase 3B＝僅限已核准的安全修正（兩項證據資格、四項全缺排除並保留診斷）。具體封頂分數、有效／獨立定義細節、例外與新權重不在 3B 範圍，須另行裁示。
- **與既有決策的關係（引用，不改寫）**：
  - **DEC-143**：第一版資料資格審查前置 Gate（缺資料不得以 0／neutral／safe 代替）；本裁示是對其所列 `fin_trend_score` 缺腿記 0 與 `shortage_screener` 缺值記 0 仍 rankable 兩項稽核風險的方向裁示，DEC-143 其餘 Gate 維持，不自動核准新來源、公式或 OneBrain runtime。
  - **DEC-147**：施工、獨立 QA、PR Merge、Branch 清理與文件同步歸屬、作者≠QA、「仍須停止並請使用者裁示」清單均原樣適用於上列各批，不放寬。
  - **DEC-148**：D1／D3 資料語意與 Batch A／B／C 順序維持；本裁示的第 1 批（D3 B2）即其延伸，範圍不得擴充到 DEC-148 之外的資料契約。
- **證據限制**：本條為客戶裁示的入庫紀錄；「已核准邊界」「尚未裁定」「施工分批」為依裁示與 BACKLOG Batch C 稽核整理，非客戶逐字（逐字僅上方引文）。Batch C 稽核為單組 grep／讀碼結論，未經第二組獨立驗證，剛上市專屬行為、真實 FinMind 缺值頻率與部署行為 NOT VERIFIED。**實作狀態**：本條僅 docs，上列三批均尚未施工。


### DEC-150｜財報缺腿不產正式評級、缺貨證據資格方向、C4 缺月不得認連續加速、無法評估檔數揭露（客戶 2026-11-08）

- **客戶逐字裁示**（來源：使用者對話訊息，2026-11-08；來源類別 D；原樣引用，不得改字）：
  > 我正式核准你建議的六項方向：財報缺任一必要腿不產正式綜合評級；接受空快照資料資格修正造成的排序變化；缺貨證據採品質、不同經濟機制、日期和來源雙重驗證，具體准入條件先驗證；強缺貨缺證據時留研究清單、不立即訂固定封頂；C4 缺月份不得認定連續加速；在既有相關畫面揭露無法評估檔數。請依最新 GitHub 獨立查核整合完整 Claude Code 提示語，分批施工，未核准數值或重大公式變更須停手。
- **決策者**：使用者（客戶）｜**日期**：2026-11-08｜**來源**：使用者對話訊息（D）｜**狀態**：進 main 前屬本 docs PR 待合併內容，不得宣稱已生效於 main；施工分批進行，**本條僅 docs，尚未施工**。本裁示是客戶對 DEC-149 之後 BACKLOG `NUI2-FIN-CHANGE-QUALIFICATION`、`NUI2-SHORTAGE-VERIFIED-EVIDENCE` 所列「待客戶裁示」(1)～(7) 的**方向核准**（DEC-148、DEC-149 後的客戶第三個直接裁示）。
- **(1) 已核准行為**（以下為依客戶裁示整理，授權僅限所列方向；每點與客戶原句的對應見括號）：
  1. **財報缺任一必要腿不產正式綜合評級**（對應「財報缺任一必要腿不產正式綜合評級」）：
     - `fin_trend_score` 月營收腿或季財報腿**任一**缺少，即**不產生正式雙頻率綜合評級**；**65%／35% 原始權重不變、不重配**（DEC-149 已核准，本條不改）。
     - 缺腿時**合法分項可顯示**，但須**明示非完整評級**；不得顯示「中性 +0.00」或以 0 分充當完整評級。
     - **資料完整且真實為 0 時仍為中性**（真 0 與缺值必須可分）。
     - **單股 Tab、組合 Tab、AI prompt 的資格判定須一致**（同一份資格結果，不得各自判斷）。
  2. **接受空快照資料資格修正造成的排序／計數變化**（對應「接受空快照資料資格修正造成的排序變化」）：#1068 已使部分舊判可評分的列變為不可評分，影響組合 Tab ⚪ 計數與排序，**客戶已接受**；後續施工須**留前後差異證據**（PR 描述可回查）。
  3. **缺貨證據資格方向**（對應「缺貨證據採品質、不同經濟機制、日期和來源雙重驗證」）：判斷某項證據是否算數，方向為「**資料品質＋不同經濟機制＋日期與來源雙重驗證**」；**具體准入條件須先驗證**，見 (2)。
  4. **強缺貨缺證據時留研究清單、不立即訂固定封頂**（對應「強缺貨缺證據時留研究清單、不立即訂固定封頂」）：證據不完整的強缺貨訊號**進研究清單**；**現階段不設任何固定封頂級別或分數**。
  5. **C4 缺月份不得認定連續加速**（對應「C4 缺月份不得認定連續加速」）：`[20, None, 40]` 這類中間缺月的序列**不得算連續加速**，**亦不得未經驗證就當成負成長**。
  6. **在『既有相關畫面』揭露無法評估檔數**（對應「在既有相關畫面揭露無法評估檔數」）：**不新增獨立功能頁**；**分母與互斥分類須先定義**；**未取得分母不得顯示 0**；**不得以此繞過 Layout Gate**（新 Layout／欄位／動線仍須先出文字線框草稿，見 DEC-147 第 6 點與 `CLAUDE.md` §-1.5.D §03-2 ①）。
- **(2) 尚待驗證的具體資格定義**（**不是已核准**；無法由既有正式定義判定者須**停手**，另行裁示）：
  - 缺貨「**具體准入條件先驗證**」：「有效」「獨立」證據的**正式定義**、**證據矩陣**（C1～C4 各自依賴的資料集與經濟機制）、是否需要**獨立性判定權重或相關係數門檻**——**這些均未核准**，不得臨時創造。
  - C4 月份**日期契約**：若 producer 沒有可信的月分識別，須先提**最小資料契約方案**（走 Decision Gate），不得靠位置推測月份。
  - 「**有效月營收**」「**有效季財報**」：若無足夠的既有正式定義，**不得臨時創造期間或完整度門檻**。
  - 畫面揭露的**分母**與**互斥分類**定義。
  - 歷史案例仍 **NOT VERIFIED**（`picks.parquet` 僅 5 期 100 列，無缺貨分數與結果報酬）。
- **(3) 禁止自行變更**（維持需另行裁示）：新權重；數值閾值；證據獨立性公式；**強缺貨固定封頂（含「3 項有效＝降為中度」）**；重大排序例外；新資料來源；正式 Layout；Risk Cap；OneBrain runtime；OAuth／Sheet；付費或不可逆操作。**「研究方向」不得被解讀為已核准任何數值規則。**
- **施工分批**（沿用 DEC-147 流程：每批獨立 PR＋非作者 QA＋最新 head 原生 CI＋squash merge＋文件同步；**未核准數值或重大公式變更須停手**）：
  1. **Batch A｜財報缺腿一致性**：單股／組合／AI 資格一致；缺腿不產正式綜合評級、合法分項可顯示並明示非完整評級；65/35 不動。
  2. **Batch B1｜C4 連續月份**：缺月不認連續加速；先查 producer 是否有可信月分識別，無則先提最小資料契約方案再停手。
  3. **Batch B2／B3｜缺貨證據資格與研究分流**：僅限已核准方向（證據資格方向、強缺貨缺證據進研究清單）；准入條件的正式定義先驗證，不得自創。
  4. **Batch C｜畫面揭露無法評估檔數**：先定義分母與互斥分類；若需新 Layout／欄位／動線則先出線框草稿。
- **與既有決策的關係（引用，不改寫）**：
  - **DEC-143**：第一版資料資格審查前置 Gate（缺資料不得以 0／neutral／safe 代替）；本裁示是其 `fin_trend_score` 缺腿記 0、`shortage_screener` 缺值記 0 兩項稽核風險的進一步方向裁示，DEC-143 其餘 Gate 維持，不自動核准新來源、公式或 OneBrain runtime。
  - **DEC-147**：施工、獨立 QA、PR Merge、Branch 清理與文件同步歸屬、作者≠QA、「仍須停止並請使用者裁示」清單均原樣適用於上列各批，不放寬。
  - **DEC-148**：D1／D3 資料語意不變；本裁示不擴充到 DEC-148 之外的資料契約。
  - **DEC-149**：65%／35% 不重配、缺貨「至少兩項有效獨立證據」資格方向、四項全缺排除正式排名並保留診斷，**均維持有效**。DEC-149 所述「證據不完整的強缺貨訊號先研究降級或封頂」，本裁示的對應表述為「**留研究清單、不立即訂固定封頂**」；兩者併讀時，**以尚未核准任何封頂級別或分數為準**〔撰寫組整理：視為對 DEC-149 該句的收斂而非推翻，待客戶確認〕。DEC-149 已施工的三批（#1067、#1068、#1069）不因本條回溯變更；本條新增的行為（單腿缺不產正式評級等）由上列 Batch A 起另批施工。
- **證據限制**：本條為客戶裁示的入庫紀錄；「已核准行為」逐點、「尚待驗證」「禁止自行變更」「施工分批」為依客戶原句、使用者交辦摘要與 BACKLOG／HANDOFF 現況整理，**非客戶逐字**（逐字僅上方引文）。其中「合法分項可顯示並明示非完整評級」「單股／組合／AI 資格一致」等細部表述為整理，與客戶原句的對應關係待客戶確認。**實作狀態**：~~本條僅 docs，Batch A～C 均尚未施工~~（2026-11-08 已更新：Batch A 已 squash 合併 #1075〔`228e976`〕、Batch B 已 squash 合併 #1076〔`556b335`〕，兩者最新 head 原生 CI 全綠、各有非作者 QA；Batch C 整合驗證進行中，見 DEC-152；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；DEC-152）；發布端到端與 Cloud 部署仍 NOT VERIFIED。


### DEC-151｜C4 採最近三個完整且到公告時點的日曆月、可信月份鍵、保留缺值位置（客戶 2026-11-08）

- **來源標示（三類，勿混）**：**①客戶逐字裁示**＝下方引文區塊，僅此一句；**②客戶同日交辦文字**（原文轉述於同一則交辦訊息§1『已核准』清單等，**非單句逐字裁示**）＝(1)已核准七點、(2)五項分開判定、(3)時間語意、(4)未授權清單，及三批名稱與順序；**③AI 整理**＝預設推薦方案 B、Batch A／B／C 細節與負測清單、『屬連續性語意修復的資料契約』之歸類（待客戶確認）。
- **客戶逐字裁示（①）**（來源：使用者對話訊息，2026-11-08；來源類別 D；原樣引用，不得改字）：
  > 我正式核准 C4 採最近三個完整且到公告時點的日曆月份、可信月份鍵、保留缺值位置；不連續不得判逐月加速，可依既有部分達標規則評分但不得虛構證據。請重新查 GitHub 並提供完整 Claude Code 分批施工提示語，包含資料契約、負測、非作者 QA 與 CI Gate。
- **決策者**：使用者（客戶）｜**日期**：2026-11-08｜**來源**：使用者對話訊息（D）｜**狀態**：~~進 main 前屬本 docs PR 待合併內容，不得宣稱已生效於 main；施工分批進行（Batch A→B→C），**本條僅 docs，尚未施工**。~~（2026-11-08 已更新：Batch A 已 squash 合併 #1075〔`228e976`〕、Batch B 已 squash 合併 #1076〔`556b335`〕，兩者最新 head 原生 CI 全綠、各有非作者 QA；Batch C 整合驗證進行中，見 DEC-152；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；DEC-152）本裁示是客戶對 DEC-150 Batch B1（C4 缺月）調查結論所列「C4 資料契約 (a)~(d)」的**方向核准**（DEC-148、DEC-149、DEC-150 後的客戶第四個直接裁示）。
- **(1) 已核准行為**（來源②：客戶同日交辦訊息§1『已核准』清單，原文轉述於交辦訊息，**非單句逐字裁示**，亦非 AI 自創；授權僅限所列方向。其中第 5～7 點的措辭——『可依既有部分達標規則評分』『沒有充分證據時必須標示資料不足／無法判定，不能用 0 假裝已評分』『不得自行創造月份、公告日期、營收、基期或 YoY』——出自該清單）：
  1. C4 使用**最近三個完整且已達可信公告時點的日曆月份**。
  2. 使用**可信月份鍵**，**不從列表位置推測月份**。
  3. 缺月份或缺 YoY 時，**保留對應月份位置與缺值原因**（固定三個位置，不壓縮）。
  4. 月份不連續、不可驗證，或連續性證據不足 → **不得發『逐月加速』正式訊號**。
  5. 有可信部分月份證據時，**可沿用既有『部分達標』規則**評分，但須符合該規則**原有條件**。
  6. 沒有充分證據時標**資料不足／無法判定**，**不能用 0 假裝已評分**。
  7. **不得自行創造**月份、公告日期、營收、基期或 YoY。
- **(2) 五項分開判定**（來源②；五項**不得濃縮成單一布林**；每一項各自有值與缺值原因）：
  1. 目標月份連續性；
  2. 各月是否有真實觀測；
  3. 去年同月基期是否有效；
  4. YoY 是否可合法計算；
  5. 是否到可信公告時點。
- **(3) 時間語意不得混淆**（來源②）：來源觀測日、公告時點、抓取時間、計算時間為**四種不同的時間**；**不得用 `fetched_at` 當公告日**，**不得用目前日期推斷某月已發布**。公告日期證據無法驗證 → 標**『日期資格 NOT VERIFIED』**，並**阻擋依賴它的強連續訊號**（即不得發『逐月加速』正式訊號）；需新增**公告時點資料來源**或**全新口徑** → **停手，進 Decision Gate**。
- **(4) 未授權**（來源②；維持需另行裁示）：新計分權重；新數值閾值；改 C1～C3；固定強缺貨封頂；新缺貨獨立性公式；Risk Cap；正式 OneBrain runtime；新來源／API；新 UI Layout；修改正式排程或繞過資料發布 Gate；改動 PIT 或覆寫歷史紀錄。**『方向核准』不得被解讀為已核准任何新數值規則或新來源。**
- **施工分批**（批次名稱與順序 A→B→C、每批獨立 PR＋非作者 QA＋最新 head 原生 CI 屬來源②；**各批內容細節、預設推薦方案 B、負測清單屬來源③AI 整理，待客戶確認**；沿用 DEC-147 流程：squash merge＋文件同步；**未授權事項須停手**）：
  1. **Batch A｜月份契約**（producer additive 欄位；**預設推薦方案 B**：月營收計算層傳遞可信月份與缺值證據，C4 驗證）：固定三個月份位置、可信月份鍵、缺值原因、五項分開判定；舊輸入無月份鍵須有明確預設（不得默默當連續）；範圍含 additive 欄位對下游（L3 與 CLI、forward_test 凍結 schema）的相容查核。
  2. **Batch B｜C4 評分修復**：不連續／不可驗證／證據不足不發『逐月加速』；有可信部分月份證據時依既有『部分達標』規則評分；無充分證據標資料不足；不新增分數值、不改 C1～C3。
  3. **Batch C｜整合驗收**：端到端負測與對照（含 `[20,30,40]`／`[20,None,40]`／`[20,30,None]`／`[None,30,40]`／缺整列月份的行為差異與前後證據留 PR）、非作者 QA、CI Gate。
- **與既有決策的關係（引用，不改寫）**：
  - **DEC-148**：D1／D3 資料語意不變；本裁示不擴充到 DEC-148 之外的資料契約，**不以 `fetched_at`／`cached_at` 冒充資料日**的原則一致。
  - **DEC-149**：65%／35% 不重配、缺貨『至少兩項有效獨立證據』資格方向、四項全缺排除正式排名並保留診斷，均維持有效。
  - **DEC-150**：本條是對其『C4 缺月份不得認定連續加速』方向、及其所列『C4 月份**日期契約**須先提最小資料契約方案（走 Decision Gate）』的**後續裁示**；DEC-150 其餘（Batch A 已合併 #1072、B2／B3、Batch C 畫面揭露）不因本條變更，其仍待項目照舊待裁。
  - **DEC-147**：施工、獨立 QA、PR Merge、Branch 清理與文件同步歸屬、作者≠QA、『仍須停止並請使用者裁示』清單均原樣適用，不放寬。
- **仍待驗證（不是已核准）**：**公告時點證據**——現行 producer 是否有可信的逐月公告日期來源尚未查證；若無，不得自創，依 (3) 標『日期資格 NOT VERIFIED』、阻擋強連續訊號，並走 Decision Gate。『部分達標』規則的原有條件與各情境（例如只有兩個有效月）的適用性須於 Batch B 設計時依既有規則核對，無法由既有規則判定者停手。
- **證據限制**：本條為客戶裁示的入庫紀錄；來源分三類（見開頭『來源標示』）：逐字僅上方引文（①）；『已核准行為』『五項分開判定』『時間語意』『未授權』為客戶同日交辦文字（②，非單句逐字裁示）；預設推薦方案 B、Batch 細節與負測清單、(d) 歸類為 AI 整理（③，待客戶確認）。B1 調查結論為單組讀碼＋合成實測，未經第二組獨立驗證。**實作狀態**：~~本條僅 docs，Batch A～C 均尚未施工~~（2026-11-08 已更新：Batch A 已 squash 合併 #1075〔`228e976`〕、Batch B 已 squash 合併 #1076〔`556b335`〕，兩者最新 head 原生 CI 全綠、各有非作者 QA；Batch C 整合驗證進行中，見 DEC-152；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；DEC-152）；發布端到端與 Cloud 部署仍 NOT VERIFIED。


### DEC-152｜#1076 選 B 授權合併、半邊批次失敗維持現況、全市場 STRONG 歸零僅為 fail-closed 過渡；FinMind 月份欄位驗證列下一批（客戶 2026-11-08）

- **來源標示（三類，勿混）**：**①客戶逐字**＝下方引文區塊；**②客戶同日交辦文字**＝引文之後交辦訊息中的逐項要求（驗證順序、未授權事項、文件同步與 Batch C 指示；轉述自同一則交辦，非單句逐字裁示）；**③AI 整理**＝#1076 影響面數字、FinMind 證據之 NOT VERIFIED 判定、C4-D／C4-D-real 的命名與切分。
- **客戶逐字裁示（①）**（來源：使用者對話訊息，2026-11-08；原樣引用，不得改字）：
  > 1. 選 B。#1076 可於最新 head 原生 CI、非作者 QA、Review Gate 全部通過後依既有授權合併。
  > 2. 半邊批次失敗維持現況，不另開市場隔離施工。
  > 3. 全市場 STRONG 暫時歸零只接受作為 fail-closed 的過渡狀態，不得視為長期正確排名結果。
  > ChatGPT 已額外查閱 FinMind 官方文件，TaiwanStockMonthRevenue 已提供 revenue_year／revenue_month；官方範例顯示 date 與營收所屬月份可能不同。因此：
  > - 下一小批優先驗證既有 API 欄位，不要直接信任 date。
  > - 在具有合法 token 的環境取少量真實樣本，確認欄位語意、日期完整性及公告時點資格。
  > - 優先以原有 revenue_year／revenue_month 傳遞可信月份鍵。
  > - 先做最小 schema 擴充與回溯相容，不能憑空補月份。
  > - 真實資料驗證前，不得宣稱全市場 STRONG 已恢復。
  > - 不新增權重、門檻、封頂分數或新的排名例外。
  > - 保留全市場與單股的差異測試、缺月負測、FAIL_CLOSED 及非作者 QA 證據。
  > 請在 #1076 合併後將本次裁示、FinMind 官方欄位證據、未驗證限制和下一批待辦寫入 DECISIONS／BACKLOG／HANDOFF／PROJECT_STATE。
  > 之後依原規劃執行 Batch C 整合驗證。工程與文件工作可安全分批，但不得跳過最新 GitHub Gate；最多三項安全工作同時進行。
- **決策者**：使用者（客戶）｜**日期**：2026-11-08｜**來源**：使用者對話訊息（D）｜**狀態**：本條為入庫紀錄；DEC-151 之後的客戶第五個直接裁示。
- **GitHub 事實（③，以撰寫當下為準，下次接手須重查）**：main＝`556b335`；#1075（C4 Batch A 月份契約，squash `228e976`）、#1076（C4 Batch B 評分修復，squash `556b335`）已合併；#1038（Draft，PIT，NO MERGE）、#1034（Draft）仍開。
- **FinMind 官方欄位證據（③，NOT VERIFIED）**：來源＝客戶轉述「ChatGPT 查閱 FinMind 官方文件」（`TaiwanStockMonthRevenue` 提供 `revenue_year`／`revenue_month`；官方範例顯示 `date` 與營收所屬月份可能不同）。**本 repo 沙箱無法連 FinMind、本 session 未獨立核實**。現有碼（`data_loader.py`、`monthly_revenue_fetcher.py`）在缺 `date` 時以 `revenue_year-revenue_month-01` 合成 date，與「date 可能不同於營收所屬月」並不矛盾，但也不證實該描述。欄位語意、日期完整性、公告時點資格均**未驗證**；公告日不得虛構。
- **#1076 實際交付與影響面（③；合成 3000 檔、seed 20261108，不代表真實比例）**：全市場路徑 STRONG 963→0、C4 變動 1023 檔、tier 變動 347 檔、前 50 名換 10 檔；單股路徑 C4 變動 116 檔、前 50 名換 1 檔；舊版對有缺月或不連續的 652 檔中誤給 STEADY／STRONG 者 75 檔。已知 4 組輸入 C4 STEADY→STRONG（目標三月自身完整連續、整表有未到期跳月列），為預期效果。半邊批次失敗標整池 FAIL_CLOSED 為 Batch A 既有行為（裁示 2 維持，不另開市場隔離施工）。非作者 QA 兩輪通過；#1075 與 #1076 最新 head 原生 CI 全綠。
- **效果（③對引文的整理）**：全市場 STRONG 暫為 0 僅是 fail-closed 過渡，**不得**寫成「排名已恢復」或「長期正確」；資料管線尚未傳遞可信月份鍵，真實資料驗證前不得宣稱恢復。
- **下一批（③命名，詳 BACKLOG）**：**C4-D**（plumbing：以既有 `revenue_year`／`revenue_month` 傳遞可信月份鍵，全市場批次路徑最小 schema 擴充、回溯相容）；**C4-D-real**（blocked：需合法 token 環境取少量真實樣本）；**Batch C 整合驗證**（進行中）。
- **未授權（不得擅自）**：新權重／門檻／封頂分數、改 C1～C3、新獨立性公式、Risk Cap、OneBrain runtime、新來源／API、UI 版面、改排程、PIT 改動、虛構公告日。沿用 DEC-147 流程（作者≠QA、最新 head 原生 CI、squash merge＋文件同步）；最多三項安全工作同時進行。
- **證據限制**：引文區塊為唯一逐字；FinMind 欄位證據為客戶轉述之二手資訊，未經本 repo 驗證；#1076 數字為合成資料實測，非真實市場；發布端到端與 Cloud 部署仍 NOT VERIFIED。


### DEC-153｜FinMind 真實取樣安全 Gate、缺貨資格與分數分離研究、未驗證年月鍵 C4 上限（客戶 2026-11-08）

- **來源／決策者**：客戶直接訊息（2026-11-08；D）；此段為文件 PR 草稿，**合併 main 前不得宣稱正式生效**。
- **客戶逐字裁示（原樣引用）**：
  > 我核准台股 AI 戰情室下一階段方向：1. FinMind 真實取樣選 B；2. 缺貨缺值處理選 B；3. 未驗證年月鍵 C4 評分資格選 B。請先重新做 GitHub Verification Gate，將本次裁示與研究／施工邊界寫入正式 DECISIONS、BACKLOG、HANDOFF，並提供 Claude Code 完整分批施工提示語（含三方案比較、非作者 QA、最新 head CI、Risk Cap／PIT 停手條件）。未核准的新來源、權重、門檻或重大排名公式不得擅改。
- **選項的現場定義（非客戶逐字，源自此前提供的選單）**：
  1. FinMind **B**：**優先檢查既有 Secrets**；沒有合法且可安全使用的憑證時停在真實資料驗證 Gate，不在對話／PR／log 中索取或洩漏 token，不自動開新 API／付費方案。此核准**不代表**合法 token 已存在、亦不代表准許 production 寫入。
  2. 缺貨缺值 **B**：**分離資料資格與原始分數，先量化正式排名／徽章／推播／forward_test 影響，再分批修復**。資料不足、來源失敗、未評估、合法真 0 必須區分；**不核准**重配權重、任意重排正式榜單、修改 `SCREENER_MIN_FACTOR_COVERAGE_RATIO`、新增中性分數／門檻、固定強缺貨封頂或繞過 Risk Cap。若既有正式規則不足以確定下游改動的正確行為，需提出量化證據和 Decision Gate，先不寫正式排名。
  3. 未驗證年月鍵 C4 **B**：**最高只能 PARTIAL（既有 5 分）且必須符合既有 PARTIAL 條件**；不能因 `date≠ym`、未驗證 `source_month_key_verified` 或舊 caller 就取得 STEADY（12 分）／STRONG（20 分）；有 2 個合法有效月份且符合原有部分達標條件才可得既有 PARTIAL，否則依既有資格分流為無法評估／合法動能不足；缺值不可充當真 0。不得把此上限擴張為所有缺少其他證據時的一律 5 分。日期及公告時點不可信時仍依原 fail-closed Gate，不可繞過。
- **研究／工程分批**：A：純資料契約／資格與下游呼叫鏈研究、三方案比較與真實來源安全預檢；B：在現有授權內修 C4 未驗證年月鍵不得 STEADY/STRONG，補含 `date≠ym`、完整與不完整、legacy、部分達標、PIT、真 0 的負測；C：綜合排序缺值資格與分數分離先產出影響矩陣／fixture，合法且可證實的純診斷與資格傳遞可提小 PR，正式排序／百分位／分母／通知或 forward_test 行為需先檢查既有授權，無明確規格進 Gate。
- **三案比較要求**：A 只補診斷不改排名；B 資格／分數分離並研究候選分流（優先）；C 重建計分與加權（未授權）。列正確性、PIT、排名差異、風險、速度、Token、回退路徑。客戶選 B 是方向，不是對新數值規則的授權。
- **驗收／禁令**：GitHub Gate（main SHA、Open/Draft、head/diff、CI／QA、branches）→ 每批獨立 PR → 作者≠QA、負測與必要整合測試 → **最新 head 原生 CI** success → review threads／branch protection → squash merge → BACKLOG／HANDOFF 同步。禁止改 Risk Cap、PIT／凍結歷史帳本、正式 Layout、OneBrain runtime、未核准來源、權重、門檻、強缺貨固定封頂，禁止覆寫或自行合併 #1038；#1034 舊治理 Draft 須核銷。三條歷史保留分支不刪。
- **事實與限制（ChatGPT 2026-11-08 GitHub 查核）**：main `c5846b770bdc176954edad486f92fe93e61e73c7`（#1077 已合併）、Open #1034／#1038；#1077 head `a708b001c27b1ffb077bdd445c5bfce52b63b42e` 原生 run 42474547644 success。 `fundamental_screener_service.py` 的 `shortage_map` 目前只傳缺貨分數，下游缺值誤判已有可重現程式線索但**真實市場影響 NOT VERIFIED**；FinMind 真實欄位與公告時點仍 NOT VERIFIED。
- **③AI整理：執行結果（2026-11-08；非客戶裁示、非客戶逐字；決策者 AI 總管（事實更新）；GitHub 為準：main `35c08d2`，#1075～#1078 已 merge，#1038 Draft NO MERGE，#1034 Draft 待核銷）**：
  - **Batch A（FinMind 預檢，唯讀）**：C4-D-real **BLOCKED**——沙箱無 FinMind token、repo 無 secrets.toml／.env、無任何真實或錄製的月營收樣本；`date` 與 `revenue_year/month` 語意目前只有程式假設與客戶轉述（ChatGPT 查閱官方文件），**NOT VERIFIED**。`FINMIND_TOKEN` 僅以 GitHub Actions `secrets.FINMIND_TOKEN` 存在於 14 支 workflow，皆會寫入／推播／推分支，不適合當取樣載體。`BATCH_SOURCE_MONTH_KEY_VERIFIED` 維持 False，全市場 STRONG 維持 0。合法取樣選項（只列、未執行、需客戶授權）見 BACKLOG `NUI2-DEC153`。
  - **Batch B（C4 未驗證月份鍵上限）**：commit `93904d0`＋`964f717`，~~實作完成＋非作者 QA 通過，**待 PR／CI／merge，尚未合併**，不得宣稱已生效於 main。~~（2026-11-08 已更新：Batch B（C4-E）已由 #1079 squash 合併，main `b01db69`，head `d02811d` 最新 head 原生 CI 全綠、非作者 QA 通過；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；#1079）現行：已生效於 main（#1079，`b01db69`）；詮釋點仍待客戶確認。**待客戶確認的詮釋點**（AI 不自行裁決）：未驗證且有效值全部＞門檻時給 5 分（現行實作）vs 嚴格讀為僅符合既有 PARTIAL 條件（則為 0 分）；詳見 BACKLOG。
  - **Batch C（缺貨缺值與綜合排序研究，唯讀、單組結論未經第二組驗證、合成資料不代表真實市場）**：仍成立的問題只剩 n_ok=1～3 部分缺值入百分位／composite；推薦方案 A 先行、B 的資格規則進 Decision Gate；**不建議任何數值門檻**。無新客戶裁示、未新增 DEC；未授權事項依本條不變。


### DEC-154｜C4 保留合法 5 分上限、FinMind 一次性安全取樣、缺貨 G1 診斷先行、候選視窗優先研究（客戶 2026-11-08）

- **來源／決策者**：使用者於 ChatGPT 對四項建議回覆「同意」（客戶逐字僅此二字）。下列四項為緊接的 ChatGPT 具體提案之核准內容，**不是**使用者逐字逐項列出。此項 docs PR 合併前僅為待驗草案，需原生 CI／非作者 QA／Review Gate。
- **核准 1｜C4**：維持 DEC-153 下**未驗證月份鍵最高 5 分**之上限。有效且真實可用的月營收 YoY 與缺乏月份驗證不是同一狀態；上限不能成為任何 missing／抓取失敗／無效月份的保底分。針對此前明確提問「未驗證但有效值皆高於既有門檻，給 5 或 0」：**保留 #1079 現行 5 分行為**，前提是來源合法、數值確實可計且原有 `PARTIAL` 分流的有效資料條件滿足；若數值有效性／可觀測性不足，仍依既有 fail-closed 與未達標規則，不得憑空給 5 分。**不授權**新增權重／門檻或開啟未驗證 STRONG／STEADY。
- **核准 2｜FinMind**：選 **B：新增一次性、手動觸發、唯讀的 `workflow_dispatch` 安全探針**作小量真實月營收欄位及月份語意驗證，不改既有正式排程。先查現有 Secrets 的**可用性與授權範圍**，不能讀出／印出 token；若無合法可用憑證，保持 `C4-D-real=BLOCKED`，需另提授權。探針先獨立 PR 經 QA／CI／安全檢視，再於允許的環境手動執行；輸出只限必要的非敏感欄位與來源、資料日、公告時點證據、查詢時間及驗證限制；不得意外外傳 token、碰 production 寫入、發布、推播、資料 PR。**探針成功不等於自動准許將 `BATCH_SOURCE_MONTH_KEY_VERIFIED` 翻成 True**：需證明欄位語意、公告時點及 PIT，另走明確驗收／決策 Gate。
- **核准 3｜缺貨缺值**：先 **G1：不變更正式排名、因子權重、百分位分母或准入門檻**，在既有下游適當地方補足可追溯的「部分有效證據 n/4、缺值／未評估／來源失敗／合法低分」診斷與文案，保留原始分數和資格分離的方向。必須確保觀測值 0 ≠ 缺值；介面與推播不得把證據不足簡化成已證實「缺貨弱」。**G2／G3 均不啟用**，僅作後續研究候選；G2 依有效項目數直接排除的規則**未獲授權**，且需評估「不同經濟機制」獨立性與避免漏掉早期成長股。新 enum、正式資料結構／凍結版型、正式推播動作或排名變動需另立 Gate。
- **核准 4｜候選視窗與版本**：優先對 `_candidate_pool` 的末三列趨勢 vs C4 最近三個目標日曆月份做**唯讀、可重現研究與影響量化**，不自動改候選准入。 `SHORTAGE_VERSION` 暫做設計及版本／凍結資料回溯研究，**不直接修改既有 forward_test 凍結 cohort 或歷史紀錄**；仍須獨立 Schema／PIT Gate。
- **三方案比較（AI 整理）**：A 僅診斷／文案，成本最低且正式排名不變但保留既有排名偏差；B 資格與分數分離並驗證正式／研究候選分流（未來方向，需資格規則 Decision Gate）；C 重建權重和排名公式，影響及回測風險最大，未獲授權。採 **G1=A 為立即安全工作，B 保留後續候選**；針對 FinMind 比較 A 客戶自取、B 一次性新探針、C 改既有探針，選 B 以避免人工作業及正式排程耦合。
- **施工與驗收**：先 GitHub Verification Gate（main SHA、Open/Draft PR/diff/head、CI/QA、branches）；最多三件安全工作／批；Phase 0 文件裁示→ Phase 1 FinMind 探針設計、最小安全施工 PR（Secrets 不可見／僅手動唯讀、不可自動執行）→ Phase 2 G1 additive 診斷與負測／下游顯示（不得改正式排名）→ Phase 3 候選視窗差異研究與 SHORTAGE_VERSION 設計。每個工程批獨立 PR、作者≠QA、最新 head 原生 CI 與 Review Gate 全過才合併，文件進度同步 GitHub。
- **不變停手條件**：新增數值權重／門檻／固定封頂、正式 ranking／percentile／coverage／Research enum、Risk Cap、OneBrain runtime、現有正式 UI2 Layout／權限、正式資料來源／API 承諾、真實歷史帳本、PIT、凍結資料 schema、付費／外部不可逆寫入皆需先 Gate；#1038 PIT Draft **NO MERGE**、#1034 舊治理 Draft 待核銷；保留分支不刪。
- **GitHub 時點證據（AI 查核，非客戶逐字）**：main `72bc5caf542cf5333c8b8153b9c5d649c634da86`（#1081 docs-only 已合併）；Open #1034／#1038。 #1081 最新 head `fd053f89c35292fbc2ae795d7529201573992d44` 原生 CI Run 42483556378 success。 C4-D-real 真實 FinMind 資料仍 NOT VERIFIED，全市場 STRONG 仍為 0 的過渡 fail-closed 不可宣稱恢復。

- **③AI整理：執行結果（2026-11-08；非客戶裁示、非客戶逐字；決策者 AI 總管（事實更新）；GitHub 為準 main `476529d`）**：
  - **已合併**：#1082（DEC-154 文件，squash `412d15b`，head `501cafa` CI 全綠、非作者 QA 通過）；#1083（G1 缺貨資料資格顯示，squash `b6a20b6`，head `691eaa3` 原生 CI 全綠、非作者 QA 通過；首輪 head `b2b28bb` 因 d3e characterization 測試未納入兩個新顯示鍵而紅，已修且斷言未放寬）；#1084（FinMind 唯讀探針，squash `476529d`，head `eb2e20a` 原生 CI 全綠；非作者 QA＋安全審查兩輪通過）。#1038 NO MERGE、#1034 待核銷、歷史分支保留。
  - **G1**：n_ok＜4 且 tier＝不明顯不再寫確定「缺貨弱」，改顯示「缺貨：部分證據 n/4」；n_ok＝0 無徽章、資料資格「無法評估 0/4」；n_ok＝4 低分維持「缺貨弱」；新增顯示鍵「資料資格」「_evidence_status」；推播多一句「缺貨：無評估資料」（勾缺貨但無缺貨列時，僅文案）。排名／百分位／composite／權重逐位元不變（非作者 QA 獨立 parity）；forward_test 凍結不帶新欄。**仍待 Decision Gate**：G2／G3、n_ok＝1～3 低分是否仍進正式百分位、`get_ranked_picks` 輸出追溯欄、`N_SIGNALS_TOTAL=4` 局部常數日後移 SSOT。
  - **FinMind 探針**：`.github/workflows/probe_finmind_monthrev.yml`＋`scripts/probe_finmind_monthrev.py`＋測試；僅 workflow_dispatch、`contents: read`、secret 僅一處、無寫入／artifact／推播、不印 API msg 內文。**合併不等於執行**：Claude Code 嘗試 `run_workflow` 得 403「Resource not accessible by integration」，無權限由此整合觸發，**探針尚未執行**；secret 是否存在、方案能否取 `TaiwanStockMonthRevenue` 仍 **NOT VERIFIED**。需客戶／repo 擁有者在 GitHub Actions 頁手動 Run workflow（預設輸入即可），或另授權其他合法途徑；跑完只讀日誌，**不得據此翻 `BATCH_SOURCE_MONTH_KEY_VERIFIED`**；status≠200 即 NOT VERIFIED。探針測試守衛為正則比對，非作者 QA 實證約有 6 類可繞過變體（例如 `shell: bash {0}; curl`、flow-style 步驟、checkout 加 `ref:`），需先編輯 workflow 才可能發生，屬防誤改的防呆層，不宣稱無法繞過；建議日後改 yaml 結構白名單（須先確認 requirements 有 yaml）。
  - **C4**：依 DEC-154 保留 5 分（含全高值；missing 不保底），先前「5 分 vs 0 分」詮釋點已解。**全市場 STRONG 恢復條件＝真實樣本驗證＋客戶裁示**，不得宣稱已恢復。
  - **候選視窗研究（唯讀、單組、合成資料）**：`classify_trend` 末三列只用於批次路徑（`_candidate_pool`，需 sponsor tier），存活池路徑不經它；與 C4 目標月不一致案例：缺月（誤選）、最新月已到期未入表（過時證據入池）、未到期月已入表（漏選＋前視）、date 全為抓取日但 year／month 正確（被篩掉）、重複／亂序（FAIL_CLOSED 股仍佔深掃名額）。合成 N=6000：舊池 1129 vs 目標月池 833，舊入目標出 330（5.5%）、舊出目標入 34（0.6%）（缺陷機率為假設，僅方向性）。方案：研究 1 推薦先 A（meta 診斷差異數，不改池）；改池視窗為目標月屬 Decision Gate（池 −26% 合成、改排名、歷史 cohort 不可比）。
  - **SHORTAGE_VERSION 設計（只設計，未施工）**：現行 `shortage_screen_v1`（`shared/shortage_screen_thresholds.py:114`）全 repo 無 production 讀者，僅 meta 寫入；forward_test 凍結列僅 6 欄（cohort／stock_id／name／entry_price／factors／frozen_at）不含版本；`picks.parquet` 實測 100 列、5 個 cohort 全早於 2026-11-08 評分修復。建議：升版觸發＝評分／C4 契約語意／准入或排序規則變更；舊資料缺版本欄讀端視為 unknown／legacy、不回填；位置選項 (1) 僅 meta (2) parquet 加性欄 (3) 側檔 `freeze_meta`；Sheet 讀端表頭 A–F 精確等於 `_FT_HEADERS`、寫端不得改既有表頭，Sheet 不能攜帶版本欄；偏好 meta＋側檔（加性、不動 picks schema）；是否升版／採哪個位置為 Decision Gate。
  - **待客戶事項**：(1) 探針手動執行（Actions 頁）或其他取樣授權；(2) G2／G3 與 n_ok＝1～3 是否進正式百分位；(3) 候選池視窗改為目標月？(4) `SHORTAGE_VERSION` 位置與升版；(5) C4 全市場 STRONG 恢復條件（真實樣本驗證＋客戶裁示）。

### DEC-155｜#1088 自動資料 PR 合併紀錄與一次性窄範圍治理裁示（2026-11-09；ChatGPT 獨立裁示，非客戶逐字裁示）

- **來源／決策者**：ChatGPT 獨立裁示（評論 https://github.com/linchen-20200325/my-stock-dashboard/pull/1088#issuecomment-6735942091）。**不是客戶逐字裁示**；一次性、範圍窄。本條只追加登記，不改寫既有條文。
- **事實**：PR #1088（自動資料 PR「macro-history 2026-11-08」，head `7fc23df73a8fbf0806630a3a641caab07bf2ba4b`）於 2026-11-09T08:49:58Z squash 合併 → main `da97d193`（完整 SHA `da97d193cbbf30e187dc60b2d724e146622fa88d`）。原生 CI run 42580786108 五項檢查 success。非作者資料 QA 以 pyarrow 完整解碼 parquet：main 與 PR 皆 4912 列 x 8 欄、schema 相同、新增／移除列 0，僅 1 格不同——2026-11-06 該列 `fetched_at` 由 `2026-11-07T15:33:58.585925+00:00` 改為 `2026-11-08T15:53:08.299701+00:00`；OHLCV／source／日期／34 筆 volume NaN 未變。QA 評論：https://github.com/linchen-20200325/my-stock-dashboard/pull/1088#issuecomment-6735771473
- **metadata.json**：`finmind_inst`／`finmind_margin`／`finmind_m1m2` 新增 `fetch_outcome=NO_NEW_DATA`（含 evidence 字串）；`tw_pmi` 新增 `fetch_outcome=UNDETERMINED`；`last_updated`／`row_count` 未變。`tw_pmi.json` 僅 `fetched_at`／`cached_at` 變動（proxy 值 62.5、date 2026-10-01、`is_proxy=true` 未變）。
- **裁示（選項 A，僅此一次）**：允許本次合併。`fetched_at` 為「最新抓取時間」（揮發欄位，見 `scripts/publish_data_pr.py` 的 `VOLATILE_PARQUET_COLS={fetched_at,captured_at}`），不可用來推論 2026-11-06 該列的 PIT 可得時間；舊值僅保存於上述 QA 評論。
- **不授權**：覆寫 OHLCV／歷史／帳本／觀測日期／schema／投資公式／Risk Cap，亦不擴大寫入豁免；**不是**放寬全域「不可變帳本」原則。`NO_NEW_DATA` ≠ fresh；`UNDETERMINED` ≠ success；proxy PMI 62.5 不得成為正式訊號。
- **後果（未驗證）**：main metadata 現帶 `fetch_outcome`（finmind_inst／margin／m1m2／tw_pmi）；`calibrate_health_weights` 的 `check_inputs_fresh`（見既有 BACKLOG／HANDOFF 關於 UNDETERMINED 阻擋的營運註記）可能仍因 `tw_pmi` 為 UNDETERMINED 而阻擋；**NOT VERIFIED**。
- **其他**：#1038 已 closed 未合併（PIT FAIL 證據保留）；main `da97d19` 時 Open PR 數 0；發布端到端除本 PR 檔案層事實外仍 NOT VERIFIED。

### DEC-156｜New UI2 台股加權指數日 K A／B／A 客戶裁示（2026-11-09；客戶明確裁示）

- **來源／效力**：客戶於本對話明確表示「同意你推薦的 A／B／A：K棒開收紅綠灰、手機近期20根圖高約220px、Yahoo OHLC唯讀接線方案。先同步 GitHub 決策與規格，正式施工仍需另行核准。」——此為**客戶於對話中的口頭裁示（轉述），repo 內無原始連結／NOT VERIFIED by repo（來源：對話引述）**，此處僅作為已記錄的客戶裁示。本項是**已核准的產品／資料接線方向和 docs-only 同步授權**；**不是**正式程式碼／生產接線授權。
- **A — K 色**：日 K 以**當日開盤 vs 當日收盤**決定顏色：`close>open` 紅、`close<open` 綠、`close==open` 灰十字線（開收同價）。不以「相對前收」決定 K 棒色；與前收相比的日漲跌幅應另取合法前收資料及其獨立語意，不能混稱。
- **B — Mobile**：390px 手機版**預設顯示最近 20 根已驗證的完整日 K**，圖高**約 220px，屬視覺設計目標，非強行豁免首屏版型／可用高度／無水平溢出規則**；資料可有最多 252 個交易日的候選讀取窗口供後續切換，期間切換／縮放／捲動互動尚未核准具體實作，不得自行加假按鈕；桌機採相同 K 語意，須驗 1440×900。資料不足 20 根不得補 0、補假棒；不足／過期／錯誤各依契約清楚降級。
- **A — 來源／唯讀**：優先重用**現有 Yahoo `^TWII` 日 OHLC `data_cache/twii_ohlcv.parquet`**，以具來源、日期、`is_stale`、`upstream_state`、`as_of` 的合法、最小化加性唯讀 L3/UI2 契約接線；**FinMind `TaiwanStockPrice` 是舊 UI 個股 K 備援，不是已接大盤**，TAIEX 分 K 與官方替代來源只列研究／對帳／備援候選。**不核准新付費、live API、cron、publisher 或第二個 writer**。
- **現狀與覆蓋範圍**：#1096「P1 收盤折線／252 根」僅是**舊研究候選**，#1097 合併的是 HTML FAKE 視覺稿及 FinMind 差異研究；**本決策覆蓋上述候選的圖型／色彩／手機預設顯示數，舊文件保留歷史、不再當待核准設計**。#1097 的 Gate 文件曾以 `close>=open` 寫紅字樣，視為舊候選：現以嚴格 `>`、`<`、`==` 決定；不可改寫歷史文件來假裝原始就一致。**有意識的政策變更，不是漏刪；決策者見上（客戶口頭裁示，轉述）；原文件（#1096 P1 折線／252 根預設、#1097 `close>=open`）保留為歷史。**
- **施工前 Gate（仍阻擋）**：現行 `market_twii_view_service.get_twii_trend_view` 只有 close＋freshness；`macro_v2_service.get_twii_ohlc` 有 OHLC 但缺 freshness，且 G2F 未許可直接接進 UI2。資料契約必須驗證 OHLC 邏輯、有限正值、日期升序唯一／無未來日／未完成棒、stale/failed 區分、卡片與圖同源 as_of、legacy 資料有疑義時誠實降級；不得放鬆 G2F/G2/G4/G9、不得將 missing 當 0、中性或正常。實際擴充方法、schema／tests、視覺真機截圖須另行施工核准及獨立 QA／latest-head CI。
- **文件規格 SSOT（決策附屬）**：`docs/vnext/NEWUI2_MARKET_TWII_KBAR_ABA_DECISION_SPEC_2026-11-09.md`。工作現況另同步 BACKLOG／HANDOFF；本次 PR **docs-only**，不得觸及 src、tests、CI／workflow、Risk Cap、OneBrain、登入／Sheet、股票選股公式。

- **實作註記（2026-11-09 追加；AI 總管派工實作紀錄，非新客戶裁示）**：正式施工依 GitHub Issue #1099 的核准範圍進行——客戶施工授權為**對話轉述，repo 內無原始連結（NOT VERIFIED by repo）**。PR-1 #1100（main `e5a429c`）落地 L0／L1／L3 日 K OHLC 唯讀 fail-closed 契約；PR-2（分支 `feat/ui2-twii-kbar-market-20261109`，merge pending QA/CI）落地 Real-data Preview 📊 主圖日 K（feed 第二次讀同一白名單函式、canonical 重驗＋卡片同源對帳、FAKE 軸不給 K 棒）。本註記不改寫上方任何條文。
- **合併補註（2026-11-09 追加；非新客戶裁示）**：PR-2 #1101 已 squash 合併 → main `31acbe8`（完整 `31acbe878be2d3a055307d1e090d65c13f6f6fc0`；CI run 42677530800 全 success；非作者 QA PASS https://github.com/linchen-20200325/my-stock-dashboard/pull/1101#issuecomment-6749470261）；上一則實作註記「merge pending QA/CI」狀態已過時，原文保留不改。

- **治理裁示紀錄（2026-11-10 追加；僅紀錄 owner 於 #1105 留言所給裁示，非 AI 新決策）**：PR #1105（macro-forward-test，2026-11-06 列）已於 2026-11-09T23:41Z 關閉未合併；owner／ChatGPT 治理裁示見 https://github.com/linchen-20200325/my-stock-dashboard/pull/1105#issuecomment-6754457744 ——PIT 不接受、未授權改寫歷史或 PIT 豁免、日後補列須另設 PIT 契約設計＋來源證據 Gate。本註記不改寫上方任何條文。

### DEC-157｜New UI2 📊 市場頁順序改為 日 K 主圖／Primary → 核心指標卡 → OneBrain Outlook（方向 B；Issue #1108；2026-11-10）

- **來源／效力（據實，不誇大）**：客戶於 2026-11-10 提供 Streamlit Cloud 實際手機截圖並回饋「這圖放在 OneBrain 這邊滿奇怪的」，之後回覆「繼續」；協作 ChatGPT 依前一輪推薦以**方案 B 作為優先修正方向**，記錄於 GitHub Issue #1108。**repo 內沒有客戶逐字點選 B 的裁示**——本條**不得**描述為「客戶逐字選了 B」，只能寫「客戶截圖回饋＋『繼續』，ChatGPT 轉達 B 為優先方向（Issue #1108）」。原始對話為轉述，**NOT VERIFIED by repo**。
- **有意識的政策變更，不是漏刪（決策者：AI 總管依 Issue #1108 授權範圍執行；來源見上）**：DEC-133 G-3＝A（客戶 2026-11-04 (19)，fence 逐字）寫明的已核准順序為「今日主要風險 → OneBrain Outlook → 台股 Primary 空槽 → 核心指標卡」。**本條只取代其中『OneBrain 的位置』**，DEC-133 其餘（G-1＝A 空槽依內容高度、G-2＝B SPEC 省略頻率、「最新收盤參考」誠實性、導覽餘裕 ≥160px、首屏四必要項不變、P2 僅兩項施工範圍之外不做項）**全部維持**；DEC-133 原文（含 sha256 釘住的 fence）與 DEC-156、Wireframes、Active Contract 等舊文件**一字未改**，保留為歷史。
- **舊順序 vs 新順序**：
  - 舊（DEC-133 G-3；至 main `1f3c489`）：頁首 → 〔今日結論／狀態／Risk Cap／是否需要行動／下一步／主 CTA〕＋今日主要風險 → 🤖 OneBrain Outlook → 台股日 K 主圖／誠實空槽 → 核心指標卡 → 其餘區塊。
  - 新（本條）：同一組首屏（內容與位置**不變**）＋今日主要風險 → **台股日 K 主圖／誠實空槽 → 核心指標卡（TWII、VIX、US10Y、DXY、利差、PMI，VM 原狀）→ 🤖 OneBrain Outlook**（無資料＝原樣『未提供』，不捏造推論；缺席＝不畫空框、不重複）→ 其餘區塊。
- **兩邊理由並陳**：
  - **舊順序的理由（仍然成立，不是寫錯）**：AI 解讀（OneBrain）是客戶最想先看到的『所以呢』，放在今日主要風險之後、數據之前，能維持 AI 摘要的顯著度；且那是客戶 2026-11-04 逐字核准的順序。
  - **新順序為何勝出**：台股 K 棒與核心指標卡屬**客觀市場資料**，彼此相鄰才讀得連貫；OneBrain 是**推論／解讀**，緊貼在 K 棒之下（客戶實機截圖回饋『放在 OneBrain 這邊滿奇怪』）會讓使用者把資料與推論混為一談。資料先、解讀後，資訊層分離。此為被權衡掉，不是舊規則寫錯。
- **範圍／不做**：只動 `src/ui2/views/market.py` 渲染順序，以及依賴該順序的測試／viewport 判定器與證據（`tests/ui2_viewport/measure_viewport.py` 的 `p2_onebrain_primary_slot_order` 判定改為 Primary → 指標卡 → OneBrain，並新增突變 teeth）。**不改**：feed（real／FAKE）、K 棒契約與驗證器、20 根、紅綠灰、svg 220px、Risk Cap、OneBrain 模型／推論／VM、投資公式、其它頁、cron／secrets／OAuth／Sheet、G2／G2F／G4／G9 守衛、`render_sections(skip={onebrain})` 去重與 L2／L3 不顯示政策。
- **與其他裁示的關係**：#1107（Cloud 實機驗收）**仍為 PARTIAL**（僅部分看到真實資料日 K，未驗證項仍未驗證），**本條與其施工不關閉 #1107**，也不是 production cutover；Streamlit Cloud 線上實況 **NOT VERIFIED**。
- **證據限制**：新順序的版面量測（390×844、1440×900，FAKE 與 Real-data Preview）由 `tests/ui2_viewport/measure_viewport.py` 於沙箱 Chromium 量得；非 Cloud 線上驗證。

> 📌 **2026-11-10 DEC-157 合併後追記（只追加，非新決策）**：PR #1109 已 squash-merge → main `81db06377b43688df49c9daf5594faea2b5e6b01`（head `30920e90bec746d7db6a4d7e2f302e57e67390e2`；CI run 42760415674 五項 success；非作者 QA PASS）。**釐清**：DEC-157「決策者」欄寫 AI 總管，係指依 Issue #1108 授權範圍執行；**授權來源**為客戶 Cloud 截圖回饋＋「繼續」、ChatGPT 轉達方案 B 為優先方向（repo 無客戶逐字點選 B）。DEC-157 原文未改。

> 📌 **2026-11-10 指標（只追加；非新決策）**：Issue #1110 研究證據見 `docs/vnext/ISSUE1110_DATA_AVAILABILITY_MATRIX_2026-11-10.md`；此為研究紀錄，**不是**新的 DEC，不授權任何施工，亦不改變既有 DEC。

> 📌 **2026-11-10 紀錄（只追加；非 AI 決策、非新的 DEC 編號）｜客戶 D6 授權：舊 UI 診斷頁／側欄資安最小修補（Issue #1113）**：本條**記錄**客戶就 Issue #1110 研究中 D6 所做的授權，內容依 Issue #1113 的轉錄；**repo 內沒有客戶原訊息的連結**，故此處只能引述 Issue #1113 的轉錄文字，不能自稱逐字原文。**授權範圍（摘要）**：僅限舊 API 診斷頁（`src/ui/pages/api_diagnostic.py`）與 `app.py` 側欄 Proxy 顯示的最小資安修補——不得顯示金鑰片段、長度、完整 proxy URL 或敏感回應；**不改 API 資料流、不改其他 UI**。**未授權**：D1（US10Y 口徑）、D2（VIX）、D3（利差）、D4（PMI vs 景氣燈號）、D5（落地 cron）**仍全部未授權**，本條不改變它們；亦不授權任何請求語意變更（含 `verify=False`，另列為可能的獨立 Gate）。實作見 fix/legacy-diagnostic-secret-display-20261110；Cloud 線上實況 **NOT VERIFIED**。

> 📌 **2026-11-10 指標（只追加；非新決策、非新的 DEC 編號）**：上方 D6 授權紀錄所指的實作已由 PR #1114 squash-merge → main `da675689e5010795bc87f5a56d3136ff1747d1cf`（非作者資安 QA 回修後 PASS，同 head 五項 CI success）；殘留資安項與 AI 建議見 `docs/BACKLOG.md`（`SEC-D6-RESIDUAL-*`，皆需客戶授權），D1–D5 仍未授權。


> 📌 **2026-11-10 紀錄（只追加；非 AI 決策、非新的 DEC 編號）｜客戶授權：ETF 經理人週更 workflow 改走資料 PR（Issue #1116 最小修補）**：本條**記錄**客戶就 Issue #1116 所做的授權，內容依 Issue #1116 的轉錄；**repo 內沒有客戶原訊息的連結**，故此處只能引述 Issue 轉錄，不能自稱逐字原文。**事實**（Issue #1116）：`.github/workflows/update_etf_managers.yml`（每週一 20:00 UTC）取數成功後，以裸 `git push` 推 main，run 42743389479 在該步被 branch protection 擋下（GH006）。**授權範圍**：僅限 (1) 該 workflow 的發布步驟改呼叫既有 `scripts/publish_data_pr.py --job etf-managers`（分支 `auto/data-etf-managers`，與 update_macro_history／update_sector_flow 同機制）；(2) `scripts/publish_data_pr.py` 的最小相容登記（僅新增一個路徑鍵 `src/data/etf/etf_managers.json` 的揮發鍵：`updated_at`、`last_seen`、`tenure_days`，不改通用語意）；(3) 測試與本類只追加文件。**未授權**：其他 workflow、`scripts/update_etf_managers.py` 的取數／解析、資料 schema、Secrets、排程時間、branch protection、UI2、OneBrain、Risk Cap；不得直推 main、不得 force-push、不得繞過 required checks；PR 建立／檢查失敗必須讓步驟失敗。實作見 fix/etf-managers-data-pr-20261110。**NOT VERIFIED**：真實 GitHub Actions 發布 PR 的行為（含 GITHUB_TOKEN 建立之 PR 是否觸發 required check、倉庫設定『Allow GitHub Actions to create and approve pull requests』）尚無一次真實執行證據；下次排程為 2026-11-16（週一）20:00 UTC；手動 workflow_dispatch 的結果不得充當 PR required-check 證據。


> 📌 **2026-11-10 指標（只追加；非新決策、非新的 DEC 編號）**：上方 Issue #1116 授權紀錄所指的實作已由 PR #1117 squash-merge → main `aa69d99e8674da17c23e1153aa677551b5837704`（非作者 QA PASS，同 head 五項 CI success）；真實 Actions 發布仍 NOT VERIFIED（下次排程 2026-11-16 20:00 UTC），待辦與限制見 `docs/BACKLOG.md`（`ETF-MGR-DATA-PR-1`／`-NIT-*`／`GH006-OTHER-DIRECT-PUSH-WORKFLOWS`）。


> 📌 **2026-11-10 指標（只追加；非新決策、非新的 DEC 編號）**：Issue #1119（workflow 瘦身唯讀稽核）僅授權**盤點與提出清單**，**不是**刪除或停用任何 workflow 的授權，也不是新的決策；AI 做出的分類（保留核心／排程停用候選／手動研究／資安閘）皆為**提案**，待客戶另行裁示。摘要見 `docs/HANDOFF.md` 2026-11-10 session-end handoff snapshot 與 `docs/BACKLOG.md` `WORKFLOW-SLIM-AUDIT-1`。


> 📌 **2026-11-10 指標（只追加；記錄客戶裁示，非 AI 決策、非新的 DEC 編號）**：客戶於 Issue #1119 留言（https://github.com/linchen-20200325/my-stock-dashboard/issues/1119#issuecomment-6768487486）裁示「Action等儀表板好了 刪死碼時候再一起刪除」：#1119 **HOLD**，待新儀表板完成並開始死碼 Removal Gate 時再與之合併處理並重新驗證；現在不做任何 workflow 刪除／停用／合併。取代上方 2026-11-10 Issue #1119 指標中「盤點與提案」的後續動作；細節見 `docs/HANDOFF.md` 同日更正。


### DEC-158｜Issue #1121 客戶裁示轉錄：Issue #1110 題號 D1～D5 現狀、方案 A 文件、EPS 僅唯讀研究、Digest F／OneBrain G 暫列切換前置、#1119 HOLD（2026-11-10；docs-only）

- **來源／效力（據實，不誇大）**：決策者＝客戶；來源＝GitHub Issue #1121（docs-only 授權）。本條是 AI 總管依 Issue #1121 對「客戶口頭同意 ChatGPT 四項建議」的**轉錄**，**非客戶逐字原文、非 QA PASS**；原始逐字對話不在 repo（**NOT VERIFIED by repo**）。本條是**記錄**，不授權任何施工。
- **⚠️ 編號澄清（避免混淆）**：下文的 **D1～D5 是 Issue #1110 的「題號」**（US10Y 口徑／VIX／利差／台灣 PMI／每日落地 cron），**不是** `DEC-*` 條文編號。本條的 DEC 編號是 **DEC-158**；題號 D1～D5 與 DEC-001 起的任何 DEC 無對應關係。（D6 資安最小修補已由 Issue #1113／PR #1114 處理，不在本條範圍。）
- **六項裁示（轉錄）**：
  1. **D1（US10Y 口徑）**：採官方 FRED `DGS10`，應標示 `source`、`as_of` 與 missing／stale 狀態。**僅核准「資料口徑」**；**不核准**新增 adapter、新增來源、fetcher、排程或正式 UI 接線（實作須另行授權）。
  2. **D2（VIX）、D3（利差）、D4（台灣 PMI）**：維持空槽。D2 先完成「已收盤日」PIT Gate、不接線；D3 定義與來源暫不選定、不新取數；D4 不將 proxy／`UNDETERMINED` 當正式訊號。
  3. **D5（新增每日落地 cron）**：**不核准**，不新增 cron／workflow。
  4. **方案 A 文件**：本批僅 docs-only 文件（CAPMAP 三欄能力對照、C1～C7 切換缺口矩陣、EPS／Digest／OneBrain 研究），不改程式、測試、資料、workflow。
  5. **EPS 預估大盤**：僅准**唯讀研究**；不新增 EPS 來源、公式或 runtime，不得宣稱任何估值或指數預測已可計算。**Digest Stage F／OneBrain Stage G**：沿現有契約**暫列 cutover 前置**，未經新裁示不改（客戶可推翻；已由獨立 QA 對照 Issue #1121 第 4 項原文確認）。
  6. **#1119（workflow 瘦身）維持 HOLD**（見先前客戶留言紀錄）。
- **D1～D5 現狀（截至 2026-11-10）**：UI2 真資料 feed 仍只接 TWII 卡片、TWII 日 K、市場位階三項事實；US10Y 為空槽（口徑已定、實作未授權）；VIX／利差／PMI 為空槽；無新增落地 cron。故 C5（真資料）在現行授權下仍未滿足。
- **仍 NOT VERIFIED（不得因本條轉為 PASS）**：ETF Managers 2026-11-16 20:00 UTC 真實 GitHub Actions 發布 PR；Streamlit Cloud 上的 New UI2；以上皆無本批證據。
- **證據文件**：`docs/vnext/NEWUI2_CAPMAP_3COL_2026-11-10.md`、`docs/vnext/NEWUI2_CUTOVER_GAP_MATRIX_2026-11-10.md`、`docs/vnext/NEWUI2_EPS_AND_DIGEST_ONEBRAIN_RESEARCH_2026-11-10.md`（皆單組產出、未經第二組獨立複驗）。待辦見 `docs/BACKLOG.md` 2026-11-10 Issue #1121 追加段。


### DEC-159｜Issue #1127 P-4 S7/S8 施工轉錄與設計決定：採「側車」揭露省略，不升 Digest v2（2026-11-11）

- **來源／效力（據實，不誇大）**：
  - **授權範圍**＝客戶授權；來源＝GitHub Issue #1127（標題「[已授權] New UI2 Stage F P-4：Evidence→Digest headless 組裝及省略揭露（S7/S8）」，2026-11-11，台北日期以 Issue #1127 日期為準）。Issue 內文自述為客戶在 ChatGPT 對話回覆「同意 P-4」的**轉錄**、不含原對話 URL；本條再依該 Issue 轉錄，**非客戶逐字原文、非 QA PASS**；原始逐字對話不在 repo（**NOT VERIFIED by repo**）。
  - **設計決定**（下方「側車」各點）＝**AI 總管**依 `CLAUDE.md` §-1.5 v3 §03-1 的內部技術決策，**不是客戶裁示**；客戶只授權「P-4 S7/S8 最小可測程式碼」，未裁示採哪種 schema 做法。
- **授權邊界（轉錄自 Issue #1127）**：僅 `docs/vnext/NEWUI2_EPS_AND_DIGEST_ONEBRAIN_RESEARCH_2026-11-10.md` §2.4 的 P-4——**S7**＝Evidence→Digest 的 headless 組裝、**S8**＝省略揭露（`total`／`shown`／`omitted_count` 類）。**不升完整 Digest v2、不做 P-1 全量、不建 production caller、不做 P-2／P-3／OneBrain Stage G、不新增資料取數／來源／Provider／UI 表層／session 寫入。** 發現觸及凍結契約或新投資語意須停在 Gate。
- **設計決定：採「側車（sidecar）」，避免升 Digest v2**：
  1. **Digest v1 凍結契約未動**：`shared/decision_digest*.py`（既有）、`SCHEMA_VERSION`、`MAX_ACTIONS`、列舉成員皆**未修改**；Digest 本身一個欄位都沒加。
  2. **builder 僅純加性**：`src/services/decision_digest_builder.py` 新增 `plan_action_selection`（回 `ActionSelectionPlan`，攤開 builder 的行動選取與各分類計數）；站內列掃描抽成單一共用迴圈 `_scan_action_rows`（回 `_ScanResult`），`build_decision_digest` 路徑（`_action_candidates`）與 `plan_action_selection` **共用同一份判定、不得各寫一份**；分支順序與原 builder 逐一相同，只在原本 `continue` 處多記分類計數；輸出行為中立，既有測試未改。作者以 **24000 組隨機輸入**比對，輸出與舊版**逐位元相同**（作者自跑，非獨立驗證）。
  3. **掃描分類原則（第三輪回修後；寫死）**：builder 掃描時**每一個站內列都必歸入互斥窮盡的分類**，不得有任何一列被靜默略過。分割恆等式（由測試守住）：`rows_total == 候選 + non_action + not_held + excluded_invalid + unrecognized + unmatched + non_mapping`。其中 `not_held`（held 缺／False）、`non_action`（合法非行動碼 premium／cruise 且 ticker 對得上 held 持股）屬**合法且已知的排除**；`excluded_invalid`、`unrecognized`、`unmatched`、`non_mapping` 屬**未能讀入**。另有**正交疊加計數** `duplicate_rows`（同 ticker 出現在 ≥2 個 held 站內列者的所有列數；**不在分割內**，builder 選取行為不變）。持有列另有自己的分割：`holdings_rows_total == non_mapping + not_held + held_keyed + unkeyed_held`。新的靜默略過一律「先分類再計數」，**不逐例補丁**。
  4. **新增 L0 `DigestCoverage`**（`shared/decision_digest_coverage.py`，`COVERAGE_SCHEMA_VERSION = "digest_coverage.v1"`，與 Digest 版本號互相獨立；**尚未發布，三輪回修皆未升版，仍為 v1**）。欄位：`actions_total_eligible`／`actions_shown`／`actions_omitted_count`／`actions_max`／`excluded_invalid_rows`／`unkeyed_held_count`；`station_rows_unmatched`（**由 `actions_unmatched_dropped` 更名**——因未發布、無 production caller，無相容問題；語意擴大為含非行動碼 ticker 不在 held 持股、大小寫／空白不符、不在 `holdings_rows`、沒有 `HoldingKey`）；`station_non_mapping_rows`／`holdings_non_mapping_rows`（站內／持有列中非 Mapping 的項，原本被靜默略過）；`unrecognized_action_code_rows`（held、無異常，但 `_action` 缺／None／未知碼如 `'Add'`、`'zzz'`）；`duplicate_station_ticker_rows`；`holdings_without_station_row`（held 持股沒有任何同 ticker held 站內列的數量）；`digest_holdings_available`／`digest_actions_available`（由 digest 推得，皆 bool）；加上四段 `SegmentEvidence`（market／risk_cap／holdings／actions）。**`is_complete` 為唯一完整性判定**，要求**九個計數全 0**（`actions_omitted_count`／`excluded_invalid_rows`／`unkeyed_held_count`／`station_rows_unmatched`／`holdings_without_station_row`／`station_non_mapping_rows`／`holdings_non_mapping_rows`／`unrecognized_action_code_rows`／`duplicate_station_ticker_rows`），**且**兩個 digest 可用旗標皆 True，**且**四段 `used` 皆 True；物件不合法即 False（fail-closed）。**不能評估的計數為 `None`，不是 0**；不含 confidence／score／neutral／safe 語意。
     - ⚠️ **`is_complete` 不判斷新鮮度**：它只回答「有沒有東西沒被讀進來」。例如 risk_cap 的 `snapshot_ts` 很舊（如 2025-01-01）而證據沒被拒用時，該段仍 `used=True`、`is_complete` 可為 True；coverage **如實揭露**該段 `as_of`（取該段 OK 事實最舊者），由讀者自行判讀，本物件不替讀者判舊。
  5. **新增 L3 `assemble_digest`**（`src/services/decision_digest_assembly.py`）：純函式，回 `AssembledDigest(digest, coverage)` envelope；不讀 session、不取數、不呼叫時鐘、不碰 UI／app。`AssembledDigest` 建構時交叉驗證 coverage 與 digest：`actions_shown`、`unkeyed_held_count`、兩個 digest 可用旗標、四段 `used`，以及 used 段的 `source`／`as_of`（取該段所有 OK 事實 provenance 中**最舊**者，使 fresh 的 macro 戳不會讓 coverage 看起來比 `cap_pct` 快照日更新）；不一致即 `ValueError`。
  6. **零行動／`station_rows=[]` 一律 `is_complete=False`**：v1 builder 的 holdings／actions 段只有在「至少一項行動事實」時才 AVAILABLE，**無法區分「沒事做」與「判不出來」**，故保守 fail-closed。這句的意思是「v1 Digest 不能證明沒有遺漏」，**不是**「有東西漏了」；要 Digest v2 能區分後，兩個可用旗標才可放寬。
  7. **證據 fail-closed**：證據被拒用（無日期戳、`FETCH_FAILED`／`UNDETERMINED`、freshness 非 `FRESH`——含 stale、PIT 違反）時，**不只不傳該段 stamp，連同該段上游輸入（`macro_state`／`allocation` 或 `station_rows`）一併不傳 builder**，並在 coverage 記錄原因；理由見該檔 docstring（stamp 被拒仍傳 `macro_state` 會讓 `risk_cap.cap_pct` 以快照時間變成 OK）。不補日期、不補 0、不補 neutral／HOLD。
- **為何採側車而非直接在 Digest 加欄位（兩邊理由並陳）**：
  - **直接加 `omitted_count` 欄的理由（仍成立）**：揭露與 Digest 同物件，消費者不必多拿一個物件、不會漏讀。
  - **側車勝出的理由**：Digest v1 凍結（契約 §5：不得改欄位／升版／動 `MAX_ACTIONS`），加欄位即屬 v2，須 Stage F 的 High Gate＋獨立 QA，超出 Issue #1127 授權；側車讓 v1 消費者零影響，Digest v2 日後吸收這些欄位時側車可退役。**代價見下方已知限制。**
- **回修緣由（據實）**：獨立 QA 共**三輪**，每輪都是發現問題、**不是 PASS**。第一、二輪發現 `is_complete` 空洞（builder 靜默丟列、無法區分「沒事做」與「判不出來」），回修於 `571302e1`（wip）／`95bcf809`；原版為 `7cfeb31d`（commit 層級無法逐輪對應，據實不逐輪標註）。**第三輪（第三位 QA）反例**：(1) 站內 held 列的 `_action` 為未識別碼（如 `'Add'`）時整列被靜默略過、仍 `is_complete=True`；(2) 站內／持有列中的非 Mapping 項被靜默略過；(3) 同 ticker 多個 held 站內列互相衝突卻無任何揭露；(4) 非行動列（premium／cruise）的 ticker 不在 holdings 時仍 complete。**修法**不是逐例補丁，而是改為上列第 3 點的「每個掃描列必歸入互斥窮盡分類（分割恆等式）」，並把各細項各給一個計數、全部納入 `is_complete`；回修於 `50da5574`（wip）／`8dc1ddf0`。具體 QA 原始回報不在 repo，上列反例為作者轉述。
- **與契約 §6 A6／A7 的關係（QA-A 要求，據實）**：側車的 `excluded_invalid_rows` 與契約 §6 **A7**、`segments` 與 **A6**／**A1** 的語意**部分重疊**。**A6／A7 仍未完成**；側車只是 v1 過渡揭露，**不得**成為第二個 SSOT——日後 Digest v2 吸收 A6／A7 時，以 v2 契約欄位為準，側車退役、不得並行維護兩套定義。
- **已知限制（完整列出，據實）**：
  1. **裸 `DecisionDigest` v1 本身仍沒有 omitted 欄位**；只拿到 Digest 物件而沒拿 coverage 側車的讀者，仍**看不出少了什麼**。把 coverage 嵌入 Digest 屬未來 v2 Decision Gate，**本批未做、未核准**。
  2. **`AssembledDigest` 不防惡意偽造**：`total`／`omitted`／`excluded`／`unmatched`／`unrecognized`／`non_mapping`／`duplicate`／`holdings_without_station_row` 在 digest 內**看不到**，envelope 只能交叉驗證 digest 內可見者（shown、unkeyed、段落 used、source／as_of、availability 旗標）；其餘計數靠 `plan_action_selection` 與 builder 共用同一掃描迴圈、parity 測試（固定種子隨機輸入）與測試保證。
  3. **零行動／`station_rows=[]` 一律 `is_complete=False`**（v1 無法區分「沒事做」與「判不出來」；要 Digest v2 才能放寬）。
  4. **證據被拒用時，`station_rows` 的列層級型別錯誤不 fail loud**（該段上游輸入不交給 builder，builder 不會掃到；頂層型別 Mapping／list／tuple 仍會檢查）。
  5. **ticker 為精確字串比對**：大小寫／空白不同者被計入 `station_rows_unmatched`／`holdings_without_station_row`（揭露，不是修正；builder 比對行為不變）。
  6. **`held` 缺失（缺／None）視為 `not_held`**：與 builder 既有行為相同（`held` 型別為 bool／None 以外仍 `TypeError`）；本批不改。
  7. **premium／cruise 在 builder 內為字串複本**（`_NON_ACTION_CODES = ("premium", "cruise")`；L3 不得 import `src.compute`，故無法直接引用 `dividend_station.ACTION_*`）；有一致性測試 pin 住與 `dividend_station.ACTION_PREMIUM`／`ACTION_CRUISE` 相同，但上游若新增碼，須同步修改（測試會紅燈提醒）。
  8. **risk_cap 舊快照仍可 complete**：`is_complete` 不判斷新鮮度（見上第 4 點的 ⚠️）；只是 `as_of` 如實揭露，讀者須自行判讀。
  9. **無 production caller**：`assemble_digest` 目前沒有任何正式路徑呼叫；不改 UI、不接線、無新資料來源。
  10. **P-4 完成 ≠ Stage F 完成，也 ≠ C1～C7 切換條件通過**；Digest 的 A2（stale 入 Digest）等 v2 加性欄位、OneBrain Stage G 皆未動。
  11. 仍 **NOT VERIFIED**：Streamlit Cloud 上的 New UI2、ETF Managers 2026-11-16 20:00 UTC 首次排程真實 Actions PR、Open 資料 PR #1124／#1125／#1126 的 PIT（本批與其完全隔離，未碰）。
  12. **站內列 `_detail` 為 str／list（非 Mapping）時 builder 只認 Mapping、仍取用該列**，`is_complete` 可為 True（第四輪獨立 QA 發現）：正式 producer 給 dict，僅上游契約漂移才觸發；builder 既有行為、非本 PR 引入，本批未改、未揭露於 coverage 計數。
  13. **`held=False` 的衝突站內列被歸 `not_held`、不計入重複計數**（第四輪獨立 QA 發現）：同 ticker 一列 `held=False` 帶 cut、另一列 `held=True` 帶 add 時，前者歸 `not_held`，不進重複計數；builder 既有行為、非本 PR 引入，本批未改。
  14. **列內 `portfolio_id` 與 `holding_keys` 鍵不一致、額外欄位（如 `_warning`）不被讀取**（第四輪獨立 QA 發現）：builder 只讀其認得的鍵，不一致與額外欄位皆不揭露；builder 既有行為、非本 PR 引入，本批未改。
- **測試結果（據實）**：第三輪回修後作者自跑 **1361 passed**（digest 相關測試＋`tests/test_c3_layering_guard.py` 分層守衛）；兩個新測試檔（`tests/test_decision_digest_coverage.py`、`tests/test_decision_digest_assembly.py`）合計 **364** 條（`pytest --collect-only` 實測）。builder 新舊版以 **24000 組隨機輸入**比對，輸出逐位元相同（作者自跑）。**獨立 QA 前三輪皆發現問題並已回修；獨立 QA 第四輪 PASS（作者以外；約 7 萬組 oracle、3 萬組新舊 builder 逐位元比對、25 突變全殺〔0/25 存活〕；指定 pytest 1696 passed；無 blocker／major，另發現 3 項 minor 已記入已知限制 12～14）；原生 CI 待補**——本條**不得**讀成已通過原生 CI 或已合併。
- **程式落點**：`shared/decision_digest_coverage.py`（新）、`src/services/decision_digest_assembly.py`（新）、`src/services/decision_digest_builder.py`（純加性修改）、兩支新測試檔；commit：原版 `7cfeb31d`；第一、二輪回修 `571302e1`／`95bcf809`；第三輪回修 `50da5574`／`8dc1ddf0`（分支 `ccr-588f897e-7wzywe`，PR 號待補）。獨立 QA 第四輪 PASS（作者以外；約 7 萬組 oracle、3 萬組新舊 builder 逐位元比對、25 突變全殺；指定 pytest 1696 passed）；原生 CI 待補。
- **單組產出聲明**：上述事實取自 commit 內容、三個檔案的 docstring 與程式、Issue #1127；本條由單組撰寫，**未經第二組獨立複驗**。

- **DEC-159 合併後註記（2026-11-11；只追加，以本註取代上文「測試結果」等處「尚未合併／原生 CI 與第四輪待補」之效力，原文不改）**：PR #1128 已 squash 合併為 main `720ccbed420da1e7c6066d81c20ce71698f4bf1d`（head `05d2733c`）；同 head 原生 CI 5 項全 success；第四輪獨立非作者 QA PASS（約 7 萬組 oracle、3 萬組新舊 builder 逐位元比對、25 突變 0 存活，無 blocker／major）。
  - 最後一個 commit（日期相依測試修復，6 行，`TEST-DATE-DEP-1`）僅作者端驗證＋突變，未另送獨立 QA；本註為單組撰寫，仍 NOT VERIFIED：Cloud UI2、真機、ETF Managers 2026-11-16 20:00 UTC 真實 Actions PR、資料 PR #1124～#1126（PIT）；P-4 完成 ≠ Stage F／C1～C7 通過，無 production caller。

### DEC-160｜Issue #1130 客戶裁示轉錄：headless 唯讀 Gate、A2 stale 語意、Digest v2 B＋M1 方向、TEST-DATE-DEP-1 最小修復（2026-11-11）

- **來源／效力（據實，不誇大）**：決策者＝客戶；來源＝GitHub Issue #1130（標題「[已授權｜方案 A] Headless 輸入與權限唯讀 Gate、A2 stale、v2 B+M1 方向及日期測試最小修復」）。Issue 內文自述為客戶在 ChatGPT 對話回覆「同意方案 A」的**轉錄**、不含原對話 URL；本條再依該 Issue 轉錄，**非客戶逐字原文、非 QA PASS**；原始逐字對話不在 repo（**NOT VERIFIED by repo**）。基準 main `8df4797d898f7002ff6c55a3fa6c3b2371a93720`。
- **裁示 1｜Headless 市場／持股資料：只讀查證與授權邊界**：逐條查證 source→consumer→authority→as_of／freshness 矩陣；找不到現成且可授權的 headless 來源就標 `MISSING`／`NOT VERIFIED` 並提 Decision Gate。**禁止**新增市場位階計算、headless fetcher、proxy、OAuth bypass、服務帳號讀私人 Sheet、API、Secret、新持久化／排程、production caller；不把 session 來源假裝成 headless、不建第二套 Pipeline；持股須維持每位使用者的 Sheet／授權／權限 isolation，不得以「缺資料」改用其他帳戶；「能讀」不等於公開、跨戶使用或有效來源。
- **裁示 2｜A2 stale 語意**：stale／來源失敗／PIT 不合格的值可在**隔離的 Evidence／audit／coverage 記錄**保留 `source`／`as_of`／`observed_at`／`fetched_at` 與拒用原因（數值保留須遵守原存取權限）；**不得**當 fresh／eligible 進入 deterministic decision、動作、Risk Cap、排序、信心或摘要的有效依據，不得補 0／neutral／safe／HOLD；區分 `stale evidence retained` 與 `stale value used for decision`。P-4 現有 fail-closed 拒用維持有效。本次只核准語意方向與文件契約研究，不改 Digest 欄位、schema／validator、計算、UI；與凍結契約衝突則回報 Gate。
- **裁示 3｜Digest v2 方向**：記錄為 architecture direction——`Digest v2 加性欄位吸收 S8 coverage；M1 v1／v2 雙版並存；v2 強制 coverage；v1 保留相容驗證`。**不是**破壞凍結 v1 的授權；禁止實作 v2、`schema_version`、A1／A2／A6／A7 新欄、升降版轉換、v1 移除、P-1 runtime、production caller、OneBrain；後續須獨立 schema／compatibility／PIT Decision Gate。
- **裁示 4｜TEST-DATE-DEP-1：僅最小測試修復**：只准測試／fixtures（凍結或參數化必要時鐘，補公告日當日／前日、跨月、適用的跨年邊界）；禁止改正式程式、公告延遲、觀測日、公式、資料、PIT 例外、全域 freeze、skip／xfail、降低守衛、新增或修改 GitHub Actions workflow／cron；無法模擬未來日期則標 `NOT VERIFIED`。**本條不記載測試修復結果（由後續另補）。**
- **裁示 4 執行結果補記（作者端驗證，未經獨立 QA；獨立 QA 待補；以本條取代上條「本條不記載測試修復結果」之效力，原句不改）**：
  - **工作 C**：測試端 +8／-1 於 `tests/test_c1_observability.py`（寫入 pickle 後 `os.utime(pkl,(time.time(),time.time()))`、`import time`）＋新增 `tests/test_date_dep_boundaries.py`（51 測試：月營收公告延遲＝次月 1 日＋10 天，即次月 11 日／月底後第 11 天；公告日當日／前一日、跨月（含閏年 2028-02-29）、跨年；以 `no_real_clock` 證明被測兩模組只用注入 `as_of`、不讀真實時鐘；窄範圍時鐘模擬 2026-12-15／2027-01-15 皆綠）。未改正式程式、延遲常數、PIT 邏輯。
  - ⚠️ **更正（重要）**：Issue #1127 研究留言與先前 QA 曾稱 `test_c1_observability::TestPcrSource::test_old_pickle_returned_as_is` 於 2026-12-01 起轉紅。複查結論：該測試在真實時鐘與 `date.today`／`pd.Timestamp.now`／`tw_now` 偽裝至 2026-11-11／12-01／12-15／2027-01-15 **皆通過，沒有真實日期相依**；先前紅燈最可能來自「只偽裝 `time.time`、檔案 mtime 仍是真實時間」的不一致偽裝（被測 `build_leading_fast` 以 `time.time()−getmtime(pkl)<30 分` 判新鮮；**推測，未核對當時偽裝**）。`os.utime` 修法只讓該測試在 freezegun 式時鐘位移下保持穩定，屬**防禦性加固，非修日期相依缺陷**。故 `TEST-DATE-DEP-1` **實際已確認的日期相依測試只有 `test_d3e_mrev_fail_cache`**（#1128 已補釘）。
  - **複查 `frozen_now` 補釘**：只把 `as_of` 釘在 2026-09-28，未碰延遲常數或 PIT 邏輯；守衛在 `test_c4b_revenue_scoring`／`test_c4e_unverified_key_cap`／`test_g2_monthly_freshness` 等；延遲常數突變（0／9／11／12）使邊界測試紅 26／19／20／20 項，契約 grace 0→7 紅 7 項。
  - **NOT VERIFIED**：真正 libfaketime／freezegun（環境無）；未掃全 repo；單組驗證；其他測試檔的日期相依未掃（QA-E 當時偽裝有缺陷）。**獨立 QA 待補。**
- **與 DEC-159 的關係**：**不取代** DEC-159。DEC-159 的側車設計與 P-4 fail-closed 拒用維持有效；本條只是把「stale 保留於隔離記錄、不得用於決策」與「v2 長期方向 B＋M1」記為客戶方向，並要求後續 Gate。
- **本批結論摘要（AI 單組撰寫，未經第二組複驗）**：新增 `docs/vnext/STAGE_F_HEADLESS_INPUT_AND_STALE_SEMANTICS_2026-11-11.md`——(1) 公共市場資料僅「加權指數日 K 趨勢」有可重用 headless 讀取路徑；市場位階／light／health、`exposure_limit_pct`／allocation、`macro_state.json` 的 headless 副本、真實市場廣度、PIT `release_date` 欄均為 `MISSING`；(2) 私有持股僅登入脈絡可得，既有 SA 推播路徑授權範圍是「每日持股推播」，**不等於**授權 Digest；(3) A2 兩種解法（A2-i／A2-ii）列出優缺點，待 schema Decision Gate；(4) 列出 Gate G-F1～G-F6，皆待客戶裁示、未啟動。**本批未改任何程式、schema 或欄位，非施工授權。**

### DEC-161｜Issue #1132 客戶裁示轉錄：G-F1 方案 A（既有 canonical 市場資料 headless 唯讀契約與缺口驗證）（2026-11-11；docs-only）

- **決策者**：客戶。Issue #1132 轉錄，**非逐字、非 QA PASS**。
- **裁示**：僅核准 G-F1「方案 A」——重用現有 canonical／L3 市場資料的唯讀契約設計、獨立證據核對與缺口登記；對尚無合法、PIT 合格、可 headless 來源的市場位階／light／health／曝險，明確顯示「無法判定」或「尚未提供」，不補 neutral／0／safe，不以過去 forward-test 快照代替 live 市場判斷；給出至少三種下一階段方案並比較。
- **不授權**（照 Issue #1132）：不改位階算法／廣度 proxy 開關／風險曝險趨勢公式／D1–D5／PIT 例外；不新增 fetcher、API、source、pipeline、job、cron、Secret；不以 session 的 `macro_state.json` 或推播 SA 冒充 headless source；不實作 P-1、Digest v2、OneBrain、production caller、UI2 真資料接線；不動登入／OAuth／Sheet、Risk Cap、舊 UI、正式路由；不動資料 PR #1124–#1126、#1119 維持 HOLD。G-F2、G-F3／A2（現有 stale fail-closed 維持）、G-F4、G-F5／G-F6 仍待另行裁示。
- **本批結論摘要（兩位獨立 agent 二次核對，仍屬 agent 產出、未經人工複驗）**：新增 `docs/vnext/STAGE_F_GF1_HEADLESS_MARKET_CONTRACT_2026-11-11.md`——(1) 唯一已具備 headless 唯讀路徑的是加權指數日 K（`get_twii_trend_view`，UI2 已接）；(2) inst／margin／sector_flow／m1m2／pmi 可讀 git 檔但 UI2 未接、五檔皆無 `release_date`；(3) 位階／light／health／曝險輸入只在 session，現行 production 為 `unknown`／⬜；(4) `signals.parquet` 不得充當 live 判斷；(5) 對 DEC-160 研究文件列出四點二次核對更正；(6) 下一階段三方案比較，AI 推薦（非客戶裁示）先方案 1 最小可推進項、並請客戶裁示方案 2 前置問題，不建議方案 3。**本批未改任何程式、schema、旗標，非施工授權。**
- **與 DEC-160／DEC-159 的關係**：**不取代**。DEC-160 的 Gate G-F2～G-F6 與 DEC-159 的側車設計、P-4 fail-closed 維持有效；G-F2～G-F6 仍待裁示。

### DEC-162｜Issue #1134 客戶裁示轉錄：市場頁 Old-UI-First 唯讀盤點與接線設計（2026-11-11；docs-only）

- **決策者**：客戶。Issue #1134 轉錄，**非逐字、非 QA PASS**。
- **範圍（照 Issue #1134）**：僅核准 UI2 市場頁「三大法人（inst）／融資（margin）／板塊資金（sector_flow）」的 Old-UI-First 唯讀盤點、Old → Legacy New → UI2 能力對照、`source → canonical L3 read-only service (proposed) → UI2 VM (proposed)` 接線設計，以及 A1／A2／A3 三方案比較。
- **不授權（照 Issue #1134）**：不實作 UI2 接線或 adapter；不動任何 production 程式或測試；不切換 default；不改舊 UI；不碰登入／OAuth／Sheet、Actions／workflow、Secrets、Risk Cap、G-F2～G-F6、Digest v2、OneBrain、D1～D5、EPS、廣度開關、位階演算法、資料來源／API／cron；不授權新正式指標、法人強弱／融資趨勢／資金流信號、訊號分數、權重、排名。#1124～#1126 不得順手 merge／rebase／close／改寫（#1126 PIT NOT VERIFIED）；#1119 HOLD。
- **本批結論摘要（四位 agent 唯讀盤點，agent 產出、未經人工複驗）**：新增 `docs/vnext/NEWUI2_MARKET_CHIPS_OLD_UI_FIRST_MAPPING_2026-11-11.md`——(1) 三項資料在 UI2（`shared/ui2_contract`、`src/ui2`、`src/services/ui2`）皆 0 命中，UI2 完全未呈現；(2) 舊 UI 三項皆耦合判讀語言（±100 億結論卡、3400／2500 融資燈、四象限白話），UI2 不應沿用；(3) `finmind_inst.parquet` 只有外資，三類法人只能來自 session 路徑；(4) 融資『資料疑義』目前只是 UI 寫死文字，資料層無逐列旗標（tab_macro_v2 另有 `hold_reason`／『⚠️ 圖表資料疑義』卡片層機制，非逐列旗標）；(5) 手機 390×844 Real feed p4_market `nav_margin_after_risk`＝168.8px（量測值）；160px 門檻僅套用 stale／unavailable 場景、不含 Real，故 8.8px 餘裕不作承重論據（INFERENCE／Real 合格門檻 NOT VERIFIED，以客戶線框與實測為準）；新 section AI 推薦放日 K 之後（不動既有首屏錨點），須先出文字線框草稿；(6) AI 推薦（非客戶裁示）A2 分兩步，不建議 A3。**本批未改任何程式、測試、schema、旗標，非施工授權。**
- **與 DEC-157／DEC-161 的關係**：**不取代**。DEC-157 市場頁順序與 `MARKET_CARD_IDS` 固定 6 張維持有效；DEC-161 的 G-F1 契約與缺口維持有效，本批補能力對照與接線提案。

### DEC-163｜Issue #1136 客戶裁示轉錄：市場頁「市場資金與籌碼」文字線框方向（2026-11-11；docs-only）

- **決策者**：客戶。Issue #1136 轉錄，**非逐字、非 QA PASS**（客戶在對話回覆「同意」四項建議，不是逐字展開說明）。
- **四項同意要點（照 Issue #1136）**：(1) A2 **步驟 1 僅 docs-only 文字線框**，草稿完成後回客戶正式拍板，不得擅自進入步驟 2 程式接線；(2) 新 section 置於 **OneBrain 下方**，不插入六張核心卡、不改 OneBrain 或首屏錨點，390／1440 首屏可達性與導覽不遮擋須驗證（真機／Cloud 未做標 NOT VERIFIED）；(3) 初版三項：外資淨買賣超（僅外資，不稱三大法人）、融資餘額（億元，不沿用 3400／2500）、板塊資金流最新交易日淨額（不含四象限、動能、Top-N 推薦排序）；(4) 配色中性色＋明確正負號＋文字標籤，不沿用舊 UI 負值紅與外資藍／投信綠／自營金作投資訊號，Dark-only 不變。
- **本批產物**：`docs/vnext/NEWUI2_MARKET_CAPITAL_FLOW_TEXT_WIREFRAME_2026-11-11.md`（草案，待客戶正式拍板；上報點與待確認項 G-1～G-10 見該文）。**線框不是經驗證畫面，未做真機／Cloud／瀏覽器驗收（NOT VERIFIED）。**
- **與 DEC-157／DEC-162 的關係**：**不取代**。DEC-157 市場頁順序與 `MARKET_CARD_IDS` 固定 6 張維持有效；DEC-162 Mapping 文件 §4 AI 推薦新 section 放日 K 之後，**客戶 Issue #1136 指定改為 OneBrain 下方，以客戶指定為準**（AI 推薦非客戶裁示，兩者不衝突於客戶原文）。
- **不授權**：A2 步驟 2 程式施工；不改 production code／tests／UI2 VM／feed／section、資料讀寫、fetcher、source／API、PIT／公式／權重／燈號、Risk Cap、D1–D5、EPS、OAuth／Sheet、Digest v2、P-1、OneBrain、Actions、cron／Secrets；#1119 HOLD；#1124～#1126 不處置。

### DEC-164｜Issue #1140 客戶裁示轉錄：G-1～G-10 正式裁示、融資＋板塊唯讀 L3 與兩項獨立安全修復授權、Digest regime/light 相容性 Gate（2026-11-11）

- **來源／效力（據實，不誇大）**：決策者＝客戶；來源＝GitHub Issue #1140（客戶裁示轉錄）。本條再依該 Issue 轉錄，**非逐字展開、非 QA PASS**；僅下列「客戶原文」引號內為 Issue 所載客戶語句，其餘為依 Issue 整理（原始逐字對話不在 repo，NOT VERIFIED by repo）。基準 main `1e5542a8`（#1142 合併後；#1141 為 `907322aa`）。
- **客戶原文（Issue #1140 所載）**：「同意你的六項 G 表建議，G-4、G-6～G-8 沿用既有方向。授權融資＋板塊唯讀 L3 service 和單元測試（不接 UI、不啟用新來源），以及價格≤0、未來 as_of 的獨立安全修復；Digest regime/light 先做相容性 Gate，不改凍結 Schema。」（引文略去 Issue 後半『請正式寫入 GitHub，給 Claude Code 完整提示語，維持靜默自主巡航。』）

#### 一、G-1～G-10 正式裁示表（依 Issue #1140 轉錄；題號沿用 `docs/vnext/NEWUI2_MARKET_CAPITAL_FLOW_TEXT_WIREFRAME_2026-11-11.md`／DEC-163）

| 題號 | 議題 | 裁示（客戶） |
|---|---|---|
| **G-1** | 區塊名稱與文案 | 區塊稱「**市場資金與籌碼**」；文案「**客觀數據，不構成買賣建議；缺值不補**」；位置在 **OneBrain 下方**、六張核心卡不變（承 DEC-163／DEC-157） |
| **G-2** | 折疊 | **不折疊**；不改 `SHOWN_FOLDS`；Human UI 不增完整 evidence expander |
| **G-3** | 板塊摘要 | **方案 A**：有標示、可驗證的**衍生聚合**，只對合格資料計算。須驗：去重、口徑、一致性、缺值；**正＋負＋持平＋未觀測＝應涵蓋總數**；coverage／上市上櫃不完整時**不得稱全市場**、不得給誤導性合計；**不做依淨額排序的 Top／Bottom／排名**；衍生聚合**必須揭露**；完整來源列保留於 canonical／Evidence |
| **G-4** | 正負號與色彩 | 以 **＋／−** 與「**淨買超／淨賣超**」標籤表達；**中性色**，不以負值紅暗示賣出建議 |
| **G-5** | 單位／sanity 不通過文案 | 原則上顯示原有 `⬜ 資料未取得`；**僅**在已由資料檢查判定 sanity 未過時才附「**資料檢查未通過**」；**不得**在原因未知時假稱單位錯誤 |
| **G-6** | 資料延遲 | 一般延遲**不另加推測文字**，資料日外露；真 stale 照既有規則警示 |
| **G-7** | Secondary Visual | **不算** Secondary Visual（純文字，**不新增圖表**） |
| **G-8** | 無障礙 | 採 `role="group"`＋可辨識 `aria-label`；實作階段以無障礙測試驗證 |
| **G-9** | 授權範圍 | **明確核准僅**：兩個獨立唯讀 L3（融資、板塊）與其單元測試，以及兩項獨立安全修復（價格≤0、未來 as_of）。**未核准**：UI2 feed／section runtime 接線、上線、外資 L3、資料來源變更 |
| **G-10** | 板塊口徑 | 「**三大法人合計（外資＋投信＋自營商），依個股張數×收盤價彙總至板塊**」；**不拆分項**；與「大盤外資淨買賣超（僅外資）」**不同、不能直接比較或加減** |

- 文字線框**方向**獲核准；**正式 runtime UI 接線仍需新 Gate**（不得擅自進入）。

#### 二、授權範圍與 Digest 相容性 Gate

- **授權施工（僅此）**：(1) 融資唯讀 L3 service＋單元測試；(2) 板塊資金唯讀 L3 service＋單元測試（皆**不接 UI、不啟用新來源**）；(3) 獨立安全修復：價格≤0 一致拒用、未來 `as_of` 不再顯示負過期天數。
- **Digest regime/light：先做相容性 Gate（研究；Issue 另允許新增獨立反例測試，本批未新增）**，**不改凍結 Schema**：不改 v1 schema／validator／action semantics、不升 v2、不建 production caller、不建 OneBrain runtime。
- **永久禁止清單（分兩組；本條記錄並沿用，與 DEC-160／DEC-163 不授權事項疊加，不取代）**：
  - **(甲) Issue #1140 原清單逐項（轉錄，非逐字）**：不修改舊 UI；不切換正式 app；不動 Risk Cap；不動 D1–D5；不動 EPS／廣度／公式；不新增 API／MCP／source／fetcher／cron／Secrets；不動 OAuth／Sheet；不做外資 L3；不接 UI2 real_feed／section runtime；不實作 Digest v2；不建 OneBrain AI Provider／成本機制；不做 #1119 Actions 精簡（#1119 維持 HOLD）；不處置 #1124～#1126（#1126 PIT 未驗，不得順手合併／改寫／rebase）；上游 TWSE／TPEX／FinMind 再散布權利、Streamlit Cloud、真機、Playwright 皆 **NOT VERIFIED**。
  - **(乙) 沿用 DEC-160／162／163，Issue #1140 未重述**（為避免遺失而一併列出，**不是**本 Issue 新增的客戶語句）：不改位階／燈號／權重／PIT；不實作 P-1；不產生買賣建議、法人強弱、融資趨勢、訊號分數、排名；不建 production caller。

#### 三、本批 AI 總管內部拍板（**技術實作細節，內部自決，依 v3 §03-1；非客戶裁示**）

| # | 決定 | 理由（FACT／INFERENCE 已標） |
|---|---|---|
| 1 | 板塊 L3 需「最新交易日淨額」，而既有 `read_sector_flow_cache` 只有近 5 日累計 `x_yi`（FACT）→ 在**既有** `reader.py` 新增**純讀** `daily_net.parquet` 的 L1 函式（Q-a） | 未改變指標定義、無新來源、不新增 fetcher／cron；L1 讀取留在 L1，L3 不直讀檔 |
| 2 | 新容差常數放**新檔** `shared/sector_flow_fact_thresholds.py` | `test_batch_z42` 以 sha256 釘住舊常數檔（FACT），改舊檔會破壞該守衛；新檔符合 §3.3 SSOT |
| 3 | 未來 `as_of`：TWII 卡片層採「Stale＋不顯示負天數＋『⚠ 可能已過期』」；日 K 維持 `FUTURE_DATE` 拒用；**兩者不對稱**（已知）；融資 L3 對未來日 **fail closed** | 卡片是「提示可能過期」、日 K 是「拒用不可信資料」，語意不同；不對稱登記於 BACKLOG 待辦 |
| 4 | 價格不合格沿用既有「讀不到」灰態字樣（`_UNREADABLE_TEXT`），**不新增文案** | 專用文案屬 L1 文字常數，需另 Gate；已登記 |

- 以上四點為**總管技術拍板**，已在交付報告揭露，**不得引用為客戶裁示**；客戶若認為其中任一點涉及業務語意，以客戶為準。

#### 四、與既有 DEC 的有效讀法（只追加；舊文不改）

- **DEC-163「待確認 G-1～G-10」**：本條為其**正式裁示**；DEC-163 文中「初版三項含外資淨買賣超」的**初版範圍**，有效讀法為：**本批只授權融資＋板塊兩個 L3，外資 L3 另案**（G-9）。DEC-163 BACKLOG 上報點 (b)「板塊 Top／Bottom N 屬新排名語意，需另 Gate」維持有效，G-3 已明確**不做**排名。
- **DEC-162 §4「新 section 放日 K 之後」**：維持被 DEC-163 以客戶指定「OneBrain 下方」取代；本條 G-1 再確認。
- **DEC-157／DEC-161／DEC-160**：不取代；Gate G-F2～G-F6、方案 2 前置問題**仍待裁示**；市場頁 `MARKET_CARD_IDS` 固定 6 張維持。
- **本批施工與研究產物（據實，詳見 BACKLOG／HANDOFF）**：批 1＝#1141（main `907322aa`）C1／C2 安全修復；批 2＝#1142（`1e5542a8`）融資／板塊唯讀 L3；批 3＝`docs/vnext/DIGEST_REGIME_LIGHT_COMPAT_GATE_2026-11-11.md`（研究，**不實作**）。
- **Digest A2 實作與否＝待客戶裁示**：研究文件的 AI 推薦（方案 A2）**不是客戶裁示**；未獲裁示前不動 `decision_digest_builder.py`。
- **仍 NOT VERIFIED**：Cloud UI2、真機、Playwright／瀏覽器 viewport、資料來源授權／PIT、ETF Managers 2026-11-16 20:00 UTC 首次排程、資料 PR #1124～#1126（PIT）。

### DEC-165｜Issue #1144 客戶裁示轉錄：同意方案 A——授權 Digest builder A2（白名單驗證＋反例測試，不改凍結 Schema）；UI2 runtime 接線僅前置 Gate 研究；雙端對話交接（2026-11-11；只追加）

- **來源／效力（據實，不誇大）**：決策者＝客戶；來源＝GitHub Issue #1144（2026-11-11，作者 `linchen-20200325`，OWNER）。本條依該 Issue 轉錄，**非 QA PASS、非施工完成**；僅下列引號內為 Issue 所載客戶原文，其餘為依 Issue 整理（原始逐字對話不在 repo，NOT VERIFIED by repo）。基準 main `7060cafe618ab93b0afd3d871397aec2071b2034`（#1143 合併後）。
- **客戶原文（Issue #1144 所載，逐字）**：「同意方案 A：授權 Digest builder A2 白名單驗證與反例測試，不改凍結 Schema；UI2 只做 runtime 接線前置 Gate，查核 coverage、PIT、資料授權及缺口，不接正式 UI。請記錄 GitHub、完成交接文件查核，並給 GPT 與 Claude Code 的新對話接手提示語。」

#### 一、授權範圍表（**已授權 ≠ 已完成**）

| 線 | 已授權內容（依 Issue #1144 轉錄） | 明確不含／限制 | 狀態 |
|---|---|---|---|
| **A 線 Digest A2** | 僅 `src/services/decision_digest_builder.py::_market_section` 輸入邊界：由**既有** `shared/regime_arbiter.py::REGIME_LIGHT` 推導 `_VALID_REGIMES`／`_VALID_LIGHTS` 白名單；比對只用 `strip().lower()`；合法 `Fact.text` **逐字保留**；名單外**非空**值（載入中／待評估／pending／loading／foo／TBD／異常 emoji 等）判 `INVALID`；既有 placeholder、`is_loaded=False`、無 stamp **維持 `MISSING`**，**不得洗成 `INVALID`、0、neutral**；附反例／正例、大小寫與空白、legacy placeholder／missing、summary／assembly fail-closed、等式 SSOT、mutation tests | 不改 `shared/decision_digest*.py` 凍結 Schema／validator／grounding；不改 `normalize_regime`、`get_macro_state`、regime／light deterministic 推導、Risk Cap、System Action；**不納入 A3 配對一致性**；**不夾帶 `market.health` 0–100 範圍驗證**（獨立 Gate）；若調整會破壞意外的合法值契約，或原型「0 測試轉紅」不成立 → **先停止該部分並上報**，不擅自改 Schema；實作前以**最新 main 與實際測試**為準（研究文件 `docs/vnext/DIGEST_REGIME_LIGHT_COMPAT_GATE_2026-11-11.md` §7.1／§7.2 為規格來源，不是結果） | **已授權、尚未實作**（本條撰寫時 0 行 production／test 變更） |
| **B 線 UI2 runtime 接線前置 Gate-only** | **唯讀**查核：既有 `margin_fact_service`／`sector_flow_fact_service` 與 canonical reader／`data_cache` 的 coverage（#1142 量測：板塊 41、觀測 38、未觀測 3，**非全市場完整覆蓋**）、PIT（觀測日／來源發布日或可得日／fetch 時點／假日／stale／partial／未來日期）、TWSE／TPEX／FinMind 使用與再散布條件、`G-F2～G-F6`、`I1140-*` 阻塞、G2F allowlist、FAKE／Real 對稱、OneBrain 下方 section、六張核心卡固定、390／1440 首屏／捲動／Cloud／真機／Playwright、五頁頂部導航；產出**最小候選施工方案與 3 方案比較（風險／速度／Token）** | **只研究／文件**：不改 `src/services/ui2/real_feed.py`、VM、views／section、白名單、程式、測試；不接 UI、不上線、不做外資 L3、不用新來源／API／排程；**最低 coverage 門檻未裁示，不得自設百分比**；parquet 缺 `release_date` → **NOT VERIFIED**（不得用 commit time 假冒）；上游授權找不到官方原文 → **NOT VERIFIED**（禁止推論「已獲授權」）；Cloud／真機／Playwright 未測一律標 NOT VERIFIED | **已授權、尚未施工**（UI2 runtime 接線**本身仍未授權**，需新 Gate） |
| **C 線 交接／SSOT** | 本 docs 同步（DECISIONS／BACKLOG／HANDOFF／PROJECT_STATE，append-only）；GPT 與 Claude Code 各一份新對話接手提示語；依 `PROJECT_RULES.md` 第 32 節先落盤再換對話；Auto-Ship（獨立非作者 QA、原生同 head CI、mergeable clean、0 unresolved、合併後重查 main） | 不另立第二份 handoff／memory／狀態檔（`PROJECT_RULES.md` 第 32 節第 3 點）；三批可在**已授權範圍內**靜默巡航，範圍外停手 | 同步本身為**已授權工作**；本條所在 PR 合併前**不得宣稱完成** |

#### 二、長期禁止清單（沿用並重申；與 DEC-160～164 疊加，不取代）

Digest v1 Schema／validator 凍結；Digest v2；OneBrain runtime／provider／付費；production caller（**A2 僅 builder 為例外**）；UI2 runtime 接線／正式 UI 上線；公式／燈號／Risk Cap／D1–D5／EPS／廣度；OAuth／Sheet；舊 UI；正式路由；#1119 維持 HOLD；#1124～#1126 不碰（不得順手 merge／rebase／改寫；#1126 PIT 未驗）；L3（#1142 已合併、未接 UI）不重做；外資 L3 另案。

#### 三、與既有 DEC／文件的有效讀法（只追加；舊文不改）

- **「Digest A2 待客戶裁示（`DG-DIGEST-A2`）」已過期**：DEC-164 四、末條「Digest A2 實作與否＝待客戶裁示」、BACKLOG `I1140-DIGEST-A2-IMPL`、HANDOFF Issue #1140 接手點第 1 項、研究文件 §9 `DG-DIGEST-A2`（問題：是否授權實作 A2）——自本 DEC 起**有效讀法為：客戶已裁示＝同意方案 A（A2）**。實作範圍以**本 DEC＋Issue #1144** 為準。研究文件原文保留不改。
- **A3 與 `market.health` 0–100 範圍**：研究文件 §9「附帶」列與 §7.1「可選 A3」——Issue #1144 **明確不含**，維持**獨立 Gate、仍未授權**（BACKLOG `I1140-DIGEST-HEALTH-RANGE` 不再「併 A2 裁示」，改為獨立 Gate）。
- **「UI2 接線新 Gate」仍未授權**：DEC-164 G-9／四「runtime UI 接線仍需新 Gate」維持；本條僅授權**前置 Gate 研究**，不是接線授權。`G-F2～G-F6`（DEC-157／160／161）**仍待裁示**；`I1140-COVERAGE-MIN` 最低覆蓋率門檻**仍未裁示**。
- **推薦 vs 裁示**：研究文件的 AI 推薦（方案 A2）與本條「客戶同意方案 A」對應；但**實作細節**（白名單推導方式、測試形狀）仍是 AI 總管依 v3 §03-1 的內部拍板，不得引用為客戶裁示。

#### 四、狀態分欄（防止把授權寫成完成）

| 類別 | 內容 |
|---|---|
| **已完成（FACT，GitHub main）** | #1141 `907322aa0af9570fdcca9a496ffdc83e275bfdd3`（C1 價格≤0 一致拒用、C2 未來 `as_of`）；#1142 `1e5542a87cdc0006a6535b34457f8b59a85f6baa`（融資＋板塊唯讀 L3，未接 UI）；#1143 `7060cafe618ab93b0afd3d871397aec2071b2034`（DEC-164＋Digest 相容性 Gate 研究文件） |
| **已授權、尚未完成** | A 線 A2 builder 實作＋反例測試；B 線前置 Gate 研究文件；C 線本 docs 同步（本 PR）與雙端接手提示語 |
| **未授權** | A3、`market.health` 範圍驗證、UI2 runtime 接線、外資 L3、Digest v2、OneBrain、production caller |
| **NOT VERIFIED** | Streamlit Cloud UI2、iOS／Android 真機、Playwright／瀏覽器 viewport、TWSE／TPEX／FinMind 再散布授權、parquet `release_date`／PIT、ETF Managers 2026-11-16 20:00 UTC 首次排程、#1126 PIT |

- **證據出處**：Issue #1144 本文（LIVE Gate 快照：#1141 head `4fefb9f0` CI 42993625770；#1142 head `7c7532ad` CI 43002344807；#1143 head `87e1170bf7c186adf2a47cb1d46c4b5f8cf691ad` CI 43005805156；Open PR 僅 #1124／#1125／#1126）。⚠️ 以上 head／CI 編號為 Issue 撰寫時快照轉錄，本撰寫組未於本回合另行查驗 PR 頁，**NOT VERIFIED by this docs author**；接手者須重查 LIVE GitHub。


### DEC-166｜Issue #1144 執行結果：A2 已完成（PR #1146）；B 線前置 Gate 研究文件已產出；仍待客戶裁示事項（2026-11-11；只追加；AI 總管事實更新，非客戶裁示）

- **來源／效力**：本條為 AI 總管對執行結果的事實記錄，**不是客戶新裁示**；其中「AI 推薦」屬 RECOMMENDATION。本 docs PR 號：#1147。

#### 一、已完成（FACT）

- **A 線 Digest A2**：PR #1146 已 squash 合併，main `d4f7b3f6a64d177b7ee0953dc22563adf59120e4`；同 head `3c534de` 五項 CI success；獨立 QA PASS（diff 僅 2 檔；突變測試 30 項 failed 轉紅；邊界手測）。QA 觀察（非缺陷）：非 str 的非空值走既有路徑→MISSING；全形與 VS16 字元判 INVALID。範圍仍僅 `_market_section` 輸入邊界，未改凍結 Schema。
- **B 線研究文件已產出**：`docs/vnext/UI2_RUNTIME_PREGATE_RESEARCH_2026-11-11.md`（唯讀、docs-only）。獨立 QA PASS，附三項小修已修（§1.1 標籤映射未查證補註、§3 授權敘述改為有界說法、§4.1 G-F5 引用改指 DEC-164 §四原文）。
- 研究文件內含 Gate：`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`／`WIRING-GATE`。**RECOMMENDATION（非裁示）**：AI 推薦方案 B；是否採用待客戶裁示。

#### 二、仍待客戶裁示（未裁示，不得視為已核准）

最低 coverage 門檻；`G-F2～G-F6`；UI2 runtime 接線 Gate（`WIRING-GATE`）；Digest A3；`market.health` 0–100 範圍；外資 L3。

#### 三、狀態分欄

| 類別 | 內容 |
|---|---|
| **已完成** | A2（#1146）；B 線研究文件（待本 docs PR 合併入 main） |
| **已授權、未施工** | 無（DEC-165 授權範圍已全數產出） |
| **未授權** | UI2 runtime 接線／上線、A3、health 範圍、外資 L3、Digest v2、OneBrain、production caller |
| **NOT VERIFIED** | TWSE／TPEX／FinMind 再散布授權原文、parquet `release_date`／PIT、Streamlit Cloud、iOS／Android 真機、Playwright／viewport、真實 macro_state 端到端 |

- **有效讀法**：DEC-165 三、四中「A2 已授權、尚未完成」自本條起讀作「A2 已完成（#1146）」；授權≠接線授權的限制不變。


### DEC-167｜Issue #1144 後續：客戶裁示「同意 B」——UI2「市場資金與籌碼」先完成唯讀證據補強、不進正式 runtime 接線（2026-11-11；只追加；依客戶對話原文轉錄，非 QA PASS）

- **客戶原文（2026-11-11 對話）**：「同意 B」。方案 B＝UI2「市場資金與籌碼」先完成唯讀證據補強，不進行正式 UI runtime 接線。
- **授權範圍（僅此）**：Coverage／板塊／ETF 家族、PIT、TWSE／TPEX／FinMind 授權、G-F2～G-F6 與接線 Gate 阻塞的**唯讀研究**；研究文件＋三方案比較＋SSOT 只追加。
- **未授權（限制）**：任何程式、投資規則、資料來源、UI runtime、Schema 修改；不接線、不改 `G2F_IMPORT_ALLOWLIST`／real_feed／VM／views；不自設 coverage 百分比；A、C 方案僅未來候選，**不是施工授權**。**本裁示不是 runtime 接線授權，停在 `WIRING-GATE`（`I1144-WIRING-GATE` 仍未授權）。**
- **已完成（FACT，本批 docs-only）**：補充文件 `docs/vnext/UI2_RUNTIME_PREGATE_EVIDENCE_SUPPLEMENT_2026-11-11.md`（補強 `UI2_RUNTIME_PREGATE_RESEARCH_2026-11-11.md`，不取代）。要點：41 板塊＝窗口內標籤聯集、未觀測 3 者為單檔偶發標籤（INFERENCE：分類噪音）；15761 僅最近一次 cron 範圍；現有資料算不出個股覆蓋率；三資料集無 `release_date`；FinMind 僅 README 三句（範圍有限）。撰寫組對三份單組證據做了抽查並降級數項（見補充文件 §8）；**仍是單組，未經第二組獨立複驗**（§-2 規則 6）。
- **仍待客戶裁示**：`DG-COV`（最低 coverage，含母體口徑）、`DG-PIT`、`DG-LIC`、`DG-SCOPE`、`WIRING-GATE`。G-F2～G-F6 屬 Digest／headless 範圍，是否阻塞本區塊為 INFERENCE（不阻塞），仍待裁示。

| 類別 | 項目 |
|---|---|
| **已完成** | 補充證據文件（docs-only）；A2（#1146）與前置研究文件（DEC-166）沿用 |
| **已授權** | 唯讀證據補強與 SSOT 追加（本 DEC「同意 B」） |
| **未授權** | UI2 runtime 接線／上線、A3、health 範圍、外資 L3、Digest v2、OneBrain、production caller、方案 A／C 施工、任何 coverage 門檻值 |
| **NOT VERIFIED** | TWSE／TPEX 授權全部；FinMind 官網條款全文；OGDL 原文（僅二手線索）；來源發布日／PIT／修訂；缺日是否休市；Cloud、iOS／Android 真機、Playwright／viewport（390／1440）；真實 macro_state 端到端 |

- **有效讀法**：DEC-166 的「仍待客戶裁示」中，客戶已就方案選擇裁示「B」；其餘 Gate 不因此關閉。沉默不等於同意。


### DEC-168｜Issue #1144 後續：客戶新增指示 B8——官方網站直連不通時，參考舊 UI 的 NAS 中繼站方式查證（2026-11-11；只追加；依客戶對話原文轉錄；明確**非**網路架構變更授權，非 QA PASS）

- **客戶原文（2026-11-11 對話，B8）**：「如果連不上線，記得要用 NAS 中繼站，可以參考舊 UI 的方式。」
- **授權範圍（僅此）**：承 DEC-167「同意 B」，在 TWSE／TPEX／FinMind 條款查證遇到直連不通時，**唯讀**檢視舊 UI 既有的 NAS 中繼做法（`proxy_helper.fetch_url`／`nas_relay_fetch`／`nas_server` 的 `/proxy`），並在**已合法配置**的前提下以既有函式做唯讀 GET 官方公開條款頁。
- **未授權（限制）**：修改網路架構、新增服務、修改 Secrets、繞過安全限制；自建第二套 Proxy；修改 NAS Server、新增端點、放寬認證、新增排程；任何程式、投資規則、資料來源、UI runtime、Schema 修改。**本裁示不是 runtime 接線授權，`I1144-WIRING-GATE` 仍未授權。**
- **結果（FACT，本批 docs-only，2026-11-11）**：
  - Direct：**失敗**（沙箱出口 agent proxy 對官方網域回 CONNECT 403）。
  - 既有 Proxy（repo NAS Squid）：**未測試**——`PROXY_URL`／`NAS_PROXY_URL`／`HTTP_PROXY` 皆未設定。
  - NAS 中繼：**未測試**——`NAS_BASE_URL`／`NAS_RELAY_URL`／`NAS_API_KEY` 在本環境皆未設定（僅記 True／False，未列印任何值）。
  - 官方 GitHub raw：**成功**，但僅 FinMind README 三句。
  - 沙箱的 `HTTPS_PROXY` 是 agent proxy，**不是** NAS，未被拿來冒充。
  - 契約與安全限制摘要（`/proxy` 無主機白名單、僅 SSRF 私網封鎖；認證為 `X-API-Key` 且 NAS 端未設 key 時無認證；範例 scheme 為 HTTP、client `verify=False`）見補充文件 §9.2。
- **授權結論**：**無變動**。TWSE／TPEX／OGDL 原文仍 NOT VERIFIED，FinMind 仍僅 README 三句，DG-LIC 維持 NOT VERIFIED；補充文件 §9 未取代 §3 任何一項。
- **仍待客戶裁示**：`DG-LIC`（可選：貼條款原文／放行沙箱網域／提供已配置 NAS 的執行環境並明確授權唯讀 GET）、`DG-COV`、`DG-PIT`、`DG-SCOPE`、`WIRING-GATE`。NAS 實際是否設 API Key、是否 HTTPS、GitHub secrets 是否已設，須客戶自行確認。
- **有效讀法**：NAS 可達只代表網路可達，不代表再散布已授權，也不代表 PIT 合格；沉默不等於同意。

| 類別 | 項目 |
|---|---|
| **已完成** | B8 唯讀查證與補充文件 §9（docs-only） |
| **已授權** | 唯讀參考舊 UI NAS 中繼做法、在已配置前提下唯讀 GET 官方條款頁（本 DEC） |
| **未授權** | 網路架構／Secrets／NAS Server／端點／認證／排程變更、第二套 Proxy、UI2 runtime 接線、coverage 門檻值 |
| **NOT VERIFIED** | TWSE／TPEX 授權全部；FinMind 官網條款；OGDL 原文；NAS 實際部署設定；GitHub secrets 是否已設；PIT 發布日 |


### DEC-169｜Issue #1144 後續：客戶裁示——先收斂 Coverage 母體並補上 TWSE、TPEX、FinMind 官方條款證據（2026-11-11；只追加；依客戶對話原文轉錄；僅 docs-only 查證與 SSOT 更新；非 QA PASS）

- **客戶原文（2026-11-11 對話）**：「同意先收斂 Coverage 母體並補上 TWSE、TPEX、FinMind 官方條款證據。僅授權 docs-only 查證與 GitHub SSOT 更新；其餘 Gate 保持 HOLD。」
- **授權範圍（僅此）**：(1) Coverage 母體定義的唯讀研究與收斂；(2) TWSE／TPEX／FinMind 官方條款證據補查；(3) 以 docs-only 方式更新 GitHub SSOT（補充文件、DECISIONS、BACKLOG、HANDOFF、PROJECT_STATE，只追加）。
- **未授權（限制）**：任何程式、投資規則、資料來源、UI runtime、Schema 修改；不接線、不改 `G2F_IMPORT_ALLOWLIST`／real_feed／VM／views；**不採用新母體**、**不設任何 coverage 百分比或門檻值**；不修改 `data_cache` 任何檔（含不刪 `industry_raw.json`）、Actions、Secrets、網路架構；不新增資料來源或儲存；COV-A／B／C 僅研究候選，**不是施工授權**。**本裁示不是 runtime 接線授權，`I1144-WIRING-GATE` 仍未授權。其餘 Gate 保持 HOLD。**
- **結果摘要（FACT；本批 docs-only；詳見補充文件 §10～§12）**：
  - **Coverage 母體（§10）**：現行母體＝近 20 交易日窗口內任一天出現的標準板塊（41）；組成依研究員自訂規則為 34 官方產業名＋4 證券類別標籤＋3 偶發標籤（化學生技醫療、電子工業、未分類；窗口內合計 7 股日、全 37 日 15 股日；成因 NOT VERIFIED）。四種覆蓋中**僅「板塊標籤覆蓋」可算**，個股／交易金額／市值覆蓋全部 NOT VERIFIED（`net_amt_yi` 是三大法人淨買賣超，不是成交金額）。比較 COV-A／B／C 後，**RECOMMENDATION：暫不改母體；日後揭露合計至少 COV-A 強制揭露；若要避免偶發標籤誤導，研究候選為 COV-C「標註不剔除」；不選 COV-B**（缺 ETF 家族、無版本／適用日／授權證據、剔除即丟證據）。現有資料**沒有穩定分母**，不具備以比例設門檻的基礎；歷史列用回補當下的產業對映而非各日 PIT 對映。
  - **官方條款（§11）**：TWSE、TPEX、data.gov.tw 官方站在沙箱不可連，**零頁原文，維持 NOT VERIFIED**。FinMind 取得官方 GitHub Pages 條款原文（版本日期 2026-10-31）→ **PARTIALLY VERIFIED**：授權不含對外再散布、轉售、建置鏡像；對外公開須自行向原資料來源機關取得授權且「非 FinMind 所能授予」；Free／Backer／Sponsor 限非商業；任何方案皆禁止再散布原始資料；須標示「FinMind」。**FinMind 條款≠TWSE／TPEX 條款；Apache-2.0 只管 SDK 程式碼；OGDL 來自 SPDX 轉錄本，只 PARTIALLY。** repo 為公開，`data_cache` 追蹤 29 檔，`industry_raw.json`（875,758 位元組）含 FinMind 與 TWSE／TPEX 原始列——僅陳述事實，**是否構成再散布、是否商業、是否須標示來源，須客戶／法律專業判斷，AI 不下結論**。
  - **抽查與降級（§12）**：撰寫組抽查關鍵數字並降級數項（官方查無 4 位數碼 190→約 186～190、1188 內部分項不引用、34＋4＋3 標明規則依賴、「UI 未標示 FinMind」降為未見／NOT VERIFIED 等）；FinMind 引文與原檔一致，並對官方 GitHub 原始檔即時重抓比對。**證據仍為單組，未經第二組獨立複驗**（§-2 規則 6）。
- **仍 HOLD／待客戶裁示**：`DG-COV`（含母體口徑與覆蓋口徑）、`DG-PIT`、`DG-LIC`、`DG-SCOPE`、`I1144-WIRING-GATE`、G-F2～G-F6、`I1144-DG-A3`、`I1144-DG-HEALTH` 等全部維持；本批**未關閉任何 Gate**。
- **有效讀法**：條款存在≠特定資料集適用≠本專案已取得再散布權；網路可達（DEC-168）≠授權；`fetched_at`≠`release_date`；沉默不等於同意。

| 類別 | 項目 |
|---|---|
| **已完成** | Coverage 母體收斂研究與官方條款證據補查（補充文件 §10～§12，docs-only） |
| **已授權** | docs-only 查證與 GitHub SSOT 更新（本 DEC 客戶原文） |
| **未授權** | 採用新母體、任何 coverage 門檻值／百分比、COV-A／B／C 施工、UI2 runtime 接線／上線、A3、health 範圍、外資 L3、Digest v2、OneBrain、production caller、任何程式／資料／Actions／Secrets／網路架構／`data_cache` 變更、刪檔 |
| **仍 HOLD** | DG-COV／DG-PIT／DG-LIC／DG-SCOPE／WIRING-GATE／G-F2～G-F6 等其餘 Gate |
| **NOT VERIFIED** | TWSE／TPEX／data.gov.tw 授權原文；OGDL 原頁；FinMind 官網即時版本、方案等級、與來源機關的另行契約；3 偶發標籤個股成因；15761 組成；來源發布日／PIT／修訂；缺日是否休市；UI 是否顯示來源標示；Cloud、真機、Playwright；本批結論的第二組獨立複驗 |


### DEC-170｜Issue #1144 後續：客戶裁示——CI 環境最小修復採方案 A、失敗再評估方案 B；已由 PR #1150 完成（2026-11-11；只追加；依客戶對話原文轉錄；僅 CI 安裝環境修復，與業務／資料／Gate 決策無關；非 QA PASS）

- **客戶原文（2026-11-11 對話，正式裁示）**：「同意優先採 A，失敗再評估 B。授權專案 AI 獨立進行最小 CI workflow 安裝環境修復，另開 PR，保留全部 Browser required checks 與測試門檻，不碰 #1149 內容或業務程式。」
- **授權範圍（僅此）**：`.github/workflows/pr-check.yml` 的 `ui2-browser` job「安裝環境」之最小修復（先 A、A 失敗再評估 B）；另開 PR；保留全部 Browser required checks 與測試門檻；不碰 #1149 內容、不碰業務程式。
- **未授權（限制）**：降低或移除任何 Browser 守衛（針對 `ui2-browser` job：`continue-on-error`、`|| true`、skip、降門檻、改 required 語意）；新增 Secret；修改 `tests/`、`src/`、`shared/`、資料或 `data_cache`；修改 #1149 的內容；任何 UI2 runtime 接線、coverage 門檻、授權／PIT 結論。**本裁示是 CI 環境修復授權，不是 `I1144-WIRING-GATE` 接線授權，也不關閉任何 Gate。**

#### 一、事實（FACT，皆有 GitHub 證據）

- **故障**（依 job 日誌）：#1149 attempt 1／2（run 43038462781）的 `ui2-browser`（streamlit 1.56.0／1.59.2）在「Install Chromium」步驟（`playwright install --with-deps chromium`）因 runner 的 apt 無法下載 9 個字型套件（DNS 解析失敗）而失敗，每次約 7～10 分鐘；無 `junit.xml` → `ui2-browser-gate` 失敗；Fast、Slow 皆 PASS。根因在 CI 安裝環境，不在 #1149 內容。
- **方案 A 實證失效**（依 job 日誌；run 層級 conclusion 為 cancelled〔被後續 push 取代〕，失敗證據在 job 130609352669）：PR #1150 早期 commit 以「切換到 Ubuntu 官方來源＋有上限重試」修復；同 runner 上 `azure.archive.ubuntu.com`、`archive.ubuntu.com`、`security.ubuntu.com` 三個 host 皆 DNS 解析失敗（run 43045769006、job 130609352669），步驟快速失敗並提示升級 B。依客戶裁示「失敗再評估 B」，進入方案 B。
- **方案 B（PR #1150 最終內容，squash 合併為 main `96cb7614`）**：`ui2-browser` job 改在 `mcr.microsoft.com/playwright:v1.64.1-noble@sha256:2f05f8a734509a7b3f26a912639488ee08f58a7b292d14d62271bcff9038768f` 內執行（tag＋digest 固定；Ubuntu 24.04；Chromium 與系統依賴預裝；與 `playwright==1.64.1` 一致），`options: --ipc=host`，`defaults.run.shell: bash`；移除 pip 快取（容器無 `lsb_release`）與 `~/.cache/ms-playwright` 快取步驟；「Install Chromium」改為無 apt 驗證（`playwright install chromium`，失敗即步驟失敗）。首次 B 實測（run 43046953627）因容器無 `lsb_release` 與預設 `sh` 失敗，已修正；修正後 head `0a30fd8b` 原生 CI 五項全綠（run 43047303965）。
- **全部 Browser 守衛保留**：matrix 兩版本（1.56.0／1.59.2）、`UI2_BROWSER_LANE=required`、`pytest -m ui2_browser` 與兩個測試檔、junit 檢查（tests≥40、skipped=0）、evidence artifact、`ui2-browser-gate`；無 `continue-on-error`、無 `|| true`、無 skip、無降門檻、無新 Secret；未改 tests／production。獨立 QA（非作者）對 B diff PASS（映像 tag／digest 亦獨立向 mcr 驗證）。
- **#1149 處置**：未改其內容；僅用 GitHub「Update branch」併入新 main 使其以修好的 workflow 重跑；新 head `a60fdd84` 原生 CI 五項全綠（run 43051230191）、0 unresolved threads，已 squash 合併為 main `d8d74ccd`。

#### 二、狀態分欄（防止把授權寫成完成）

| 類別 | 內容 |
|---|---|
| **已授權且已完成** | CI 安裝環境最小修復（方案 A 嘗試→實證失效→方案 B）＝PR #1150（main `96cb7614`）；#1149 以修好的 workflow 重跑並合併（main `d8d74ccd`）。本 DEC 的 docs PR 號：#1151 |
| **未授權** | 降低／移除任何 Browser 守衛、新 Secret、改 tests／src／資料、UI2 runtime 接線／上線、A3、health 範圍、外資 L3、Digest v2、OneBrain、production caller、coverage 門檻值、採用新母體 |
| **仍 HOLD（本批未關閉任何 Gate）** | Coverage 母體新算法／最低 coverage 門檻（`DG-COV`，未裁示）、PIT 正式語意（`DG-PIT`）、資料再散布最終授權（`DG-LIC`）、UI2 `WIRING-GATE`（`I1144-WIRING-GATE`）、Digest A3／`market.health` 範圍／外資 L3（未授權）、G-F2～G-F6 |
| **NOT VERIFIED** | 本修復只證明在**當日 runner** 上可執行；GitHub-hosted runner 的 Ubuntu 來源 DNS 故障根因（GitHub 或 Canonical 端）**未查明**；Streamlit Cloud、真機、Playwright 以外的真實環境未驗；`ui2-browser-gate` 是否已設為 GitHub Branch protection 的 required check 為設定面事項，本 AI 工作階段無權限讀寫（見 `pr-check.yml` 註解），未驗 |

#### 三、維護注意（避免日後再踩）

- 容器映像升級（Playwright 版本變動）時，**image tag、sha256 digest、`playwright==` pip pin 三者須一併更新**，並重跑 `ui2-browser` 兩個 matrix 版本；不得改用 `latest`。
- 若日後 runner DNS 恢復，是否退回非容器作法屬**新的內部技術決定**；不得因此降低 Browser 守衛。

#### 四、有效讀法與下一步

- **有效讀法**：DEC-169 之後、#1149 被 CI 環境阻塞的描述（含 HANDOFF 前段「PR 待 CI／被環境阻塞」類字樣）自本條起**已過期**——CI 環境已修復（#1150）、#1149 已合併（`d8d74ccd`）。CI 環境修復**已授權且已完成**，與 Gate 決策是兩件事：它不構成任何資料授權、PIT、coverage 或接線的核准；沉默不等於同意。
- **下一步**：**等客戶就 Coverage 門檻／母體口徑（`DG-COV`）與資料授權風險（`DG-LIC`，含 `DG-PIT`、`DG-SCOPE`）裁示**；無裁示即停手（CLAUDE.md §-1）。


### DEC-171｜Issue #1144 後續：客戶裁示「同意方案 B」——先執行公開 Repository 的資料曝露、來源授權與儲存架構唯讀稽核，再決定是否修改資料保存方式（2026-11-11；只追加；依客戶對話原文轉錄；僅 docs-only 唯讀稽核；非 QA PASS）

- **客戶原文（2026-11-11 對話）**：「客戶已同意方案 B：先執行公開 Repository 的資料曝露、來源授權與儲存架構唯讀稽核，再決定是否修改資料保存方式。」
- **用語消歧**：客戶說的「方案 B」＝先做唯讀稽核；研究文件 §5 的「方案 A／B／C」是三種**儲存架構候選**，與客戶的「方案 B」用語無關。
- **授權範圍（僅此）**：(1) `data_cache/` 追蹤檔資料曝露盤點；(2) 來源授權（TWSE／TPEX／FinMind／MOPS／data.gov.tw／CBC／Yahoo）證據矩陣；(3) Git 歷史曝露與資料發布／讀取架構唯讀分析；(4) 三方案比較與分階段遷移**候選**；(5) docs-only 更新 GitHub SSOT（只追加）。
- **未授權（限制；明確不是下列任何一項的授權）**：資料遷移、刪除任何檔（含 `industry_raw.json`）、改寫 Git 歷史、改 repo 可見性（公開／私人）、修改 workflow／Actions／Secrets／網路架構、新增儲存或認證、任何程式／投資規則／資料來源／UI runtime／Schema 修改、採用新 Coverage 母體或任何門檻值。**「再決定是否修改資料保存方式」是客戶之後的另一個裁示，本 DEC 不含。本裁示不是 runtime 接線授權，`I1144-WIRING-GATE` 仍未授權。**
- **成果摘要（FACT／抽查；詳見 `docs/vnext/PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT_2026-11-11.md`）**：
  - **曝露**：repo 公開；`data_cache` 追蹤 29 檔、約 2.30 MB，**個股級 15 檔**；無 Secret、個人持股（regex 範圍內，非專業掃描器；PR-only 物件未掃），安全事件候選：無可確認事件（僅低度本機路徑觀察）。
  - **更正先前說法**：`industry_raw.json` 內 FinMind 列只保留 `date`／`industry_category`／`type` 三欄（官方列只 `code`／`endpoint`／`market`／`name` 四欄），**不是**「全部原始列」；是否仍屬條款所稱原始資料＝客戶／法律判斷。補充文件 §11 原文不改，自本條起讀作更正後意義。
  - **授權**：條款原文僅 FinMind 取得（官方 GitHub Pages，2026-10-31 版）＝PARTIALLY VERIFIED；TWSE／TPEX／MOPS／data.gov.tw／央行／Yahoo 零頁原文＝NOT VERIFIED；在 grep 範圍內（單組）找不到 repo 內授權證據；A（原文）／B（適用）／C（已取得授權）三層分開，**未下任何法律定論**。
  - **Git 歷史**：`data_cache` 歷史 1,036 個相異 blob、約 80.0 MB；存在於各分支與 1,133 個 PR head；停止追蹤不減歷史。
  - **架構**：Streamlit Cloud 讀 repo checkout 內 `data_cache`；若離開公開 repo，至少 8 個主要 L1／L3 讀取模組（主要，非窮舉）受影響；含 `data_cache` 字串的檔案 src 約 23 個、tests 約 60 個（QA 實查）；Google Sheets／NAS／`data` 分支／Artifact 皆非現成可替換的非公開資料倉。
  - **RECOMMENDATION（非裁示）**：先取得授權書面答案再決定；高優先級項目為 `industry_raw.json` 與 FinMind 市場級序列；若須降低曝露面，優先考慮可逆的方案 C 第一階段（H1 來源列不再寫入公開 repo），不動歷史；**以上僅候選，非施工授權**。
  - **抽查與降級**：撰寫組自行實跑抽查並降級數項（歷史 blob 大小口徑、僅 PR blob 數、main commit 數、路徑觀察計數等，見研究文件 §8）；**證據仍為單組，未經第二組獨立複驗**（§-2 規則 6）。
- **仍 HOLD**：`DG-COV`（Coverage 母體變更、最低 coverage）、`DG-PIT`、`DG-LIC`（最終判斷）、`DG-SCOPE`、`I1144-WIRING-GATE`、Digest A3、`market.health` 範圍、外資 L3、OneBrain runtime、UI2 接線、G-F2～G-F6；本批**未關閉任何 Gate**。
- **有效讀法**：公開≠違法；API 可取得≠可再散布；條款存在≠適用於該資料集≠本專案已取得授權；網路可達（DEC-168）≠授權；沉默不等於同意。

| 類別 | 項目 |
|---|---|
| **已完成** | 公開資料曝露、來源授權與儲存架構唯讀稽核（研究文件，docs-only）；本 docs PR 號：#1152 |
| **已授權** | 唯讀稽核與 GitHub SSOT 只追加更新（本 DEC 客戶原文） |
| **未授權** | 資料遷移、刪檔、改歷史、改 repo 可見性、改 workflow／Secrets／儲存／網路、任何程式／資料／`data_cache` 變更、採用新母體或門檻、UI2 runtime 接線／上線、A3、health 範圍、外資 L3、Digest v2、OneBrain、production caller |
| **NOT VERIFIED** | TWSE／TPEX／MOPS／data.gov.tw／央行／Yahoo 條款原文與適用性；FinMind 官網即時版本、方案等級、是否商業、與來源機關契約；Streamlit Cloud 部署設定；UI 來源標示是否顯示；raw URL 等實際可取得性；歷史 Secret 掃描窮盡性；裸 push 是否被 branch protection 擋下；本批結論的第二組獨立複驗 |


### DEC-172｜客戶 2026-11-12 五項治理裁示 D1–D5（客戶回覆「我同意」；內容轉錄自總派工 §六）；就地註記已由 PR #1153 完成（2026-11-12；只追加；非 QA PASS）

> 2026-11-12 補登（ID 取下一個未用號；落盤前 `grep -n "DEC-172\|DEC-173" docs/DECISIONS.md` 0 命中，DEC-171 為上一號）。**來源類別（依本條 D3）**：客戶直接可追溯的原文**僅為「我同意」**；D1～D5 的內容是**總派工 §六的轉錄**（撰寫組未見客戶原訊息本身，只見總管轉交之內容；若有出入以客戶原訊息為準）。故下列 D1～D5 為**轉錄摘要、非客戶逐字原文**，不得據以擴大授權。

- **決策者**：**客戶**（2026-11-12）。｜**效力日期**：2026-11-12 起。
- **D1｜廢除 `PROCESS.md` §4 Skip-PR 直推例外**：正式檔案修改一律走 PR、獨立 QA、同 head CI 與分支保護；typo／文件／版本字串亦不得 bypass。本裁示不改 branch protection 設定。
- **D2｜GitHub-first＋五檔 SSOT 取代 `PROCESS.md` §1「只讀 STATE.md」**：查核順序為即時 GitHub（main／Open PR／Issue／CI／branches）→ 現行高位階治理與正式契約 → 五檔 SSOT 相關最新有效部分 → 最新 handoff → 必要時才查歷史與原始 Decision。`STATE.md` **保留**作歷史／相容來源，不得刪除。
- **D3｜客戶裁示來源規則**：有可追溯原文者才記為客戶 Decision；Issue 轉錄／AI 摘要／AI 研究**不得擴權**，須標來源與範圍；無法確認者標 NOT VERIFIED；AI 推薦與客戶已批准分開記。DEC-155、DEC-158～171 須**逐項**依來源與合併狀態查核（**本 DEC 未執行該查核**，屬待辦）。
- **D4｜CI 與視覺 Gate**：`ui2-browser-gate` 是否為 required check **須實查**，無權限者標 NOT VERIFIED；不得降低門檻、不得自行解除 `UI_VISUAL_FIDELITY_GATE`；New UI2 視覺以最新正式五頁契約（DEC-142／DEC-146＋Top-Five Gate）為準。
- **D5｜文件重整路線**：A 修正入口 → B 建立新骨架 → 分批 C 安全遷移；「新增目錄方向已同意」≠「既有文件已准搬移」（既有文件搬移的範圍另見 DEC-173）。
- **落地**：`PROCESS.md`（§1 D2、§4 D1 取代註記）、`PROJECT_RULES.md`（第 15 節補註、第 25.1 節 R1 補註、第 25.3 節 D2～D5 索引）、`docs/vnext/NEWUI2_UI_EXECUTION_SPEC_2026-11-04.md`（檔頭 R2 註記）之就地註記**已由 PR #1153 完成**（main `e5a8ec05`）；該 PR 留下的「DEC 號待補」字樣於本 DEC 同一 PR 改為「DEC-172」。
- **未授權／不含**：改 branch protection 設定；任何 `src/`／`tests/`／workflow／資料變更；既有文件搬移（見 DEC-173）；關閉任何 Gate。
- **NOT VERIFIED**：`ui2-browser-gate` 是否已設為 required check（本工作階段無權限查 branch protection）；D1～D5 轉錄與客戶原訊息的逐字一致性；本條撰寫為單組，未經第二組獨立複驗（§-2 規則 6）。


### DEC-173｜客戶 2026-11-12 對 3C 文件重整六項正式裁示 Q1～Q6（Q1～Q4、Q6 同意〔Q6 有嚴格條件〕，Q5 暫不執行）（2026-11-12；只追加；非 QA PASS）

> 2026-11-12 補登（ID 取下一個未用號，DEC-172 為上一號）。**來源類別 D：客戶 2026-11-12 正式裁示，經總管轉交；下方 fence 逐字收錄，未改一字**（撰寫組未見客戶原訊息本身，只見總管轉交之全文；若有出入以原訊息為準）。fence 內容（不含首尾 fence 行與結尾換行）sha256＝`e99433da07494aef458896e983c5d2e097190edd93a440c55450c978c81ed504`（撰寫時計算，供比對；尚未由測試釘住）。

- **決策者**：**客戶**（2026-11-12）。｜**效力日期**：2026-11-12 起。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：

```
- Q1＝同意：HANDOFF 歷史段逐字遷入歷史分冊，主檔保留最新有效交接及路徑索引。必須先確認受影響的測試、章節字串、歷史錨點與復原能力，完成必要的測試適配。
- Q2＝同意：PROJECT_STATE 指定歷史段可分冊歸檔。但不得只留下空標題而遺失仍有效的知識；有效架構、限制、產品狀態及 Decision 關係必須留在可直接查閱的現行內容。
- Q3＝同意：BACKLOG 已結案內容可逐字歸檔，但必須由獨立 QA 逐項查證狀態，未結案、待驗證、HOLD、待客戶裁示的項目不得移出唯一現行 BACKLOG。
- Q4＝同意：CLAUDE.md 僅允許真正失效的純歷史內容歸檔；重複補註可在不改變規範效力下收斂為指向。永久規則、現行補註、客戶原文、規範位階及必要上下文一律保留。
- Q5＝暫不執行：不得拆分 CLAUDE §-1.5 判定本文，先實測 Q4 的 Token 成效與 Agent 遵循能力。
- Q6＝同意但有嚴格條件：允許將歷史內容逐字搬至 Repo 內的正式歷史分冊，保留 Git 歷史與可還原路徑；不得刪除任何客戶原文、Decision、不可變 hash 證據或尚有效的規範。新 Decision 必須精確記錄這次裁示的範圍，不得宣稱所有歷史文件皆已獲准自由搬移。
```

#### AI 整理（非客戶原文；撰寫組依上方原文與總派工整理，不得據以擴大授權）

- **範圍**：僅 `docs/HANDOFF.md`（Q1）、`docs/PROJECT_STATE.md`（Q2）、`docs/BACKLOG.md`（Q3）、`CLAUDE.md`（Q4）四檔；**依序、每份獨立 PR**。
- **逐字搬移≠刪除**：此讀法**僅於本裁示範圍內成立**；DEC-068 及其他情境不受本條影響。
- **不涵蓋**：`docs/DECISIONS.md`、`PROCESS.md`、`PROJECT_RULES.md`、`STATE.md` 或其他任何歷史文件；不得宣稱所有歷史文件皆已獲准自由搬移（Q6 原文）。
- **Q5**：暫不執行——不得拆分 `CLAUDE.md` §-1.5 判定本文；待 Q4 實測 Token 成效與 Agent 遵循能力後再議。
- **每批必要條件**：非作者獨立 QA；同 head 五項 CI 全綠；附「原段落 → 新路徑」對照表與內容等價驗證（逐字一致）；保留 Git 歷史與可還原路徑；不得刪除客戶原文、Decision、不可變 hash 證據或尚有效規範；Q1 須先確認受影響的測試、章節字串、歷史錨點與復原能力並完成測試適配；Q3 未結案／待驗證／HOLD／待客戶裁示項目不得移出現行 BACKLOG。
- **其餘 Gate**：一律維持 HOLD；本 DEC **未關閉任何 Gate**，也不是任何 runtime／資料／UI 接線授權。
- **NOT VERIFIED**：fence 與客戶原訊息的逐字一致性（撰寫組只見轉交全文）；本條 AI 整理為單組撰寫，未經第二組獨立複驗（§-2 規則 6）。


### DEC-174｜客戶 2026-11-12「方案 B」裁示：股票儀表板採 UI 與資料契約雙軌推進，每批最多三項（2026-11-12；只追加；非 QA PASS）

> 2026-11-12 補登（ID 取下一個未用號；落盤前 `grep -n "DEC-174" docs/DECISIONS.md` 0 命中，DEC-173 為上一號）。**來源類別 D：客戶 2026-11-12 正式裁示，經總管派工訊息（轉達客戶裁示）轉錄；repo 內無獨立原始對話紀錄——依 DEC-172 D3 精神標示「經派工訊息轉錄；原始對話 repo 內 NOT VERIFIED」。** 下方 fence 逐字收錄派工訊息所載該句（派工訊息中該句帶外層引號符號，與 DEC-173 fence 慣例一致〔fence 內不含包覆引號〕，故 fence 內不收引號符號，句子本文未改一字）。fence 內容（不含首尾 fence 行與結尾換行）sha256＝`e6e356f94ca00758acc6e1112f5b832a28db2868bef5f8f901982dba647f85f2`（撰寫時計算，供比對；尚未由測試釘住）。

- **決策者**：**客戶**（2026-11-12）。｜**效力日期**：2026-11-12 起。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：

```
股票儀表板採 UI 與資料契約雙軌推進。每批最多三項，沿用既有資料架構，先建立 UI 五頁資料對應稽核表與安全 UI 改善，不授權突破既有資料及接線 Gate。
```

#### AI 整理（非客戶原文；撰寫組依上方原文與總管派工訊息整理，不得據以擴大授權）

- **Batch 1 範圍**：**A1**＝五頁 UI2 × Canonical Data 對應稽核；**B1**＝UI2 安全改善，**僅限已核准契約內可重現的最小問題**——新 layout、欄位、導航、卡片、section、核心六卡、視覺契約外改動，**一律先出文字線框給客戶**（草稿先行，CLAUDE.md §-1.5.D §03-2 ①）；**C1**＝市場頁作為第一個資料契約驗證案例，含「市場資金與籌碼」（依 DEC-164）。每批最多三項。
- **不取代任何既有 DEC、資料安全守衛或停工條件。** 沿用既有 Auto-Ship 與驗收要求（總管派工訊息之 Auto-Ship 與驗收段，非客戶文件；本條不複製全文）。
- **不解除任何 HOLD／Gate**：#1119、#1124～#1126、`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、G-F2～G-F6、Digest A3、market.health 範圍、外資 L3、OneBrain runtime／provider、Digest v2、新 API／MCP／fetcher／cron／Secrets／Sheet／OAuth、資料搬移／刪除／改 Git 歷史／公開性／儲存架構、投資公式／EPS／D1～D5／廣度／Risk Cap／System Action、Old UI 修改與預設 UI 切換（⚠️ 此項為撰寫組歸納、**非某 DEC 逐字條目**；依據：DEC-165「未授權」清單禁「舊 UI；正式路由」、BACKLOG `NUI2-CUTOVER` 仍 open、DEC-097 對舊 UI 的條件——不得刪除、不得破壞 rollback、隱藏不等於通過 Old UI Removal Gate）。
- **用語消歧（「方案 B」不同義；已查證 repo 原文）**：本 DEC 的「方案 B」＝**UI 與資料契約雙軌推進**（Batch 1＝A1／B1／C1）。與下列既有用法**不同義**：
  - **DEC-165**：經查證，DEC-165 客戶原文為「同意方案 A」（授權 Digest builder A2），條文內**無**客戶「方案 B」用語；其「B 線」＝UI2 runtime 接線前置 Gate-only 工作線。與其相關的「方案 B」見 **DEC-166**（AI 推薦方案 B＝「先關 Gate、不動程式」，見 `docs/vnext/UI2_RUNTIME_PREGATE_RESEARCH_2026-11-11.md`；RECOMMENDATION，非裁示）與 **DEC-167**（客戶「同意 B」＝UI2「市場資金與籌碼」先完成唯讀證據補強、不進正式 runtime 接線）。
  - **DEC-171**：客戶「同意方案 B」＝先執行公開 Repository 的資料曝露、來源授權與儲存架構**唯讀稽核**，再決定是否修改資料保存方式（DEC-171 自身已註明與研究文件 §5 儲存架構候選 A／B／C 無關）。
  - 另有 DEC-170（CI 環境最小修復的方案 A→B）、DEC-157（市場頁順序方向 B）等亦各自使用「方案／方向 B」，彼此與本條亦不同義。**引用時一律須帶 DEC 編號，不得單說「方案 B」。**
- **另註（同名不同義）**：DEC-158 轉錄的 **D1～D5 為 Issue #1110 題號**（US10Y 口徑／VIX／利差／台灣 PMI／每日落地 cron），與 **DEC-172 治理用 D1～D5**（Skip-PR 廢除、GitHub-first、來源規則、CI 與視覺 Gate、文件重整路線）為**不同組**。
- **結果指標**：Batch 1 實際成果（稽核文件）以 PR #1165 為載體；**登錄待其合併後另行追加**，本條不寫結果。
- **NOT VERIFIED**：fence 與客戶原訊息的逐字一致性（撰寫組只見總管派工訊息轉錄；原始對話 repo 內不存在）；本條 AI 整理與消歧查證為單組撰寫，未經第二組獨立複驗（§-2 規則 6）。

#### DEC-174 結果指標（2026-11-12；只追加；**結果指標，非新裁示**、非新 DEC 編號、非授權；決策者 AI 總管〔事實更新〕；非 QA PASS）

> 本段履行上方「結果指標」條「登錄待其合併後另行追加」的自述。**為何不另開 DEC 號**：`PROJECT_RULES.md` 的登錄規則（客戶裁示→新 DEC）管的是**客戶裁示**，本段只登錄 DEC-174 Batch 1 的**執行結果**，無任何新客戶裁示；同檔 DEC-159 合併後註記亦為就地追加。**另立編號作法的理由仍成立**：DEC-166（A2 執行結果）曾另立編號，好處是查找容易、結果與裁示不混在同一條；本組取不佔號，是因本段內容全為指標、不含裁示。

- **Batch 1 載體**：PR **#1165** 已 squash 合併，main `68e56ff0`（2026-11-12 `git fetch origin main` 實取；PR 頁記錄 `merged=true`、merge 時間 2026-11-12 11:23 UTC、2 檔、+905 行、docs-only）。PR 描述自述最終 head `9ef6b81a` 同 head 五項原生 CI 全綠、兩組非作者 QA PASS；**該 CI／QA 數字本組僅轉述 PR 描述，未重查**。
- **兩份文件**（結果與證據都在這兩份，本段不重抄）：`docs/vnext/NEWUI2_FIVE_PAGE_DATA_CONTRACT_AUDIT_2026-11-12.md`（A1＋B1；結論見其 §0、§7、§11）、`docs/vnext/NEWUI2_MARKET_DATA_CONTRACT_VALIDATION_2026-11-12.md`（C1；結論見其 §0、§7、§10）。
- **B1 結論**：**未發現「契約內、可重現、不涉及新設計決策」的缺陷**（五頁稽核 §7.1），故**未開 UI 修復 PR**；Visual Gate 候選、文案漂移、守衛缺口只登記（BACKLOG 檔尾「方案 B Batch 1 收尾」段），不動 UI。
- **主要發現摘要（5 行內；單組稽核，待獨立複驗）**：
  1. 預設路徑只到 FAKE；REAL 軸帶真值的畫面欄位只有台股卡與日 K；市場位階已接線但在 UI2 獨立 session 目前恆為「⬜ 尚未載入」（五頁稽核 §0-1～3）。
  2. 「市場資金與籌碼」不在 UI2 VM；融資／板塊 L3 在 UI2 引用數為 0；外資無 L3（五頁稽核 §0-4；市場契約 §0-1／§0-2）。
  3. 口徑問題有實證：`finmind_inst` 同欄兩種 `source` 標籤；板塊外資分項與 FinMind 大盤外資同日不等；板塊 stale 4 日 vs 融資／外資 7 日（市場契約 §3、§4）。
  4. 台股卡資料日停在 2026-11-09，疑為每日資料 PR #1124～#1126 未合併（INFERENCE；cron 成功率 NOT VERIFIED）。
  5. 新候選 N-1～N-4、文案漂移、Visual Gate 候選 VG1／VG2、守衛缺口 G1／G2、CAPMAP 漂移已登記於 BACKLOG，皆非授權。
- **HOLD／Gate 全部未動**：#1119、#1124～#1126、`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、G-F2～G-F6、`I1144-DG-A3`、`I1144-DG-HEALTH`、外資 L3、OneBrain runtime／provider、Digest v2 等**維持原狀**；Batch 1 **未關閉任何 Gate、未新增任何接線授權**，也不是 runtime／資料／UI 授權。
- **仍待客戶裁示（皆為既有或新登記項；附推薦者為 AI 推薦，非客戶裁示）**：(1) 是否處置每日資料 PR #1124～#1126（推薦本批與下一批皆不處置，先做唯讀 PIT 檢查與 cron 成功率檢查）；(2) VG1／VG2（Visual Gate 候選）的文字線框（草稿先行，`CLAUDE.md` §-1.5.D §03-2 ①，客戶拍板前不得寫 UI code）；另「只接 2 項真資料」文案漂移**先確認類別**（開發面文案＝內部自決；產品畫面才需文字線框），不預設請客戶為它出線框；(3) `I1144-DATA-STORAGE-DECISION`／`I1144-LIC-THREE-QUESTIONS`（DEC-171）；(4) Q5（DEC-173：暫不執行，是否及何時重議）。
- **NOT VERIFIED**：兩份文件的第二組獨立複驗（五頁稽核 §11 推薦項 1 尚未執行）；Cloud／真機／Real 軸瀏覽器量測；授權原文；PIT。本段單組撰寫，未經第二組獨立複驗（§-2 規則 6）。



### DEC-175｜UI2 與既有資料層整理優先；Actions／死碼清理延後；跨對話持續落盤（2026-11-12）
- **決策者**：客戶。**狀態**：生效（工作優先序與交接要求；不構成任何新的資料接線／UI 施工 Gate 核准）；**非 QA PASS**（本 PR 為 Draft，待 Delta QA 與同 head 原生 CI）。
- **客戶原文（逐字，fence 內未改一字，含原文「按造」）**：

> 2026-11-12 修正（獨立 QA 項目 2，客戶授權方案 A（來源：經派工訊息轉錄；repo 與 PR 留言內無原文；與 PR #1168 留言 6824799769 的「方案 A」〔CI 最小環境修復〕是**兩件不同的授權**，不得混讀）；本 PR 新增文字內的格式更正，句子本文未改一字）：原以 blockquote 收錄，現改為 fence 並附 sha256，格式比照 DEC-173／174（fence 內不含包覆引號符號「」；兩句以換行連接）。**來源類別 D：客戶 2026-11-12 與 ChatGPT 的對話；本條由 ChatGPT 編擬並經派工訊息轉錄，撰寫組未見客戶原訊息本身，repo 內無獨立原始對話紀錄——依 DEC-172 D3 精神標示「經派工訊息轉錄；原始對話 repo 內 NOT VERIFIED」。** fence 內容（不含首尾 fence 行與結尾換行）sha256＝`af650bbb261fe697634c05b294ef56fbe972fe49cd875b4748e63039f4d14663`（撰寫時計算，供比對；尚未由測試釘住）。
> 第一句「這有空處理」的「這」指稱什麼，原文未寫、repo 內無前文；本條下文與 BACKLOG 把它解讀為 GitHub Actions Runs／Artifacts 清理（**INFERENCE**，依派工訊息脈絡，非客戶逐字；來源僅派工對話。「這有空處理」之「這」＝Actions 清理，以及「CSV 候選」，皆為 **INFERENCE，來源僅派工對話，repo 內無原文**；可作脈絡佐證但**未證實等同**的客戶留言：Issue #1119 留言 6768487486（2026-11-10，Actions 精簡延後到死碼清理批次）與 6822675191（2026-11-12，Run 歷史 30 天保留方案：唯讀盤點，未經再次明確確認禁止不可逆刪除））。

```
這有空處理，最後死碼清理的時候再來處理，先處理UI+資料庫
這邊更新專案AI問題，請將這次新增的規則加進GITHUB中，後續比較不會因為對話斷而進度不見，記得按造之前談過的資料層整理。
```

#### AI 整理（非客戶原文；撰寫組依上方原文與派工訊息整理，不得據以擴大授權）

- **範圍**：股票儀表板 `my-stock-dashboard`。延續 **DEC-174** 的 UI 與資料契約雙軌；「資料庫」先解讀為既有資料來源、資料快取、Canonical Data／L3、契約、觀測日／新鮮度、PIT、授權與覆蓋率的整理／驗證，**不**代表授權重建 DB、資料遷移、改變存放方式、新 API、cron、模型或真實接線。遇到與既有正式決策不同的設計，另請客戶裁示。
- **執行順序**：(P0) UI2 五頁與既有資料層雙軌盤點／已核准範圍內改善；(P1) 逐 Gate 做資料契約與 Real 接線決策，僅授權後實作；(P2) 真實資料、跨頁、瀏覽器與 PIT 驗收；(P3) 新 UI 完整驗收與 cutover／rollback Gate 後才處理 Old UI／死碼；GitHub Actions Runs／Artifacts 清理安排在此收尾階段，**現在停止相關施工，不執行刪除**。**「安排在收尾階段」只表示順序，不是日後刪除授權**：屆時仍須客戶逐批明示授權（Runs／Artifacts 刪除為不可逆操作，屬 `CLAUDE.md` §-1.5.D §03-2 ②）。Old UI／死碼清理仍受 **Old UI Removal Gate**（DEC-019／DEC-020／DEC-097；BACKLOG `UIM-REMOVAL-GATE`、`NUI2-CUTOVER`）與 **DEC-173 Q6**（逐字搬移≠刪除）拘束，本條不解除。
- **持續化要求**：每批最多三項。每次啟動先獨立確認 GitHub main SHA、Open／Draft PR、head/base/diff、CI、review 與治理 SSOT；進度分別落在 DECISIONS（裁示）、BACKLOG（未完成及 Gate）、PROJECT_STATE（有效架構知識）、HANDOFF（當前／下一安全點），不可只在對話或短暫 scratchpad。跨對話以 GitHub 最新事實優先，HANDOFF 不是完成證明；不建立重複交接文件。
- **資料層整理邊界**：沿用現有資料架構與核准來源、分開資料事實與 AI 分析；從 Old UI → 新 UI 五頁逐欄比對 source、source authority、as_of／publication／fetched_at、PIT、coverage、completeness、單位、staleness、missing／unavailable／not_evaluated／proxy、L3／UI2 consumer、License、測試證據、對應 Gate；不得補 0、把未驗判 safe、把板塊外資當大盤外資或把 Cron 執行時刻冒充觀測日。每項標 FACT／INFERENCE／NOT VERIFIED，缺證據維持 HOLD。
- **保留原有阻塞**：#1124～#1126 資料 PR 不合併、不關閉、不 rebase；其 PIT 與 cron 成功率先唯讀調查、再提交商業語言決策單。AI 推薦「暫不處置」**不是本 DEC 客戶對 A／B 的新裁示**。#1164、#1119 及 DEC-174、DEC-171、I1144-WIRING-GATE、DG-COV／DG-PIT／DG-LIC／DG-SCOPE 等保持原狀。舊 UI 不改、不刪；預設 UI 不切換。
- **執行治理**：本條只保存優先序與安全界線，不允許越過舊 UI First、文字線框、非作者獨立 QA、同 head CI、Review／Merge Gate；不得將「先做 UI」誤解為能直接更改 UI Layout／文案／欄位。
- **provenance**：本條由 ChatGPT 根據客戶本對話編擬；若客戶逐字性或範圍有異議，停止並修正，不升格推論為客戶裁示。
- **QA 軌跡（2026-11-12）**：已有單組非作者獨立 QA（判定 PASS with fixes〔內容層〕，單組判讀，非窮舉）；客戶裁示「方案 A」授權在本 PR 依其 8 項意見做文字修正（來源：經派工訊息轉錄；repo 與 PR 留言內無原文；與 PR #1168 留言 6824799769 的「方案 A」〔CI 最小環境修復〕是**兩件不同的授權**，不得混讀）；修正後的 **Delta QA 與同 head 原生 CI 尚未完成**，故本條仍「非 QA PASS」。
- **NOT VERIFIED**：fence 與客戶原訊息的逐字一致性（含「按造」是否為客戶原字）；「這有空處理」之「這」的指稱；DEC-164／165／170／171／172 與本條的相容性僅經關鍵字比對，未逐條精讀。


#### DEC-175 後續註記（2026-11-12；只追加；DEC-175 上文一字未改；決策者 AI 總管〔事實更新〕；**非新裁示**）

> ① **狀態更新**：上文「本 PR 為 Draft，待 Delta QA 與同 head 原生 CI」之「本 PR」＝#1168，已 squash 合併為 `169b74ed`（main，2026-11-12T14:53:59Z；GitHub MCP 取回 main 提交紀錄，FACT；合併提交訊息自述經獨立 QA ＋兩輪 Delta QA〔非作者〕PASS with fixes、同 head `ba3532ae` 五項原生 CI 全綠，**本組僅轉述提交訊息，未逐項重讀 check runs**）。② **權限釐清**：DEC-175 是否構成開工指派／施工授權，客戶已於同日答覆，見下方 **DEC-176(c)**——結論：**不是無條件施工授權，不解除任何既有 Gate；既有明確核准的工作不必重新請示**。

### DEC-176｜客戶 2026-11-12 三則續工裁示轉錄：(a) 正式整合裁示與續工派令（#1124～#1126 方案 A＝維持 HOLD）、(b) CI 修復＋#1168／#1170＋資料層 SSOT 續工、(c) DEC-175 權限釐清與下一批正式派工（2026-11-12；只追加；非 QA PASS）

> 2026-11-12 補登（ID 取下一個未用號；落盤前 `git grep -n "DEC-176" docs/DECISIONS.md` 0 命中，DEC-175 為上一號）。**來源類別 D：客戶 2026-11-12 裁示，經總管派工訊息轉錄；repo 內無原始對話紀錄——依 DEC-172 D3 精神標示「經派工訊息轉錄；原始對話 repo 內 NOT VERIFIED」，逐字一致性 NOT VERIFIED。**
> **三則的逐字程度不同，不得混讀**：(a) 本組只有派工訊息對該則的**摘要，無逐字原文 → 不做 fence，只以「AI 整理（非逐字）」記**；(b)(c) 派工訊息有**逐字節錄**，各以一個 fence 收錄（**節錄**，非該則全文；其餘內容見各則「AI 整理」，該部分非客戶逐字）。
> **fence 結構與 sha256 算法**：每則一個 fence，fence 內各段落之間以**一個空行**分隔（空行為本組為合併成單一 fence 所加，原訊息中各段是分開呈現的）；sha256 對 fence 內文（以換行連接各行，不含首尾 fence 行與結尾換行）以 UTF-8 計算，**與 DEC-173／174／175 同一算法**（本組先以同法重算三者，與其登記值逐一相符：DEC-173 `e99433da…`、DEC-174 `e6e356f9…`、DEC-175 `af650bbb…`，後才套用於本條）。(b) 第三段原文第二行行尾「跳過檢查。」與「可先使用」之間有一個空格，已原樣保留。

- **決策者**：**客戶**（2026-11-12）。｜**效力日期**：2026-11-12 起。
- **本條新增的是記錄，不是擴權**：三則都**不解除任何既有 HOLD／Gate**（`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、G-F2～G-F6、`I1144-DG-A3`、`I1144-DG-HEALTH`、外資 L3、#1119、#1164、`REORG3C-Q5-GATE`、Old UI Removal Gate、預設 UI 切換）。

#### (a) 客戶 2026-11-12「正式整合裁示與續工派令」（較早一則；**無逐字原文，不做 fence**）— AI 整理（非逐字；不得據以擴大授權）

- **裁示 1｜#1124～#1126 採方案 A（維持 HOLD）**：僅授權**唯讀** PIT＋cron 調查，並說明台股資料日為何停在 2026-11-09，結論須分 **FACT／INFERENCE／NOT VERIFIED**；**禁止**合併、關閉、rebase、修改該三 PR，或改動資料／cron／發布流程；交付**商業語言決策單**供客戶另行裁示。**此裁示不等於同意合併。** 〔補註：此「方案 A」對應 `docs/vnext/DAILY_DATA_PR_PIT_CRON_INVESTIGATION_2026-11-12.md` §5 決策單的 DATA-PR 選項 A「維持現狀：本輪不合併、不關閉、不 rebase」（FACT，已讀該文件 §5.1）；以派工訊息所述「維持 HOLD」為準。〕**與 DEC-175 的關係**：DEC-175 AI 整理曾註明「AI 推薦『暫不處置』**不是**本 DEC 客戶對 A／B 的新裁示」；本則**才是**客戶對 #1124～#1126 本輪處置的方向裁示（維持 HOLD，經派工訊息轉錄），**但仍不是合併／關閉／外部對帳的授權**，後續處置另待客戶裁示。
- **裁示 2｜下一批最多三項**：A＝第二組獨立複驗 #1165 兩份文件；B＝給非工程客戶看的 `DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC`／`I1144-WIRING-GATE` 決策單（**不解除 Gate**）；C＝#1124～#1126 PIT／cron／資料日／發布鏈唯讀調查。「🗂 資料新鮮度總覽」文字線框**僅列為下一批候選**（客戶另行指派前不啟動）；#1168 前置驗收須非作者 QA、同 head CI 後依 Auto-Ship 判斷。
- **對應結果（FACT）**：A／B／C ＝ #1169（`aa98de4c`，三份 `docs/vnext/` 文件：`NEWUI2_INDEPENDENT_REVERIFICATION_2026-11-12.md`、`DATA_WIRING_GATE_DECISION_SHEET_2026-11-12.md`、`DAILY_DATA_PR_PIT_CRON_INVESTIGATION_2026-11-12.md`，已讀存在於 main）。

#### (b) 客戶 2026-11-12「CI 修復＋#1168／#1170＋資料層 SSOT 正式整合續工」（**逐字節錄**；節錄，非全文）

- **客戶原文（逐字節錄，fence 內未改一字；具約束力；單一 fence，四段間以一個空行分隔）**：fence 內容 sha256＝`d394ca08eada1b4f6fb51b78da9a1ee9a21b2bb4396aa7e343f7c11e8c670a67`（撰寫時計算；尚未由測試釘住）。

```
① #1168：採方案 A
授權目前專案 AI 在 #1168 分支完成獨立 QA 提出的 8 項文字修正。

② CI `pip exit 127`：沿用前次已核准授權
這項授權已記錄在 PR #1168 的 GitHub 留言，不需要再次請客戶裁示。

禁止降低雙版本 browser matrix、no-skip、最低測試數量或 `ui2-browser-gate` 的標準。
不要因 Actions Re-run 權限 403 而要求客戶直接修改權限或跳過檢查。 可先使用正常 PR 更新觸發 CI；若平台權限仍阻擋必要操作，附精確證據請求最小權限裁示。

③ #1170：決策追溯對帳收尾
```

##### AI 整理（非客戶原文；不得據以擴大授權）

- **① #1168 採方案 A**：授權在 #1168 分支完成獨立 QA 的 8 項文字修正（與下列 ② 的「方案 A」＝CI 最小環境修復是**兩件不同的授權**，不得混讀，見 DEC-175 QA 軌跡同一提醒）。**對應結果（FACT）**：#1168 已合併為 `169b74ed`。
- **② CI `pip exit 127`**：沿用 PR #1168 留言（GitHub comment 6824799769）所載已核准授權，不需再請客戶裁示；**不得降低**雙版本 browser matrix、no-skip、最低測試數量或 `ui2-browser-gate`；遇 Actions Re-run 權限 403 **不得**要求客戶直接改權限或跳過檢查，可先以正常 PR 更新觸發 CI，若平台權限仍阻擋必要操作，附精確證據請求最小權限裁示。**對應結果（FACT）**：獨立 PR #1171 已合併為 `2a1623e8`（僅動 `.github/workflows/pr-check.yml` 的 `ui2-browser` 容器 job：`pip` 改 `python -m pip`；matrix、`UI2_BROWSER_LANE=required`、junit tests≥40／skipped=0、gate 全保留，已讀該檔確認）。**有效性仍 NOT VERIFIED，見下方「CI 證據」。**
- **③ #1170 決策追溯對帳收尾**：客戶原文僅標題一行，無細節；**對應結果（FACT）**：#1170 已合併為 `40d21c7f`（單檔 docs-only 對帳底稿 `docs/vnext/UI2_OPEN_ISSUES_PR_SSOT_CROSSWALK_2026-11-12.md`，非 DEC、非授權；已讀 PR 檔案清單確認）。
- **範圍／禁止（派工訊息所述，AI 整理）**：每批最多三項、寫入序列化；不改舊 UI、不解除 Gate、不動 #1164、不處置 #1124～#1126、不提前清理。
- **CI 證據（FACT／INFERENCE／NOT VERIFIED；2026-11-12，GitHub MCP 重讀 job 131230664848 日誌）**：
  - **FACT**：#1171 前，`ui2-browser` #1171 描述所列的 6 個失敗 run 皆為預建 pip **26.3**後 bare `pip` 於容器內 exit 127（*cannot execute: required file not found*）、成功 26/26 皆為預建 26.2.2（**兩數字為 #1171 描述自述，本組未全驗**）；本組另重讀 job 131230664848（run 43232345078；**不在**該 6 個 run 內，為**第 7 個失敗樣本，即 ≥7 個失敗樣本**；`python -m pip install --upgrade pip` 回報 *Requirement already satisfied: pip (26.3)*，未重裝；runner image `ubuntu-24.04` 版本 `20261111.127.1`）；#1171 修正生效後至少 2 個預建 pip 26.3 的 1.59.2 cell 成功：run 43232020099（job 131229652524，head `abc0ec38`）是 **#1171 PR 自身**的 CI（合併前）、run 43235464794（job 131241682819，#1170 分支，14:16Z 之後）才是**合併後**；兩 job 的預建 pip 版本，#1170 對帳底稿記為 26.3（轉述），本組因日誌代理限制未逐一讀到（**NOT VERIFIED**）；其後 #1172／#1173 head 的原生 CI 亦全綠，但**未逐 cell 讀 pip 版本，不得宣稱已走過失敗路徑**。
  - **更正（有意識的更正，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）**：先前 #1171 描述／BACKLOG `DEC175-CI-UI2BROWSER-EXIT127-RECUR`「失敗為 runner image 分流（image 370.1）」的**推測不成立**——失敗 job 131230664848 的 image 是 `20261111.127.1`，不是 370.1。目前只能說「預建 pip 26.3 與失敗共變」（**INFERENCE**，非因果結論）。〔#1170 對帳底稿記：#1171 後的成功樣本 image 字串為 `20261111.370.1`，與失敗樣本 `20261111.127.1` 不同，但成功樣本已改用 `python -m pip`，兩者**不可直接配對**，故 image 版本不宜當因子。〕
  - **NOT VERIFIED**：偶發故障是否完全消失，需後續樣本；`Fast checks`／`Slow tests` job 內仍有 bare `pip install`（`pr-check.yml`），在預建 pip 26.3 image 上**無樣本**，是否同樣受影響未知。

#### (c) 客戶 2026-11-12「DEC-175 權限釐清與下一批正式派工」（**逐字節錄**；節錄，非全文）

- **客戶原文（逐字節錄，fence 內未改一字；具約束力；單一 fence，兩則之間以一個空行分隔）**：fence 內容 sha256＝`f200ddfc8131d60103c4cc3bf188920f064daf5cb765c4b7b522f16421ca15cc`（撰寫時計算；尚未由測試釘住）。

```
DEC-175 是已生效的工作優先序、資料架構與交接治理決策，不是無條件的 UI／資料施工授權。

它不解除 "CLAUDE.md" §-1、文字線框 Gate、資料接線 Gate、獨立 QA、CI 或任何其他既有治理要求。

但既有明確核准的工作不必重新請示；可依已批准範圍繼續。

此次新派工僅授權下列三項安全工作，不得自行擴張。

本次三項工作完成後，停止擴張並回報。新的 UI 施工、資料接線與外部資料處置仍須客戶裁示。
```

##### AI 整理（非客戶原文；不得據以擴大授權）

- **此釐清回答的問題**：先前 HANDOFF（2026-11-12 DEC-175 段）與 #1168 合併提交訊息都寫「**DEC-175 是否構成開工指派，待客戶確認；確認前維持 `CLAUDE.md` §-1**」。**客戶答覆：DEC-175 是已生效的工作優先序、資料架構與交接治理決策，不是無條件的 UI／資料施工授權；不解除 `CLAUDE.md` §-1、文字線框 Gate、資料接線 Gate、獨立 QA、CI 或其他既有治理要求；但既有明確核准的工作不必重新請示，可依已批准範圍繼續。** 即：該待決問題**已結案**（結論＝不是開工指派）；`CLAUDE.md` §-1 仍是動工入口。
- **「既有明確核准的工作不必重新請示」的讀法邊界**：只指**已有明確核准、範圍已定**的工作可在該範圍內繼續；**不**把 DEC-175 本身變成新工作的授權，**不**擴大任何既有核准的範圍。
- **本次新派工僅三項安全工作（不得自行擴張）**：① GitHub SSOT 結果同步（本 DEC 所在的同步 PR）；② 🗂 資料新鮮度總覽**僅文字線框**三方案（對應 #1173，`76ed4b7b`；三案 A／B／C，AI 推薦 A〔展開層沿用 B〕＝RECOMMENDATION，非裁示，仍待客戶拍板）；③ 資料 PR 既有證據整理（對應 #1172，`57885e6e`；證據缺口 G-01～G-17、決策順序 DPE-1～DPE-7；不構成合併授權）。
- **停止條件**：三項完成後停止擴張並回報；**新的 UI 施工、資料接線與外部資料處置仍須客戶裁示**。

#### DEC-176 範圍外與 NOT VERIFIED

- **未授權／仍 HOLD**：本條**不是** UI 施工、資料接線、#1124～#1126 合併／關閉／rebase、外部對帳、儲存／授權決策、清理（Actions Runs／Artifacts／死碼／Old UI）、CI 設定變更的授權；各 Gate 原狀。
- **NOT VERIFIED**：(a)(b)(c) 與客戶原訊息的逐字一致性（本組只見派工訊息；(a) 連逐字都沒有）；(b) 中 ① ③ 的細節（客戶原文僅標題）；「#1171 修正有效」；#1168／#1169／#1170／#1171／#1172／#1173 的非作者 QA 與同 head CI 結果本組僅轉述各 PR 合併提交訊息與派工訊息，未逐 PR 重讀 review／check runs；#1171 最後一次僅註解字句補修由總管看 diff 確認（**未經第二組**）。本條 AI 整理單組撰寫，未經第二組獨立複驗（§-2 規則 6）。


#### DEC-174／DEC-176 後續註記：#1169 獨立複驗結論的有效讀法（2026-11-12；只追加；DEC-174／DEC-176 上文一字未改；**非新裁示**、非新 DEC 編號、非授權；決策者 AI 總管〔事實更新〕；非 QA PASS）

> **為何有本小節**：DEC-174 結果指標（上文）寫於 #1165 合併後、#1169 複驗之前；#1169（`aa98de4c`）新增 `docs/vnext/NEWUI2_INDEPENDENT_REVERIFICATION_2026-11-12.md`（219 行，下稱「複驗文件」），對 #1165 兩份文件提出 13 條勘誤（E-1～E-13）並修正 B1 結論措辭。上文數處敘述因此過期或過強。**依既有慣例，上文不改字（只追加）**；讀者遇到下表「舊位置」所列敘述時，一律以本小節的「有效讀法」為準。本小節不新增任何客戶裁示，不解除任何 Gate／HOLD，不授權 UI 施工、資料接線或任何處置。
> **行號說明**：下表「舊位置」的 `DECISIONS.md:N` 與複驗文件的行號，皆為**撰寫時 main `85c65dfc` 的行號，僅供定位**（本檔只追加時舊行號不會移動，但仍以符號／章節為準；複驗文件 §4 為表格，E-1～E-13 在其 110～122 行、R-A／R-B／R-C 在 128～130 行、§5 在 134～156 行）。
> **單組聲明**：複驗文件本身是**單組**產出（逐項事實組、紅隊組、文件組各自單組；紅隊盤點並非盲測，見其 §1「重要揭露」）。本小節對它的轉述同為單組；複驗內的事實（含紅隊以渲染輸出重現 R1～R5）**未被再次重驗**。

**(a) 逐點對照：舊位置 → 有效讀法**

| 舊位置（撰寫時 main `85c65dfc`） | 舊說法（摘要） | 有效讀法 | 複驗文件出處 |
|---|---|---|---|
| `DECISIONS.md:8405`（DEC-174 結果指標「B1 結論」） | 「未發現契約內、可重現、不涉及新設計決策的缺陷」 | 見下 (c)：**未證明違反已核准契約，但不能說「無」；R1～R5 為候選**（候選、只分類，不修） | §5、§7 第 3 點 |
| `DECISIONS.md:8409`（主要發現 3） | 「板塊 stale 4 日 vs 融資／外資 7 日」 | 外資 `finmind_inst` 現行唯一 consumer 走 **10 日曆日**（複驗文件自述，單組）（極端風險兩腿），7 日對它只被校準腳本使用；過期門檻實為**三種**（4／7／10），且 repo 另有以交易日計的 `shared/freshness_policy.py` SSOT（見 (b) E-1、E-7） | §4 E-1、E-7 |
| `DECISIONS.md:8411`（主要發現 5） | 「新候選 N-1～N-4……皆已登記」 | N-2／N-3／N-4 紅隊自報成立；**N-1 部分推翻**（漏引 `shared/freshness_policy.py`，見 (d)）。「已登記」屬實，但 N-1 的論述需補註 | §2.2 第 8 列；§4 E-7 |
| `DECISIONS.md:8414`（NOT VERIFIED） | 「第二組獨立複驗（五頁稽核 §11 推薦項 1）尚未執行」 | **已過期**：#1169 已產出一份單組複驗文件。但這**不等於** `DEC174-B1-INDEP-QA` 結案（見 (f)） | 複驗文件 §0、§7、§9 |
| `DECISIONS.md:8460`（DEC-176(a) 對應結果） | 只列 A／B／C 三份文件檔名 | 補：A（複驗文件）的結論＝核心事實獨立重現、**0 個被整體推翻**（複驗文件自述，單組），但有 13 條措辭／查法勘誤與 B1 結論修正；細節見本小節 (b)(c)(d)(e) | 複驗文件 §0、§2.2 |
| 同 `DECISIONS.md:8405`／五頁稽核 §0-9、市場文件 §0-7 | 「所有 Gate 維持 HOLD／未授權」 | 正確說法是「**未解除任何 Gate**」（見 (g)） | §4 E-8 |

**(b) E-1～E-13 與 R-A／R-B／R-C 精簡結果表**（狀態詞：修正＝措辭／事實需更正；補註＝事實不變、需補一句；部分推翻＝複驗者自己的論點僅部分成立；待判定＝需總管／客戶判定，本小節不代判）

| 編號 | 一句話有效讀法 | 狀態 |
|---|---|---|
| E-1 | 外資門檻**不是只有 4 vs 7**：現行 consumer 走 10 日曆日（複驗文件自述，單組）（`macro_cache_reader.load_extreme_risk_legs`／`EXTREME_STALE_MAX_CALENDAR_DAYS`），7 日僅校準腳本使用；「若日後接 L3 外資會落在 7 日」屬假想 | 修正 |
| E-2 | 「無交易日曆」過度絕對：repo 有交易日曆服務與休市表抓取、也有以交易日計的新鮮度 SSOT，但**這幾條 stale 判定未接到它們** | 修正 |
| E-3 | `15761` 在 `metadata.json` 的 `coverage.n_dropped_missing_price`，**不在** `per_day`（五頁稽核 X-03、§10 尾段位置不準；算術正確） | 修正 |
| E-4 | 五頁稽核 §8 Q5 的 FAKE 字串 grep 關鍵字未含「無異常」；`scenarios.py` 另有 FAKE 值「無異常（FAKE）」（帶 FAKE 標示，無實質危害） | 補註 |
| E-5 | CAPMAP「真資料＝是」其實 5 列（MK-02、MK-03、MK-04、TG-30、SY-03）；SY-03 備註「位階有真 as_of／source」與程式不符（位階畫面明寫「市場位階未提供資料日」，`source` 是規則分支識別、非資料來源）；該備註在 CAPMAP 檔，不在 #1165 兩份文件 | 修正＋補註 |
| E-6 | 五頁稽核 M-10 測試欄 `::test_twii_*` 實際在 `tests/test_ui2_real_feed.py`，與 M-09 的 `tests/test_ui2_twii_kbar.py` 不同檔 | 補註 |
| E-7 | N-1「未登記於 BACKLOG」可成立，但兩份文件都漏引 `shared/freshness_policy.py`（客戶 2026-10-14 核准的新鮮度 SSOT，已登記 `STALE_DAYS_DAILY`＝7、板塊 4、極端風險 10、領先報價 5 為顯示用日曆日規則） | 部分推翻（N-1） |
| E-8 | 「所有 Gate 維持 HOLD」與文件自己的 §6.2 矛盾（G-F1 已裁示方案 A〔DEC-161〕、融資／板塊 L3 與 A2 已授權並完成〔DEC-164、DEC-165〕）；正確說法＝**未解除任何 Gate** | 修正 |
| E-9 | 「停更＝每日資料 PR 未合併」**方向成立、力度過強**：每日資料自 11-06 起改為「資料分支＋人工合併」，不合併就不前進是設計狀態而非故障；TWII 在分支上缺 11-11 另有未解原因（NOT VERIFIED）；cron 排程與實際提交落差約 7～11 小時（原因 NOT VERIFIED）；分支上台股 11-10 那列成交量「先空後補」1 格（樣本僅 1 例）。建議把因果分 FACT／INFERENCE／NOT VERIFIED 三層寫 | 部分推翻（紅隊論證力度）＋補註 |
| E-10 | 版面／字樣列標 `READY` 易被數成「4 個 READY」誤讀為資料可用；建議改標「版面完成」或獨立欄，`READY` 只留給有真值來源的欄位 | 待判定（是否回寫由總管決定） |
| E-11 | 位階恆未載入：五頁稽核標 FACT（沙箱）、市場文件標 NOT VERIFIED；建議統一為「FACT（沙箱、讀碼）＋部署端 NOT VERIFIED」 | 補註 |
| E-12 | 兩文件檔頭自述「非作者獨立 QA 待做」、DEC-174 結果指標引 PR 描述「兩組 QA PASS」：PR 內 QA ≠ `DEC174-B1-INDEP-QA`，兩文件本身未說明這點 | 補註 |
| E-13 | 市場文件「`decision_digest` 非測試 `.py` 只被自家三檔提到」查法偏窄（實際提到者 10 個，且 `shared/strategy_class_schema.py` import 其型別）；「builder 無 production caller」是否仍成立，紅隊自報成立、文件組**未重驗** | 待判定（事實未重驗） |
| R-A | 紅隊原句「`assess_daily(11-09, today=11-12, calendar=None)` 會是 UNDETERMINED」**錯**：實測為 FRESH（落後 3 個交易日，以上界判定）；N-1「漏引 SSOT」論點不受影響 | 修正（複驗者自身） |
| R-B | 紅隊原句「main 上 `twii_ohlcv.parquet` 歷史只有 3 個提交」是**淺層複製**（71 個提交）的產物，不成立；「11-06 起改資料 PR」另有獨立證據 | 修正（複驗者自身） |
| R-C | 逐項事實組自報「不符／不精確 5 項」，清單實列 6 條 | 修正（複驗者自身） |

**(c) B1 有效讀法**：**未證明任何「違反已核准契約」的缺陷，但不能說「無」**——紅隊以渲染輸出找到 5 個可重現候選 R1～R5（紅隊自報，文件組未重做渲染）。DEC-174 結果指標「未發現契約內、可重現……缺陷」一句，讀作此義。

**(d) N-1 部分推翻（E-7）**：N-1（市場契約 §5）所指「板塊 4 日 vs 融資／外資 7 日」的**不一致本身仍成立**，但論述漏了 (1) 外資現行 consumer 走 10 日（E-1）（複驗文件自述，單組）、(2) 客戶核准的交易日 SSOT `shared/freshness_policy.py` 與顯示用日曆日規則並存（E-7）。是否統一屬客戶 Gate，**未裁示**；`DEC174-N1-STALE-THRESHOLD` 仍 open。

**(e) R1～R5 一覽（皆為**候選、只分類、不修、不授權 UI 施工**；涉及畫面結構須先文字線框＋客戶拍板；**R4 併入 VG1**；**R5 為環境依賴非缺陷**）**

| 編號 | 現象（複驗文件 §5.1 摘要） | 分類（RECOMMENDATION，非裁示） |
|---|---|---|
| R1 | 🎯「即時查一檔」未查詢時，「查詢摘要 ⬜ 尚未提供」在同一畫面出現兩次；是否違反已核准契約**不明**，去掉哪一處屬畫面結構取捨 | 視覺驗收候選；若要改須先出文字線框 |
| R2 | 真資料軸橫幅「僅台股與市場位階為真資料」宣稱位階為真資料，但位階在 UI2 恆未載入（僅開發面可見）；文案與事實矛盾，不涉新設計決策 | 文案更正候選；是否需線框由總管判定（先確認屬開發面文案或產品畫面，見 BACKLOG `DEC174-COPY-DRIFT-2ITEMS`） |
| R3 | 🗂 資料頁「是否需要行動」原因句沿用 🎯 頁文案，語意不通 | 文案更正候選 |
| R4 | 示意軸「已載入」場景的「市場目前狀態 震盪」等沒有行內示意標記（僅開發面可達） | **併入 VG1**（`DEC174-VG1-FAKE-REAL-LOOK`）處理 |
| R5 | 真資料軸讀快取用相對路徑 `Path("data_cache")`，從專案根以外目錄啟動會讀不到 | **環境依賴，不是缺陷**；兩文件的「沙箱實測」應註明可重現條件為「從專案根啟動」 |

**(f) 單組聲明（必讀）**：#1169 複驗是**單組產出**，**不等於** `DEC174-B1-INDEP-QA` 結案，也不等於 `DEC175-UI2-DATA-DUAL` 子項已結案（複驗文件檔頭第 7 行自述「是否把它們視為『非作者獨立 QA』，由總管裁定，本文不宣稱」）；複驗內事實（含紅隊渲染重現、逐項事實組統計、文件組 22 項）**未被再次重驗**。其 §8 仍列 10 項 NOT VERIFIED（部署端、真瀏覽器、上游授權、缺日是否休市、TWII 缺 11-11 原因、cron 延遲原因、全量測試未重跑、壞 JSON 旁路、資料 PR check runs 等）。

**(g) E-8 的正確說法**：**未解除任何 Gate**（不是「所有 Gate 維持 HOLD」）。已裁示／已授權項目＝G-F1 方案 A（DEC-161）、融資／板塊唯讀 L3（DEC-164）、A2 Digest builder（DEC-165）；其餘 Gate 原狀。

**(h) #1165 兩份文件仍含被修正措辭，本批不改**：撰寫時 main `85c65dfc`，至少 `NEWUI2_FIVE_PAGE_DATA_CONTRACT_AUDIT_2026-11-12.md` 的第 23 行（§0-7 新鮮度「日曆天>7、無交易日曆」）與第 25 行（§0-9「所有 Gate 維持 HOLD／未授權」）、`NEWUI2_MARKET_DATA_CONTRACT_VALIDATION_2026-11-12.md` 的第 23 行（§0-7「所有接線相關 Gate 維持 HOLD／未授權」）含上述被修正的措辭；**這是抽查到的行，不是窮舉**（該兩檔其他章節如 X-08、X-09、§4、§9 亦有相關敘述，未逐行盤點，NOT VERIFIED）。本批範圍僅 `DECISIONS`／`BACKLOG`／`HANDOFF`／`PROJECT_STATE` 四檔，**不改 `docs/vnext/` 既有檔**；以本小節為有效讀法。**是否以附註方式回寫勘誤，另待總管／客戶決定**（複驗文件 §7 第 3 點的建議是「勘誤附註、不要重寫」，屬 RECOMMENDATION，非裁示）。

**NOT VERIFIED（本小節）**：複驗文件內事實的再驗；R1～R5 的渲染重現；E-10／E-13 的處置；本小節為單組撰寫，**未經非作者獨立 QA**（§-2 規則 6），不得被引用為「已 QA PASS」。


#### 後續註記：76ed4b7b push CI 紅燈證據（FACT／INFERENCE／NOT VERIFIED）（2026-11-12；只追加；**只記錄，不修**；**非新裁示**、非新 DEC 編號、非授權；決策者 AI 總管〔事實更新〕；非 QA PASS）

> **為何有本小節**：main push `76ed4b7b`（#1173 squash）的 PR Check 為 failure，與同 head 的 PR CI 全綠不一致。本小節把兩組獨立調查（互相驗證、皆唯讀）的證據落盤，避免下一位接手者重複調查或把它誤讀為「#1173 內容有問題」。**不修測試、不重構、不放寬 CI Gate、不重跑任何 workflow**；未經客戶新授權不得改測試。
> **標籤**：FACT＝本組以 GitHub MCP 重讀（僅 run 層級欄位）或讀碼直接確認；其餘「調查組」欄位＝兩組調查員回報、**本組未重做**（見末段「本組自己驗過／沒驗過」）。**單組撰寫，未經非作者獨立 QA**（§-2 規則 6）。
> **安全聲明**：測試檔內的 secret 皆為**合成假秘密**；日誌不含任何真實 secret 值。本小節只引用片段 `5678`，**不抄出假秘密完整字串**。

**1. 事實（FACT）**

- main push `76ed4b7b`（#1173 squash）PR Check run **43253404141**：`conclusion=failure`（本組 MCP 重讀 run 層級：event=push、head_branch=main、created 2026-11-12T15:57:34Z）。只有 `Fast checks` job 失敗；日誌結尾 `9 failed, 39449 passed, 36 skipped, 226 deselected, 3 xfailed … in 1021.62s`（調查組讀日誌）。
- 9 個失敗**全在** `tests/test_d6_diagnostic_no_secret_display.py`，斷言皆為 `assert ["LONG:'5678'"] == []`（`LONG` 為測試檔內合成假秘密的常數名，片段 `5678`）：`test_baseline_page_contains_none_of_the_forbidden_strings`、`test_page_shows_only_names_state_source_never_values`、`test_env_fallback_reports_source_without_value`、`test_no_secrets_file_at_all_unset_keys_say_unset_not_parse_failure`、`test_secrets_parse_failure_shows_state_only`、`test_probe_results_are_status_and_category_only`、`test_page_probe_without_proxy_shows_direct_only`、`test_unmutated_page_passes_the_same_check`、`test_page_when_proxy_config_raises_shows_fixed_text_only`（本組 `grep` 確認 9 個測試名皆存在於該檔）。
- 同 head `8140a952` 的 `pull_request` CI run **43250372531** `success`（本組 MCP 重讀 run 層級）；更早 head `df4cc872` 的 run 43245091926 success（調查組）。**僅看 run 層級結論，未逐一展開該測試檔個別結果。**
- main push PR Check 近期結論（調查組列出；**其中標 ◆ 者本組 MCP 重讀 run 層級確認**）：`85c65dfc` success（43265246088 ◆；涵蓋同一測試檔，以 fast job 綠為據）、`76ed4b7b` failure（43253404141 ◆）、`57885e6e` cancelled（43252166395 ◆）、`40d21c7f` success（43242041455）、`169b74ed` cancelled（43241999040）、`2a1623e8` success（43235433151）、`aa98de4c` failure（43229484406 ◆）、`6241ad3b` success（43214840927）、`68e56ff0`（#1165）failure（43208678198）。
- **`aa98de4c` 與 `68e56ff0` 的失敗不是同一測試檔**：兩者 `Fast checks` 都 success，失敗的是容器 job `ui2-browser` 的 `Install dependencies`；`aa98de4c` 日誌為 `pip: cannot execute: required file not found`／exit code 127（#1171 要修的症狀）；`68e56ff0` 只確認同一步驟失敗，**退出碼 NOT VERIFIED**。（既有追蹤列：BACKLOG `DEC174-CI-UI2BROWSER-EXIT127`、`DEC175-CI-UI2BROWSER-EXIT127-RECUR`、`DEC176-CI-1171-VALIDITY`；本組先 `git grep` 確認，故**不另建重複列**。）
- **兩個 cancelled**（`57885e6e`、`169b74ed`）：`.github/workflows/pr-check.yml` 第 10～12 行設 `concurrency: group: pr-check-${{ github.ref }}` ＋ `cancel-in-progress: true`（本組讀檔確認）。**INFERENCE**：被後續 push 取消——例如 43252166395 於 15:50:40Z 建立、15:57:51Z 更新，而下一個 push run 43253404141 於 15:57:34Z 建立，時間吻合；**沒抓到取消明文**。副作用：#1172、#1168 的 push 沒有完整的 push CI。

**2. 調查組回報（機制與本機實測；本組未重做；不得當 FACT 引用——僅括號內標「本組讀碼／讀檔確認」者為本組自己驗過）**

- 該測試把測試檔內假秘密的每個 4 字元片段列為禁字（`_frags`），`screen_text` 把每個 Streamlit 元素的 `str(proto)` 納入掃描（本組讀碼確認 `screen_text` 確實納入 `str(proto)`）。元素 ID 形如 `$$ID-<32 位小寫 hex>-api_diag_run`；`streamlit.testing.v1.app_test` 模組層 `TMP_DIR=tempfile.TemporaryDirectory()` 使暫存腳本路徑每個 pytest 行程不同 → **ID 每行程隨機、行程內固定**，故同一行程內**這 9 個**測試同紅同綠（調查組讀碼推論；該檔共 33 個測試函式〔本組 `grep` 計數〕，其餘只掃部分群組或不掃整頁〔協調者複驗，本組未逐一驗〕）。
- CI fast lane 為單一 `pytest -v`：無 xdist／randomly／PYTHONHASHSEED；`pytest.ini` addopts 只有 `--strict-markers -m "not slow and not ui2_browser"`（本組讀檔確認）。
- 純 hex 4-gram：純 hex 的 4 字元片段（本組**不逐一列出**，以免還原假秘密）可能命中；另有其他禁字來源的 hex 片段也可能命中。精確機率（自動機 DP）LONG 單項約 **0.542%**；加其他禁字的 Monte Carlo（200,000 次）任一命中約 **0.63%**。
- **反事實實測**：本機整檔 3 次皆 56 passed；在**不改 repo** 的 pytest plugin 把 ID 換成含 `5678` 後，同檔 **9 failed／47 passed，且失敗的 9 個與 CI 同名**；把 ID 換成中性字元則無洩漏命中；本機 118 次 baseline 單測重跑有 1 次自然失敗，該次 ID 含 `5678`。→ 頁面輸出本身沒有輸出真正的秘密，命中位置在元素 ID。

**3. 推論與口徑（INFERENCE）**

- **INFERENCE**：`76ed4b7b` 那次 CI 行程的 ID 碰巧含 `5678`（約 0.54～0.63% 的偶發事件），故為**測試偵測器缺陷（誤報）**而非真洩漏；與 #1173 docs-only 內容無關。
- **結論口徑（必須這樣寫）**：「**高度可能為測試偵測器的非決定性缺陷（兩組獨立調查一致），但 CI 當次實例未被直接驗證 → 不記為『已證實的偶發誤報』**」。#1171 與此無關（只動 `ui2-browser` 的 pip 步驟；調查組僅看 stat 與訊息，未讀 diff 全文）。

**4. NOT VERIFIED**

CI 失敗行程實際的 ID 字串（日誌只印斷言，未印 blob，且無權限重跑）；本機為 py3.13＋streamlit 1.59.2，CI 為 py3.11，**未於同版重現**（`TMP_DIR` 機制與版本無關為讀碼推論）；repo 其他測試是否有同類「禁字 vs 隨機 ID」缺陷（**未掃**）；`68e56ff0` 的退出碼；取消明文；本節數字（機率、118 次重跑）本組未重算。

**5. RECOMMENDATION（非裁示）**

- 若客戶**另行授權**，修法方向是**掃描前正規化 `$$ID-<32hex>` 或排除 proto 的 id 欄位，且不得放寬禁字集覆蓋**；**未經新授權不改測試、不重構、不放寬 CI Gate**。
- 之後遇到類似 D6 紅燈：先看失敗片段是否出現在元素 ID 內；**rerun 通過不等於已修**。
- 追蹤：BACKLOG `DEC176-CI-D6-NOSECRET-ID-NONDETERMINISM`（P2、open、待客戶另案授權才可修測試）。

**6. 本組自己驗過／沒驗過**

- 驗過（FACT）：run 43253404141／43250372531／43265246088／43229484406／43252166395 的 run 層級 conclusion 與建立時間（GitHub MCP）；`pr-check.yml` 第 10～12 行 concurrency；`pytest.ini` addopts；9 個測試名存在；`screen_text` 納入 `str(proto)`。
- 沒驗過：日誌內容、機率計算、反事實實測、本機重跑次數、其餘 run 的結論（調查組回報）。**本小節不是 QA PASS，不得被引用為「已證實的偶發誤報」。**



### DEC-177｜客戶 2026-11-12「UI 主線恢復與預防性交接制度」裁示轉錄：🗂 資料新鮮度總覽採 A 首屏＋B 展開明細、允許最小 UI 第一版實作（不解除任何 Gate）、預防性交接制度（2026-11-12；只追加；非 QA PASS）

> 2026-11-12 補登（ID 取下一個未用號；落盤前 `git grep -n "DEC-177" docs/DECISIONS.md` 0 命中，DEC-176 為上一號）。**來源類別 D：客戶 2026-11-12 裁示，經派工訊息轉錄；repo 內無原始對話紀錄——依 DEC-172 D3 精神標示「經派工訊息轉錄；原始對話 repo 內 NOT VERIFIED」，逐字一致性 NOT VERIFIED。** 下方 fence 收錄派工訊息所附客戶訊息檔的**全文**（含標題、Model／Mode／Effort／Repository 抬頭行與各段之間的空行），未改一字；fence 內不含首尾 fence 行與結尾換行。
> **sha256 算法**：對 fence 內文（以換行連接各行，不含首尾 fence 行與結尾換行）以 UTF-8 計算，**與 DEC-173／174／175／176 同一算法**（本組先以同法重算既有 fence，與其登記值逐一相符：DEC-173 `e99433da…`、DEC-174 `e6e356f9…`、DEC-175 `af650bbb…`、DEC-176(b) `d394ca08…`、DEC-176(c) `f200ddfc…`，後才套用於本條）。

- **決策者**：**客戶**（2026-11-12）。｜**效力日期**：2026-11-12 起。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：fence 內容 sha256＝`8b059bb54d562877164ae6455c526e54097897437d13a569e1d2182ab4eae053`（撰寫時計算；尚未由測試釘住）。

```
股票儀表板｜UI 主線恢復與預防性交接制度

Model：Claude Sonnet 5.5
Mode：靜默自主巡航
Effort：High

Repository："linchen-20200325/my-stock-dashboard"

先重新確認 GitHub 最新 main、Open PR、CI／QA、DECISIONS、BACKLOG、PROJECT_STATE、HANDOFF、PROJECT_RULES、CLAUDE.md 與 PROCESS.md。

歷史基準 main："880bc17c"；#1175 已合併，合併後 push CI 五項成功。

一、本次正式 UI 方向裁示

🗂 資料新鮮度總覽採 A 首屏＋B 展開明細。

- 沿用 #1173 定義的八項固定清單及既有順序。
- 首屏同時顯示已接入、尚未接線與五態狀態計數，包含 0。
- 明細預設收合，沿用 B 的列格式。
- 第一版只使用已存在的資料日及距今天數；不新增 fetched_at／published_at 欄位。
- 保留授權、發布時點的未知／未評估說明。
- 不將未接線、未載入或未評估視為正常。
- 保留手機首屏四問與主 CTA。
- 完整資料健康度仍保留在 👤 我的既有契約位置；🗂 本批只處理新鮮度摘要，不搬移入口。
- C-16 採既有固定順序，C-17 因未選 C 不適用。
- §10 ⑥ 採 (a)，§10 ⑦ 確認為本次明確派工；不把歷史文字線框自動視為施工授權。

本次允許依核准線框進行最小 UI 第一版實作，但不解除資料接線、來源授權、PIT、Coverage、Old UI Removal 或正式切換 Gate。

若需要突破既有 "SHOWN_FOLDS" 白名單、改動 UI 契約、測試 allowlist 等尚未核准的政策，先提出精確範圍及最小修改方案，等待另行裁示，不得自行放寬。

二、本批最多三項

1. 以獨立 docs PR 記錄本次 UI 方向、授權邊界，以及已核准的預防性交接制度：每批檢查、約三批優先交接、風險提前觸發、先存檔驗證再結束舊對話。
2. 對已核准且不需突破現有 Gate 的 UI 範圍，進行最小實作；遇未授權的政策／接線需求則停在安全點，提出具體裁示單，不以 placeholder 冒充真資料。
3. 完成非作者 QA、同 head 五項原生 CI、手機首屏與缺值語意驗收，並同步所有未完成事項及安全接手點。

上述各項依序進行；不得讓多組同時寫入同一治理文件。

三、仍 HOLD

- #1124～#1126、#1164、#1119。
- DG-SCOPE／COV／PIT／LIC、I1144-WIRING-GATE。
- D6 偵測器程式修復，另批提案。
- DPE-7 維持 A（觀察），保留 11 月 19 日檢查點。
- Old UI、正式 UI 切換、資料庫重建、新 API／來源及 Actions 清理。

四、交接要求

不要每個 Agent 完成就輸出長篇進度，僅在真正阻塞、需要客戶裁示或重大里程碑時報告。

每批結束檢查交接風險；累積約三批或出現長篇 QA／CI、重大決策變動時，優先安排安全交接。

必須先把已完成、未完成、HOLD、NOT VERIFIED、待裁示問題寫入 GitHub，驗證 main／PR／CI／QA 後結束舊對話，再依最後狀態產生新對話提示語。

不承諾能準確讀取剩餘上下文 Token。

每批最多三項，未授權的新工作不得自行啟動。
```

#### AI 整理（非客戶原文；本組依上方原文與 `docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_TEXT_WIREFRAME_2026-11-12.md`〔#1173，以下簡稱「線框文件」〕逐項對應；**不得據以擴大授權**）

**(一) UI 方向裁示 ↔ 線框文件對應（本組已讀線框文件 §1.2、§2、§3、§7.2、§8、§9、§10 原文核對，FACT）**

| 客戶原文要點 | 線框文件對應項（實際內容） | 本組整理 |
|---|---|---|
| 採 A 首屏＋B 展開明細 | §7.1 推薦「A，展開層格式沿用 B」；§7.2 一鍵回覆第 1 項選項含「A首屏＋B展開層」 | 客戶選的是 §7.2 第 1 項的「A首屏＋B展開層」（AI 推薦於此**經客戶採納**；採納前它只是 RECOMMENDATION） |
| 沿用 #1173 八項固定清單及既有順序 | §1.2 候選「固定清單」8 項：台股加權指數、外資買賣超、融資餘額、M1B／M2、台灣 PMI、板塊資金流、市場位階、基本面季報（C-1）；§7.2 第 2 項 | 客戶同意 §1.2 的 8 項與其順序；線框文件自述盤點「已接入 UI2」為 2／8（台股指數、市場位階；**單組盤點，量測日 2026-11-12，會漂移**） |
| 首屏同時顯示已接入、尚未接線與五態狀態計數，包含 0 | §2.3 計數行分母規則；§3.1-6「首屏計數行狀態軸固定列出五態（含 0 項也顯示 0）」；§7.1 風險段「計數行必須永遠同時顯示接線軸與五態」；C-3 | 對應 §8.2「採 A」要求：計數行規則寫入守衛、新增「五態計數含 0 都顯示」測試 |
| 明細預設收合，沿用 B 的列格式 | §3.3 手機展開層、§4（B 的列格式）、§7.1 理由 3 | 「預設收合」的明細區＝**新增一個預設收合區**；線框文件 §1.1／§8.1-3 自述 `SHOWN_FOLDS` 現僅 3 個預設收合區、🗂 無（FACT：線框文件自述；`src/ui2/views/_page.py` 確有 `SHOWN_FOLDS` frozenset，本組未逐項核對其內容）→ **是否需要新增條目見下方 (二)，不預判** |
| 第一版只用已存在的資料日及距今天數；不新增 fetched_at／published_at | §7.2 第 3 項「只顯示資料日」；C-5（距今 n 天，用既有 `age_days`）；C-6（抓取時間欄，需 DG-PIT，**不採**）；§8.1-5 `NUI2-DATA-HEALTH-FIELD-GAPS` | 客戶選「只顯示資料日」；**C-6 不採、不新增欄位** |
| 保留授權、發布時點的未知／未評估說明 | §7.2 第 4 項「授權／發布時點說明〈要／不要〉」；C-7（發布時間「⬜ 來源未提供」）、C-8（「資料使用條件」收合區）；§3.1-5「不使用『已確認／已解除』字樣」 | 對應「要」；C-8 若為**另一個**收合區，其 `SHOWN_FOLDS` 影響併入 (二) |
| 不將未接線、未載入或未評估視為正常 | §2.1 三態對照；§2.2；§1.8-3 | 沿既有語意規則；不得以綠色／「正常」呈現未評估（§2.2 另有「不顯示『全部正常』總結句」，撰寫組補充對映） |
| 保留手機首屏四問與主 CTA | C-15（第一屏四問是否保留），其備註引「客戶 (5)-9 規定每頁有第一屏四問」；§1.1 第一屏四問現況 | 對應 C-15＝**保留**（撰寫組對映） |
| 完整資料健康度仍在 👤 我的既有契約位置；🗂 只處理新鮮度摘要，不搬移入口 | §10 ①（落點衝突）；§8.1-11（👤 入口去留）；BACKLOG `DEC176-HEALTH-ESCALATION-1` | 客戶表態＝本批不搬移、維持 Active Contract §5 的 👤 落點；**本組僅記為本批取向，`DEC176-HEALTH-ESCALATION-1` 是否結案由總管判定（本 PR 不改既有列）** |
| C-16 採既有固定順序 | §9 C-16「B 案列順序：依 §1.2 固定清單順序，或改依 `data_categories` 分類 SSOT」 | 採「依 §1.2 固定清單順序」（非 `data_categories` 順序） |
| C-17 因未選 C 不適用 | §9 C-17「C 案『未載入』放進『需要注意』或另設『尚未檢查』區」 | 不適用（未選 C），不再待裁示 |
| §10 ⑥ 採 (a) | §10 ⑥：(a) 接受 A（計數即 Level 1 摘要，逐項為第二層）／(b) 明細預設展開／(c) 改採 B | 採 (a)（撰寫組對映）：首屏計數即 Level 1 摘要，逐項狀態在預設收合明細（第二層）；客戶要求的「首屏同時顯示已接入／尚未接線／五態計數含 0」即該表所述的 (a) 前提 |
| §10 ⑦ 確認為本次明確派工 | §10 ⑦：「本草案與 HANDOFF／五頁稽核 §11『需客戶先裁示』的張力」，內容指向檔頭三點：(1) 是否占用 DEC-174「每批最多三項」名額、(2) 是否構成 DEC-175 開工指派、(3) 僅授權文字線框、不含施工 | 客戶確認這是**本次明確派工**（即本批 UI 工作屬客戶明確指派，不是 AI 自行啟動）。**本組不替客戶展開 (1)(2)(3) 各自的結論**，只記：本批的授權邊界以本 DEC 下方 (二) 為準；DEC-176(c) 對 DEC-175「不是無條件施工授權」的釐清不被本條改寫 |
| 不把歷史文字線框自動視為施工授權 | 線框文件檔頭「本文件不授權任何實作、不解除任何 Gate」 | 線框文件本身**仍不是**授權；授權來自本 DEC 的明確裁示，且僅限 (二) 範圍 |

**(二) 授權邊界（客戶原文的忠實整理）**

- **允許**：依**已核准的線框**（A 首屏＋B 展開明細，範圍如上表）進行**最小 UI 第一版實作**。
- **不解除**：資料接線（`I1144-WIRING-GATE`）、來源授權、PIT、Coverage、Old UI Removal、正式切換 Gate。第一版**不得以 placeholder 冒充真資料**（客戶「二、2」）；未接線項目以「尚未接線」如實呈現。
- **須先停手、提精確範圍與最小修改方案、等另行裁示**（不得自行放寬）：突破既有 `SHOWN_FOLDS` 白名單、改動 UI 契約、測試 allowlist（例如線框文件 §8.1-4 所述 `ENGINEERING_VOCAB` 與「接線」字樣的範圍性 allowlist，BACKLOG `NUI2-P6-VOCAB-VS-CAPABILITY-TEXT`）等**尚未核准的政策**。**是否需要新增 `SHOWN_FOLDS` 條目、是否需要 allowlist，本 DEC 不預判**（追蹤見 BACKLOG `DEC177-SHOWN-FOLDS-QUESTION`）。
- **本批最多三項**（客戶「二」）：1＝獨立 docs PR 記錄本次 UI 方向、授權邊界與預防性交接制度（本 PR）；2＝對已核准且不需突破現有 Gate 的 UI 範圍做最小實作，遇未授權的政策／接線需求則停在安全點並提具體裁示單；3＝非作者 QA、同 head 五項原生 CI、手機首屏與缺值語意驗收，並同步未完成事項與安全接手點。**依序進行；不得讓多組同時寫入同一治理文件**。

**(三) 預防性交接制度（客戶「四、交接要求」；永久規則落點＝`PROJECT_RULES.md` 檔尾新節）**

客戶要求：Agent 進度回報最小化（僅真正阻塞、需客戶裁示或重大里程碑時報告）；每批結束檢查交接風險；累積約三批或出現長篇 QA／CI、重大決策變動時優先安排安全交接；**先**把已完成、未完成、HOLD、NOT VERIFIED、待裁示問題寫入 GitHub，**驗證** main／PR／CI／QA 後才結束舊對話，再依最後狀態產生新對話提示語；不承諾能準確讀取剩餘上下文 Token；每批最多三項、未授權的新工作不得自行啟動。**「已核准」的來源**：客戶本次訊息稱其為「已核准的預防性交接制度」；本組 `git grep -n "預防性交接\|三批\|主動換對話"` 與 `git grep -n "預防性\|風險提前\|累積約"`（範圍含 PROJECT_RULES／DECISIONS／BACKLOG／CLAUDE／PROCESS／HANDOFF）**未找到更早的客戶核准紀錄**，故以**本次客戶訊息（本 DEC）為登錄依據；更早核准紀錄 NOT FOUND**（可能存在於 repo 外的對話，NOT VERIFIED，本組不編造）。與既有規則的關係見 `PROJECT_RULES.md` 新節及下方「與既有決策的關係」。

**(四) 仍 HOLD（客戶「三」原樣整理）**：#1124～#1126、#1164、#1119；`DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC`、`I1144-WIRING-GATE`；D6 偵測器程式修復（另批提案）；DPE-7 維持 A（觀察），保留 11 月 19 日檢查點；Old UI、正式 UI 切換、資料庫重建、新 API／來源及 Actions 清理。

#### 與既有決策的關係

- **DEC-174**（UI 與資料契約雙軌、每批最多三項、新 layout／欄位／導航／卡片／section 須先文字線框）：本條在其框架內——線框已由客戶拍板（A＋B），每批三項沿用。**DEC-174 的新 layout 須先線框、不突破資料 Gate 之約束不變**。
- **DEC-175**（工作優先序、資料架構與交接治理）：**不被本條擴權或改寫**；DEC-175 的「每批最多三項／跨對話持續落盤」精神由本條 (三) 具體化為永久規則。
- **DEC-176**：(c) 對 DEC-175「不是無條件施工授權」的釐清**維持有效**；本條是**新的、範圍明確的**客戶裁示（最小 UI 第一版），**不是**把 DEC-175／176 讀成開工指派。DEC-176 之 HANDOFF 待客戶裁示清單第 1 項（A／B／C）、第 2 項（C-16／C-17）、第 3 項中 §10 ⑥／⑦ 因本條而**已有裁示**（第 3 項 §10 ① 見上表，僅本批取向）；其餘項目（VG1／VG2、DPE-3／DPE-6、接線前決策單、`DEC174-B1-INDEP-QA`、D6、Q5 等）**不受影響、仍待裁示**。DPE-7：客戶已定維持 A（觀察）；11-19 為保留之檢查點，僅在客戶想讓 11-21 財報進 main 時才需另答，不屬「仍待裁示」。
- **#1173 線框文件**：維持「草案」身分；其中 A＋B 的選定範圍因本條成為已核准線框，其餘方案（C 及未選的 B 單獨呈現）不採。**線框文件原文不修改**（本批不動 `docs/vnext/` 既有檔）。
- **`PROJECT_RULES.md` 第 32 節**：本條 (三) 是第 32 節的**補充與觸發條件前移**，不是取代（詳新節）。
- **`CLAUDE.md` §-1.5.D §03-2 ①（草稿先行）、§-1、§-2**：不受影響；本條以已核准線框作為施工依據，額外的版面／欄位變更仍須先出線框。

#### DEC-177 範圍外與 NOT VERIFIED

- **PROJECT_RULES 落點說明**：本 PR 修改 `PROJECT_RULES.md` 的落點為撰寫組依該檔為永久規則 SSOT 的角色所選，客戶訊息二.1 只要求「以獨立 docs PR 記錄…預防性交接制度」，未逐字點名檔案；#1175 時期 HANDOFF 的「不改 `PROJECT_RULES.md`」為該批範圍限制，不適用本批。
- **範圍外／未授權**：本條**不是**資料接線、新欄位（`fetched_at`／`published_at`）、新 API／來源／cron／Secrets、`SHOWN_FOLDS`／UI 契約／測試 allowlist 的授權；不解除任何 Gate；不處置 #1124～#1126／#1164／#1119；不是 Actions／Old UI／死碼清理授權；不是 D6 偵測器程式修復授權。
- **NOT VERIFIED**：fence 與客戶原訊息的逐字一致性（本組只見派工訊息附檔）；預防性交接制度「更早核准紀錄」是否存在於 repo 外；線框文件 §1.2 的 8 項盤點內容（單組、會漂移）；`SHOWN_FOLDS` 實際內容與是否必須新增條目；本條 AI 整理單組撰寫，**未經第二組獨立複驗（§-2 規則 6），不得被引用為「已 QA PASS」**。


#### DEC-177 後續註記：實作前調查結果（事實更新；2026-11-13；只追加；DEC-177 上文一字未改；**非新裁示**、非新 DEC 編號、非授權；決策者 AI 總管〔事實更新〕；非 QA PASS）

> **為何有本小節**：DEC-177 要求「需突破 `SHOWN_FOLDS`／UI 契約／測試 allowlist 時，先提精確範圍與最小修改方案、等另行裁示」。本批第 2 項因此**停在安全點**：作者完成實作前調查（三組單組調查彙整＋作者自行重核檔案行號並重跑複本實驗），**未改任何 `src/`、`tests/`**，並提交裁示單 `docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_IMPLEMENTATION_DECISION_SHEET_2026-11-13.md`（Q1～Q7，含「總管推薦」與一鍵回覆範本）。**所有推薦皆 RECOMMENDATION，不是客戶裁示；沉默＝維持現狀、不寫 UI code。**

**調查結論要點（FACT＝作者讀碼／複本實測；詳見決策單 §5、§6）**

1. **完整「A 首屏＋B 收合明細」在不放寬任何既有守衛下做不出來。** 🗂 頁目前被測試規定為「無資料」頁：未列入 `tests/test_ui2_real_feed.py` `WIRED_PATHS` 的欄位不得帶 value／source／as_of。複本實驗（`origin/main` `093b323d`、17 個 `tests/test_ui2_*.py`、基準 1705 passed／3 xfailed／41 deselected）：**方案 X**（只追加 capability 骨架區塊）全綠，但畫面沒有任何新鮮度資訊；**方案 Y**（多一列帶台股資料日）19 個測試紅，皆為同一道「只有白名單欄位可帶資料」守衛。
2. **`SHOWN_FOLDS` 問題＝已確認需要（若走 B 收合明細）**：`src/ui2/views/_page.py` 的 `SHOWN_FOLDS` 現 3 項、🗂 無；線框要 3 個預設收合區。複本加 1 條＋1 個 L2 區塊：21 個測試紅（16 個為收合白名單／expander 渲染、5 個為 viewport 證據過期）。若先做 A 首屏（不含收合明細），階段 1 **預期**不需要新增（推測；實作時確認）。追蹤列 `DEC177-SHOWN-FOLDS-QUESTION` 因而由「尚未確認是否需要」更新為「**B 明細需要；A 首屏預期不需要**」（BACKLOG 以追加列註記，原列不改）。
3. **改 `src/ui2/**` 任一檔會使 4 份 viewport 證據過期**（`source_hash` 涵蓋 `src/ui2/**/*.py`＋`app_ui2.py`＋量測腳本），須在真瀏覽器重生；只改 `src/services/ui2/*` 不觸發（複本實測）。本沙箱無 Python Playwright，**能否重生 NOT VERIFIED**。
4. **其他需要裁示的政策點（決策單 Q1～Q7）**：Q1 是否允許 🗂 帶真值欄位（`WIRED_PATHS` 新增）；Q2 「尚未接線」字樣 vs 詞彙守衛 `ENGINEERING_VOCAB`（若也用在逐項明細列的 capability 欄，還需擴充 `CAPABILITY_STATUS_PREFIXES`，其只允許 `⬜ 尚未提供`；DEC-130 (a) 客戶曾列 `⬜ 尚未接線` 為資料健康度字樣；BACKLOG `NUI2-P6-VOCAB-VS-CAPABILITY-TEXT` 觸發條件是否成立待裁示）；Q3 第一屏三問與舊區塊「資料健康度尚未開放／這裡不顯示任何來源狀態與資料日」與新區塊自相矛盾（線框 C-15），且文案被 P3 證據基準釘住；Q4 狀態符號（線框 ✅◷◇⛔ vs 現行全站字樣；**總管推薦 B**，見第 5 點）；Q5 規格缺口（位階「無法判定」不在五態內、位階已載入卻無資料日）；Q6 收合明細三種做法與分階段；Q7 線框文案候選 C-2／C-4／C-7／C-8／C-9。
5. **DEC-128 (a) 旁註（不改原文）與 Q4 前提更正**：DEC-128 (a)（本檔第 6941 行）寫五態符號「僅用於 👤 我的·資料健康度面…不外溢」且「不改全站 DEC-124／Freeze §5.1 既有字樣、`text.py` 與其 guard；全站替換需客戶另裁示」，已由 DEC-130 升為正式 Active；DEC-130 (a) 客戶原文寫「資料健康度可使用」該組符號，未重述「僅 👤」。**兩者在 🗂 的適用範圍是否一致，本註記不判定**。**更正（2026-11-13，非作者 QA 後，作者以 Python 重現確認）**：本註記初稿與決策單初稿曾寫「這組符號用在 🗂 不會使測試紅、程式內無守衛」——**不正確**：`FieldVM`（`shared/ui2_contract/models.py` `__post_init__`）搭配 `shared/ui2_contract/text.py` `ALLOWED_STATUS_PREFIXES`，OK 態帶 `✅ 正常` 會 raise「OK 態不外露狀態字樣」，STALE／MISSING／UNAVAILABLE 帶 `◷ 可能過期`／`◇ 資料未備`／`⛔ 來源不可用` 全 raise「不屬於允許字樣」；符號只在純文字（如計數行的 `value_text`）才可建立並渲染（複本實測，現有自動檢查全綠）。故 Q4 選 A 的真實成本＝計數行純文字可行，但**逐項明細列的狀態欄**須新增允許字樣並放寬 OK 態規則（改共用契約與其自動檢查，與 DEC-128 (a) 限制直接衝突）；**Q4 總管推薦由 A 改為 B**（沿用現行全站字樣：`⚠ 過期 n 天`／`⬜ 資料未備`／`🔴 來源目前不可用`／`⬜ 尚未評估`，正常態無字樣；計數行純文字「資料日在規則內 n 項」；實測可行且不碰共用契約；RECOMMENDATION，非裁示）。決策單 Q4 已改寫。
6. **內部拍板項（`CLAUDE.md` §-1.5.D §03-1，不需客戶回覆，揭露於決策單 §3）**：距今天數基準沿用現行主機日 `age_days`（N-1／`I1140-TODAY-TZ` 維持 open）；FAKE 軸維持靜態、真值只走 Real 軸；新 builder 放 `data_page.py`／`real_canonical.py`；TOP_FIVE Gate 文件註記被 DEC-177 取代（docs 同步；**INFERENCE，位階解讀〔`PROJECT_RULES.md` §25：最新有效客戶 DEC 高於 `docs/vnext/` 規格文件〕；客戶若不同意請推翻**）；新增 AST 守衛禁 `published_at`／`fetched_at`；每項放寬附突變測試且不得全域放寬。

**本註記不改變任何授權**：DEC-177 的「允許最小 UI 第一版實作、不解除任何 Gate」原樣有效；在客戶回覆決策單前，作者**不寫 UI code**。**NOT VERIFIED**：部署端位階是否恆 unloaded；viewport 證據重生可行性；真瀏覽器 390／1440 實際畫面；三組調查皆單組、決策單 §6.1 為作者單組核對、未經非作者獨立 QA（§-2 規則 6），不得被引用為「已 QA PASS」。


### DEC-178｜客戶 2026-11-13「專業 AI Agent＋六項品質補強」正式執行指令轉錄：三個按需專業 Agent 入庫、六項品質補強分三批（2026-11-13；只追加；非 QA PASS）

> 2026-11-13 補登（ID 取下一個未用號；落盤前 `git grep -n "DEC-178" docs/DECISIONS.md` 0 命中，DEC-177 為上一號）。**來源類別 D：客戶 2026-11-13 裁示，經派工訊息轉錄；原始對話 repo 內 NOT VERIFIED，逐字一致性 NOT VERIFIED**（同 DEC-177 的標示方式）。下方 fence 收錄派工訊息所附客戶訊息檔的**全文**（含標題、Model／Mode／Effort／Repository 抬頭行與各段之間的空行），未改一字；fence 內不含首尾 fence 行與結尾換行。
> **sha256 算法**：對 fence 內文（以換行連接各行，不含首尾 fence 行與結尾換行）以 UTF-8 計算，**與 DEC-173～177 同一算法**（本組先以同法重算 DEC-177 的 fence，得 `8b059bb5…eae053`，與其登記值相符，後才套用於本條）。

- **決策者**：**客戶**（2026-11-13）。｜**效力日期**：2026-11-13 起。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：fence 內容 sha256＝`3479c09d9d6f924a2098ba9b11c63d2623e2205ca7b7f66333317c8aa924b473`（撰寫時計算；尚未由測試釘住）。

```
股票儀表板｜專業 AI Agent＋六項品質補強｜整合正式執行指令

Model：Claude Sonnet 5.5（不可用則選擇目前高可靠程式模型）
Mode：靜默自主巡航
Effort：High

Repository："linchen-20200325/my-stock-dashboard"

你是本專案既有的 Claude Code 專案總管。本任務是正式續工，不是重新建立架構或治理制度。

客戶已核准以下兩項工作：

1. 導入三個按需啟動的專業 AI Agent。
2. 完成六項品質補強，降低返工、資料錯誤、測試缺口及 Token 成本。

本提示語是正式執行授權，不是單純研究任務；但不能解除任何既有 Gate。

---

一、第一步：GitHub-first

先獨立核實：

- main 完整 SHA、最近 commit／diff。
- Open／Draft PR、head／base SHA、CI、QA、reviews、review threads。
- branches、worktree 與現有文件修改狀態。
- "CLAUDE.md"、"PROCESS.md"、"PROJECT_RULES.md"。
- "docs/DECISIONS.md"、"docs/BACKLOG.md"、"docs/HANDOFF.md"、"docs/PROJECT_STATE.md"。
- 相關 vNext／New UI2 規格、資料契約、既有測試及文件治理進度。

歷史參考：main "093b323d"；#1177 為 Draft，先前 head "79814147"。以上只是歷史快照，必須重新查核。

不得用 HANDOFF 的過期 SHA 取代 GitHub 即時證據。

二、先處理 #1177

若 #1177 尚未完成：

1. 優先依原授權完成其獨立 QA、最新 head 五項原生 CI、review threads 及 Merge Gate。
2. 符合原有合併規則才可合併。
3. 完成後同步 GitHub 安全接手狀態。
4. 若遇到 Q1～Q7 或未授權的 UI／契約變更，不得擅自替客戶裁示；停在安全點，明確記錄阻塞。

不得因本次新任務干擾、重做或繞過 #1177。

#1164 與 #1124～#1126 仍依既有 HOLD 管理。

#1177 合併完成且無其他真正阻塞時，直接進入以下已核准工作，不需要再次請示客戶。

---

三、第一階段：建立三個專業 Agent

採用「ChatGPT 協作總管 → Claude Code 專案總管 → 按需專業 Agent → 非作者獨立 QA」架構。

建議存放：

".claude/agents/"

Agent 1：stock-data-integrity

檔案："stock-data-integrity.md"

- Role：股票資料完整性專家。
- Trigger：資料來源、品質、PIT、as-of、freshness、缺值、Canonical／Shadow、Consumer 追溯。
- Inputs：既有資料契約、來源證據、schema、metadata、資料讀取路徑及相關測試。
- Tools：預設唯讀、最小權限。
- Forbidden：自行新增資料來源、填 0、改歷史資料、投資公式、Risk Cap、突破資料 Gate。
- Output：FACT／INFERENCE／NOT VERIFIED、資料問題、影響範圍、測試證據、修正建議。
- Escalation：來源授權、PIT、資料語意、接線 Gate 不明時回報總管。

此 Agent 只負責資料真實性，不負責股票買賣決策。

Agent 2：stock-ui-ux

檔案："stock-ui-ux.md"

- Role：New UI2 五頁與 Mobile-first 介面專家。
- Trigger：UI 設計、五頁契約、手機首屏、互動一致性、Old UI First。
- Inputs：已核准線框、五頁規格、舊 UI 功能對照、視覺證據與元件。
- Tools：預設唯讀；實作依正式授權。
- Forbidden：擅改布局、資料接線、金融語意、投資公式、OneBrain runtime、Risk Cap。
- Output：UI 差異、改善範圍、390／1440 驗收、回歸測試及風險。
- Escalation：Visual Gate、SHOWN_FOLDS、UI 契約及測試 allowlist 需要突破時停手。

此 Agent 可以改善介面，但不能把未接線或未評估顯示成正常。

Agent 3：stock-independent-qa

檔案："stock-independent-qa.md"

- Role：非作者獨立 QA。
- Trigger：PR diff、資料完整性、金融語意、CI、回歸風險、Merge Gate。
- Inputs：最新 head／base、完整 diff、驗收契約、測試及 CI 證據。
- Tools：最小唯讀／驗證權限，必要測試工具按規則使用。
- Forbidden：驗收自己修改的檔案、以舊 head CI 取代最新 head、自行放寬測試、擅自 merge。
- Output：PASS／FAIL／BLOCKED、證據、剩餘風險、未驗證事項。
- Escalation：發現契約違反、證據不足、CI 失敗、獨立性衝突時停止放行。

注意：一個 QA Agent 定義不等於只派一組 QA。仍須遵守 CLAUDE.md §-2 的多組獨立稽核與非作者驗收要求。

Agent 共通要求

每份 Markdown 定義包含 Role、Trigger、Inputs、Tools、Forbidden、Output、Escalation。

先確認 Claude Code 當前支援的 Agent frontmatter 格式及工具名稱。

- 預設按需啟動，不讓三個 Agent 每次全數載入。
- 不複製整份治理憲法。
- 不建立新的最高權威或第二份 SSOT。
- Agent 本身不取得擴權資格。
- 導入範圍只限三個角色，Investment Logic、OneBrain、GitHub Auditor 留待第二批候選，不建立。
- 設計最小任務路由規則，避免 Data／UI／QA 職責重疊。

三份 Agent 作為第一個獨立批次，遵守最多三項、寫入序列化、獨立 QA 與同 head CI。

---

四、第二階段：六項品質補強

已完成的能力直接 REUSE，不要重建。以現有 GitHub 文件、測試及程式為 SSOT。

Batch 1：需求與資料契約（最多三項）

① 現有覆蓋與真正缺口稽核

逐項盤點六項補強是否已有對應機制。輸出 REUSE／GAP／BLOCKED／NOT VERIFIED 及證據。

② Definition of Ready／Definition of Done

在既有機制最小補強：

- 已核准需求／規格 ID。
- 影響範圍與資料依賴。
- 不可變更事項及必要 Gate。
- 可驗證的驗收案例。
- Preview 完成與 Production 完成的差別。

沿用 Old UI First，不建立第二套 UI 規格。

③ New UI2 五頁資料／功能／驗收矩陣

對關鍵 Dataset 查核：

source、schema、unit、currency、as_of、fetched_at、PIT、freshness、missing reason、Canonical／Shadow、Consumer、授權狀態。

缺少的欄位標明 NOT VERIFIED 或 NOT AVAILABLE，不虛構。

已有資料契約時連結既有 SSOT。

Batch 2：測試、返工與 Production（最多三項）

④ E2E／Golden／Mutation Tests

先盤點現有測試，只補真正缺少的高風險路徑：

資料來源 → 正規化 → 選股／決策 → Digest → UI／LINE。

使用固定 fixture、Golden Tests、Mutation Tests。

不得放寬 PIT、Risk Cap、資料完整性或決策門檻。未正式接線的路徑只驗證允許的契約或離線 fixture，不假稱正式 E2E 通過。

⑤ 最小 PR Impact Check

沿用既有 PR／QA 流程，確認：

- 改了什麼？
- 影響哪些 Producer／Consumer？
- 哪些測試應重跑？
- 哪些契約不可變更？
- 哪些正式文件引用需同步？

不建立冗長重複報告。

⑥ Production 健康度

五軸分開驗證：

1. CI 是否通過。
2. 資料是否更新。
3. 資料是否有效。
4. 正式 UI 是否真正接線。
5. 投資決策與通知是否可用。

缺少正式部署證據即標 NOT VERIFIED。

Batch 3：Agent 效率與交接（最多三項）

⑦ Agent 路由整合

使用已建立的三個 Agent，驗證任務能自動選擇適合專家，且 QA 保持非作者獨立。

不另建第二套 Agent 架構。

⑧ Token 與返工基準

建立可重現的量測：

- 單件正式驗收完成工作的 Token。
- Agent 啟動與文件讀取成本。
- PR 返工次數。
- QA 修正輪次。
- 重複讀取及無效探索次數。

必須區分真實量測、估算與 NOT VERIFIED。

禁止用 bytes 冒充 Token。

⑨ 零記憶接手測試

以不依賴舊對話的 Agent 測試：

- 是否找到最新 main 與有效治理。
- 是否正確辨識唯一 NEXT。
- 是否知道 HOLD 與資料 Gate。
- 是否正確選用專業 Agent。
- 是否避免重做已完成工作。

完成後按既有 GitHub 交接制度同步。

---

五、正式治理與停手邊界

以下一律維持：

- 不修改投資公式、Risk Cap、System Action。
- 不新增未授權 API、資料來源、cron 或 Secrets。
- 不突破 OneBrain 或 New UI2 資料接線 Gate。
- 不擅改 UI 布局、SHOWN_FOLDS、UI 契約與測試 allowlist。
- 不把 missing 填 0。
- unavailable ≠ neutral。
- not evaluated ≠ safe。
- FAKE Preview ≠ 正式接線。
- 不擅自合併、關閉或 rebase #1124～#1126。
- 不處置 HOLD 中的 #1164、#1119。
- 不清理不明 worktree。
- 不重建資料庫或修改歷史投資資料。
- 不降低 CI／QA／Merge Gate。

若出現真正需客戶裁示的問題，提出 A／B／C 三方案比較（正確性、風險、速度、Token）、推薦方案、最小變更範圍後停手。

其餘已授權技術事項自行依序執行，不反覆請示。

六、PR、QA、CI 與永久交接

每批遵守：

1. GitHub-first、確認基準與分支。
2. 每批最多三項。
3. 一次只寫一個模組／文件，避免競爭寫入。
4. 非作者多組獨立 QA。
5. 同最新 head 五項原生 CI success。
6. Review threads 與 Merge Gate 核實。
7. 合格才 merge。
8. 同步 GitHub 留證後才進下一批。

使用既有權威文件：

- BACKLOG：工作狀態與下一步。
- DECISIONS：只登記真正正式裁示。
- HANDOFF：最新接手點、唯一 NEXT、HOLD／NOT VERIFIED。
- PROJECT_STATE：依現行制度同步專案狀態。
- 既有治理與測試證據文件：記錄驗收，不建立第二套 SSOT。

不得把全部歷史日誌複製到 HANDOFF。

七、執行模式

維持靜默自主巡航。

不逐步輸出：

- Agent 啟動。
- 等待 QA。
- 等待 CI。
- commit／push 中。
- 準備下一批。
- 無需客戶決策的進度訊息。

只在真正阻塞、客戶 Decision Gate、重大里程碑或整批完成時回報。

每批完成先檢查對話風險及 GitHub 存檔。累積約三批或發生重大決策、長篇 CI／QA 時，依 PROJECT_RULES 第 33 節主動安排安全交接。

如需更換對話，先完成 GitHub 存檔、QA／CI 核實，再提供結束對話與新對話接手提示語；不得憑記憶宣稱完成。

八、最終完成標準

三個專業 Agent 已正式入庫，且路由、權限與非作者 QA 符合治理。

六項品質補強各有：

- 實際交付與驗收證據；或
- 既有能力可重用的證據；或
- 明確 BLOCKED／NOT VERIFIED／未授權邊界。

最後提供：

- 最新 main SHA。
- 已合併 PR 與同 head CI／QA。
- 三個 Agent 驗證結果。
- 六項補強狀態。
- Token／返工基準。
- 剩餘 HOLD 與風險。
- 唯一 NEXT。
- 是否需要客戶回覆。

現在開始 GitHub-first。先完成 #1177；符合條件後，自動接續上述已核准工作。不重複規劃、不另求同一授權、不突破任何 Gate。
```

#### AI 整理（非客戶原文；本組依上方原文逐項對應；**不得據以擴大授權**）

**(一) 授權範圍**

| 客戶原文要點 | 本組整理 |
|---|---|
| 一、GitHub-first；二、先處理 #1177 | 前置工作。#1177 已於 `63da9515` 合併（派工訊息自述；本組 `git fetch origin main` 實查 main＝`63da9515c2f35549aa943a2728e287168632cdb0`，FACT）。#1164、#1124～#1126、#1119 仍 HOLD |
| 三、第一階段：建立三個專業 Agent | **本批（`DEC178-AGENTS-BATCH-A`）**：`.claude/agents/stock-data-integrity.md`、`stock-ui-ux.md`、`stock-independent-qa.md` 入庫；最小任務路由規則落 `PROJECT_RULES.md` 第 34 節；結構守衛 `tests/test_agent_definitions_guard.py`。Investment Logic、OneBrain、GitHub Auditor 僅為第二批候選，**不建立**（`DEC178-AGENT-SECOND-CANDIDATES`）。「一個 QA Agent 定義不等於只派一組 QA」＝仍遵守 `CLAUDE.md` §-2 規則 4。**UI Agent 定義做成硬性無寫入工具＝撰寫組對客戶「預設唯讀；實作依正式授權」的解讀，比客戶字面更保守；客戶若要 UI Agent 可在授權下直接實作，另行裁示**（DEC-177 Q1～Q7 回覆前不寫 UI code） |
| 四、第二階段：六項品質補強，分三批、每批最多三項 | Batch 1（`DEC178-QUALITY-BATCH-1`）＝①現有覆蓋與真正缺口稽核、②Definition of Ready／Definition of Done、③New UI2 五頁資料／功能／驗收矩陣；Batch 2（`DEC178-QUALITY-BATCH-2`）＝④E2E／Golden／Mutation Tests、⑤最小 PR Impact Check、⑥Production 健康度五軸；Batch 3（`DEC178-QUALITY-BATCH-3`）＝⑦Agent 路由整合、⑧Token 與返工基準、⑨零記憶接手測試。已完成的能力 REUSE，不重建；以現有 GitHub 文件、測試及程式為 SSOT |
| 五、正式治理與停手邊界 | 全部維持（見下方 (三)）。出現真正需客戶裁示的問題：提出 A／B／C 三方案比較（正確性、風險、速度、Token）、推薦方案、最小變更範圍後停手 |
| 六、PR、QA、CI 與永久交接 | 每批：GitHub-first、最多三項、一次只寫一個模組／文件、非作者多組獨立 QA、同最新 head 五項原生 CI success、review threads 與 Merge Gate 核實、合格才 merge、同步 GitHub 後才進下一批。權威文件分工沿第 15 節（BACKLOG／DECISIONS／HANDOFF／PROJECT_STATE），不另立 SSOT |
| 七、執行模式 | 靜默自主巡航；每批結束檢查交接風險（第 33 節） |

**(二) 順序（客戶原文的忠實整理）**：#1177 → 三個 Agent（第一階段，獨立批次）→ Quality Batch 1 → Batch 2 → Batch 3；每批合併並於 GitHub 留證後才進下一批。

**(三) 本條不是授權突破任何 Gate**：不修改投資公式、Risk Cap、System Action；不新增未授權 API、資料來源、cron 或 Secrets；不突破 OneBrain 或 New UI2 資料接線 Gate；不擅改 UI 布局、`SHOWN_FOLDS`、UI 契約與測試 allowlist；不把 missing 填 0（unavailable ≠ neutral、not evaluated ≠ safe、FAKE Preview ≠ 正式接線）；不擅自合併、關閉或 rebase #1124～#1126；不處置 HOLD 中的 #1164、#1119；不清理不明 worktree；不重建資料庫或修改歷史投資資料；不降低 CI／QA／Merge Gate。DEC-177 的 🗂 資料新鮮度總覽 Q1～Q7 裁示單**不受影響、仍待客戶回覆**（本條未回答其中任何一題）。

#### 與既有決策的關係

- **DEC-174**（UI 與資料契約雙軌、每批最多三項）、**DEC-175**（工作優先序與交接治理）、**DEC-176**、**DEC-177**（含預防性交接制度、🗂 實作停在安全點）：全部維持，本條不改寫、不擴權。
- **DEC-173 Q5 / `REORG3C-Q5-GATE`**：Q5＝暫不執行，前置為「先實測 Token 成效與 Agent 遵循能力」。本條⑧（Token 與返工基準）是該前置證據的候選來源，但**不構成 Q5 重議**；不可用單次樣本或 bytes 冒充 Token。
- **`PROJECT_RULES.md` 第 31 節（ChatGPT×Claude 分工）／第 31.2 節／第 33 節／新增第 34 節**：第 34 節為路由索引，與上列並存，互不取代。
- **`CLAUDE.md` §-2（每次任務都派工、多組獨立稽核、不得自己驗收自己）、§-1、§-1.5**：不受影響；「按需」只決定挑哪個 Agent，**不改變每次任務都派工**。

#### DEC-178 範圍外與 NOT VERIFIED

- **範圍外**：本條不是 Quality Batch 1～3 的內容授權以外的任何施工授權；不修改 `.claude/settings*`、`CLAUDE.md`、`PROCESS.md`、`src/`、`scripts/`、`.github/`、資料；不授權建立第二批候選 Agent。
- **更早核准紀錄**：本組 `git grep -n -i "專業 AI Agent\|專業 Agent\|GitHub Auditor\|\.claude/agents"` 於本批前未命中任何更早紀錄（僅限 repo 內搜尋）→ 更早客戶紀錄 **NOT FOUND（repo 外是否存在 NOT VERIFIED）**，不編造。
- **NOT VERIFIED**：fence 與客戶原訊息的逐字一致性；三個 Agent 在 Claude Code 的實際載入與路由效果（新對話 `/agents`、`/doctor` 實測，BACKLOG `DEC178-AGENT-LOAD-VERIFY`）；Bash 唯讀為指示性約束、settings 層是否強制（`DEC178-AGENT-BASH-READONLY-ENFORCEMENT`，是否需要由客戶另裁示）；Agent frontmatter 格式：撰寫組依派工訊息轉述的官方文件，其後 2026-11-13 QA-A 已以官方 sub-agents 文件核對（frontmatter 欄位、tools／disallowedTools 語法、MCP 命名、未知欄位被靜默忽略；單組；回傳被截斷尾段 NOT VERIFIED）；本條 AI 整理單組撰寫，**未經第二組獨立複驗（`CLAUDE.md` §-2 規則 6），不得被引用為「已 QA PASS」**。

### DEC-179｜客戶 2026-11-13「資料優先正式裁示與安全執行」轉錄：整體策略方案 A（資料優先）、DPE-3＝D（先確認來源條款）、DPE-6＝B（客戶貼 Cloud 設定）、#1124～#1126 維持 HOLD、UI Q1～Q7 與 P3 候選暫不施工（2026-11-13；只追加；非 QA PASS）

> 2026-11-13 補登（ID 取下一個未用號；落盤前 `git grep -n "DEC-179" docs/` 0 命中，DEC-178 為上一號）。**來源類別 D：客戶 2026-11-13 裁示，經派工訊息轉錄；原始對話 repo 內 NOT VERIFIED，逐字一致性 NOT VERIFIED**（同 DEC-177、DEC-178 的標示方式）。下方 fence 收錄派工訊息所附客戶訊息檔的**全文**（含標題、Model／Mode／Effort／Repository 抬頭行與各段之間的空行），未改一字；fence 內不含首尾 fence 行與結尾換行。
> **特別注意（來源鏈）**：客戶訊息內的「客戶已明確回覆『聽你的建議』」是**訊息對客戶回覆的轉述**——客戶那句原始回覆**不在 repo 內**，本條無從逐字收錄；fence 收錄的是訊息本身（含該轉述），**不是**客戶原話。
> **sha256 算法**：對 fence 內文（以換行連接各行，不含首尾 fence 行與結尾換行）以 UTF-8 計算，**與 DEC-173～178 同一算法**（本組先以同法重算 DEC-178 的 fence，得 `3479c09d…a924b473`，與其登記值相符；DEC-177 得 `8b059bb5…eae053`，亦相符，後才套用於本條）。

- **決策者**：**客戶**（2026-11-13，經上述轉述）。｜**效力日期**：2026-11-13 起。
- **客戶原文（逐字，fence 內未改一字；具約束力；但見上方來源鏈提醒）**：fence 內容 sha256＝`beb5704422011826e97464b6c761a2158cc0ab89b21adbcec9be36e02e6951e6`（撰寫時計算；尚未由測試釘住）。

```
股票儀表板｜資料優先正式裁示與安全執行
Model：Claude Sonnet 5.5
Mode：靜默自主巡航（Silent Autonomous Cruise）
Effort：High
Repository：`linchen-20200325/my-stock-dashboard`
你是既有股票儀表板專案總管。
一、客戶正式裁示
客戶已明確回覆「聽你的建議」，正式接受股票儀表板總管提出的資料優先方案 A。
本次正式裁示如下：

1. 整體策略：方案 A，資料優先。
2. DPE-3＝D：先確認外部對帳涉及的資料來源使用條款，確認後才重新考慮是否授權小範圍唯讀對帳。
3. DPE-6＝B：確認 Streamlit Cloud 實際追蹤的 Repository、Branch、Main file path 與部署觸發方式。
4. #1124～#1126 維持 HOLD。
5. DPE-7 維持先前已核准的 A（觀察），保留 2026-11-19 檢查點。
6. 🗂 資料新鮮度總覽 Q1～Q7 暫不裁示，不執行 UI 施工。
7. DEC178-QB3-* 六項 P3 改善候選暫不施工。

注意：本次核准的是 DPE-3 的 D 與 DPE-6 的 B，不是 DPE-3 的 B，也不是 UI 裁示單的 Q1＝A。不得混淆方案代號。
二、GitHub-first
在任何修改前，獨立核實：

* main 完整 SHA。
* Open／Draft PR、head／base。
* 最新 CI／QA／review threads。
* 既有正式決策及取代鏈。
* 工作樹與未推送 commit。

歷史基準：

* main：`df844b900520533f2e69d6edffe117478dc57547`
* #1186 main push CI run `43413653601`：五項 success（總管已獨立核實）。
* Open PR：#1164、#1124～#1126，全部 HOLD。

以最新 GitHub 實況為準，不以聊天摘要代替驗證。
三、讀取正式文件
依序讀取：

1. `CLAUDE.md`
2. `PROCESS.md`
3. `PROJECT_RULES.md`
4. `docs/DECISIONS.md`（DEC-176、DEC-177、DEC-178）
5. `docs/BACKLOG.md`
6. `docs/HANDOFF.md` 檔尾「Quality Batch 3 完成後最新接手點」
7. `docs/PROJECT_STATE.md` 最新段落
8. `docs/vnext/DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md`
9. `docs/vnext/PRODUCTION_HEALTH_FIVE_AXIS_SNAPSHOT_2026-11-13.md`

不得重新研究已完成的 Quality Batch 1～3。
四、本次核准工作
工作 1：正式登錄客戶裁示
沿用現行正式決策與交接制度。
在 `docs/DECISIONS.md` 登錄：

* 客戶核准資料優先方向 A。
* DPE-3＝D。
* DPE-6＝B。
* DPE-7 維持 A。
* 資料 PR 仍 HOLD。
* UI Q1～Q7 與 P3 候選仍未授權。

同步既有 BACKLOG、HANDOFF、PROJECT_STATE。
不得建立第二份 SSOT。
工作 2：DPE-3 條款確認準備
僅允許既有 GitHub／repo 文件的唯讀檢查。
整理：

* 需要外部對帳的資料來源。
* 現有授權證據。
* 使用條款是否已被正式核實。
* 哪些資料來源尚需客戶或法務確認。
* 若後續只查兩個最大疑點，需要什麼授權。

禁止：

* 執行外部資料對帳。
* 新增外部 API／MCP。
* 自行登入第三方服務。
* 抓取或儲存外部數據。
* 變更原始資料或 `data_cache`。
* 宣稱 `DG-LIC` 已解除。

DPE-3＝D 只是條款確認前置決定，不授權後續 B／C 的對帳施工。
如尚缺客戶或法務確認，標 BLOCKED／NOT VERIFIED。
工作 3：DPE-6 Cloud 設定確認
客戶選擇 B。
需要確認：

* Repository。
* Branch。
* Main file path。
* 部署觸發方式。

先核對現有 GitHub 是否已有可信、未過期的證據。
若資料不完整，只向客戶提出最小必要資訊需求。
禁止要求或顯示：

* Secrets。
* API Keys。
* Access Tokens。
* 密碼。
* 私密憑證。

不得自行修改 Streamlit Cloud 設定、部署分支、正式入口或環境變數。
沒有實際 Cloud 設定證據，不得宣稱部署正在追蹤 main。
五、仍然禁止

* Merge／Close／Rebase #1124～#1126。
* 處置 #1164。
* 清理 #1119 Actions。
* 修改 PIT、Canonical／Shadow 或資料來源契約。
* 修改投資公式、Risk Cap、System Action。
* 修改 OneBrain 正式接線。
* 修改 Old UI、正式 UI 切換。
* 改動 SHOWN_FOLDS 或測試 allowlist。
* 新增 API、cron、Secrets。
* 修改 `.claude/settings*`。
* 修改或刪除不明 worktree。
* 施工六項 DEC178-QB3-* P3 候選。

資料層與 AI 分析層維持分離。
missing 不填 0；unavailable ≠ neutral；not evaluated ≠ safe。
CI success 不代表資料已更新，更不代表 Production 已有效。
六、QA／CI／Merge Gate
本次預期僅需要最小文件決策同步。
如需修改 GitHub：

1. 使用獨立 branch／PR。
2. 寫入序列化。
3. 最多三項工作。
4. 非作者多組獨立 QA。
5. 同最新 head 五項原生 CI success。
6. Review threads 與 Merge Gate 核實。
7. 符合既有合併授權才 merge。
8. GitHub 留證後重新驗證 main。

不得直接推 main。
不得為了本次裁示順手修其他缺口。
七、最終回報
只回報：

1. 最新 main SHA。
2. 本次裁示是否正式入庫。
3. PR／QA／CI 結果。
4. DPE-3 條款確認缺口。
5. DPE-6 尚缺哪些客戶設定資訊。
6. #1124～#1126 是否仍 HOLD。
7. Production 五軸是否有新證據；沒有就維持既有判讀。
8. 唯一 NEXT。
9. 是否需要客戶回覆。

八、靜默自主巡航
本次僅授權以上安全範圍。
不逐步回報 Agent 派工、CI 或 commit 過程。
完成正式文件同步後，若 DPE-3 的條款與 DPE-6 的 Cloud 設定仍缺客戶證據，停在 Decision／Input Gate。
不得自行推進 DPE-4／DPE-5 或直接合併資料 PR。
現在依客戶正式裁示開始執行。
```

#### AI 整理（非客戶原文；本組依上方原文逐項對應；**不得據以擴大授權**）

**(一) 七項裁示的登錄結果**

| # | 客戶原文要點 | 登錄結果 | 這不是 |
|---|---|---|---|
| 1 | 整體策略：方案 A，資料優先 | **接受**。「方案 A」的提案全文（總管先前向客戶提出者）**repo 內無紀錄，NOT VERIFIED**；本條只以客戶訊息列舉的第 1～7 項為準，不補寫、不外推其餘內容 | 不是對任何未列項目的授權 |
| 2 | DPE-3＝D：先確認外部對帳涉及的資料來源使用條款；確認後才重新考慮是否授權小範圍唯讀對帳 | **已裁示：DPE-3＝D**（DPE-3 方案 D，見下方代號對照表）。狀態＝**BLOCKED／NOT VERIFIED**，等客戶或法務提供條款確認 | **不是 DPE-3 的 B**；不授權任何外部對帳施工；不是 UI 決策單的 Q1＝A；不解除 `DG-LIC` |
| 3 | DPE-6＝B：確認 Streamlit Cloud 實際追蹤的 Repository、Branch、Main file path 與部署觸發方式 | **已裁示：DPE-6＝B**（客戶提供上列四項設定值，**不含 Secrets**）。狀態＝**Input Gate（等客戶貼設定）** | **不含** DPE-6 的 C（日後比對 Cloud 畫面資料日）與 D；不授權 AI 修改 Cloud 設定、部署分支、入口或環境變數 |
| 4 | #1124～#1126 維持 HOLD | **維持**。訊息並重申 #1164（Draft）HOLD、不處置，#1119 Actions 不清理 | 不是合併／關閉／rebase 授權（承 DEC-176(a)） |
| 5 | DPE-7 維持先前已核准的 A（觀察），保留 2026-11-19 檢查點 | **維持 A（觀察）**。2026-11-19 是**保留檢查點，不是自動合併授權** | 不是放行 |
| 6 | 🗂 資料新鮮度總覽 Q1～Q7 暫不裁示，不執行 UI 施工 | **仍待客戶裁示**（DEC-177 裁示單 Q1～Q7 一題都未回答）；不寫 UI code | 不是 Q1＝A，也不是 Q1＝B |
| 7 | DEC178-QB3-* 六項 P3 改善候選暫不施工 | **暫不施工**：`DEC178-QB3-ROUTING-GAPS`、`-HANDOFF-HYGIENE`、`-TOKEN-AB-PROTOCOL`、`-ZEROMEM-V2`、`-1124-TWII-1111`、`-LAST-EDIT-NO-QA`（六項為 BACKLOG 檔尾「Quality Batch 3 完成同步」段 P3 列，本組 `grep` 數得 6 列）；維持「需客戶或總管另行指派、非授權」 | 不是取消，也不是授權 |

**(二) 方案代號對照表（客戶訊息明示「不得混淆方案代號」；本表各列的字母只在所屬決策內有效）**

| 所屬決策 | 代號 | 意義（出處） | 本條是否選中 |
|---|---|---|---|
| 整體策略 | 方案 A | 資料優先（客戶訊息第一點；提案全文 repo 內無，NOT VERIFIED） | **接受** |
| DPE-3（是否授權唯讀外部對帳，以及範圍與來源條款） | A | 不授權，維持 HOLD（`DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md` DPE-3 表） | 未選 |
| | B | 小範圍唯讀對帳：只對 #1124 兩個最大疑點（同上） | **未選、不授權** |
| | C | 全範圍唯讀對帳：三個 PR、板塊業別數、交易日曆（同上） | 未選 |
| | **D** | **先請客戶（或法務）確認外部對帳是否牽涉來源條款（`DG-LIC` 範圍），確認後再回頭選 B 或 C**（同上） | **選中** |
| DPE-6（Streamlit Cloud 追蹤分支與重新部署時機） | A | 不確認（同上 DPE-6 表） | 未選 |
| | **B** | **客戶貼出 App 設定頁的 Repository、Branch、Main file path 與部署觸發方式（不貼 Secrets）**（同上） | **選中** |
| | C | 授權 AI 日後任一資料 PR 合併後，比對 Cloud 畫面資料日與 main 上 `twii_ohlcv.parquet` 末日（同上） | **未選** |
| | D | B 加 C（同上） | **未選** |
| UI 決策單（`NEWUI2_DATA_FRESHNESS_OVERVIEW_IMPLEMENTATION_DECISION_SHEET_2026-11-13.md`）Q1 | A | 🗂 資料頁允許出現「帶真值的欄位」（該決策單 Q1；總管推薦＝A，為 RECOMMENDATION） | **未裁示**（暫不裁示） |
| | B | 不允許 | 未裁示 |
| `DG-LIC`（`DATA_WIRING_GATE_DECISION_SHEET_2026-11-12.md` 決策 4）方案 A／B／C | A／B／C | A＝先取得官方條款原文或法務意見再決定；B＝A 加另案「停止新增」；C＝風險自負先行 | **未選**（見下方有效讀法） |

**(三) DPE-3＝D 的有效讀法**

- **授權的只有一件事**：確認外部對帳所涉資料來源的使用條款（哪些來源、條款原文為何、是否允許以程式唯讀存取以做對帳）。確認方式由客戶決定（貼條款原文／交法務意見／放行網域或提供合法配置環境供唯讀 GET 條款頁——後兩者為 AI 提出的選項，不是客戶裁示）；選項與缺口見證據文件 `docs/vnext/DPE3_TERMS_AND_DPE6_CLOUD_CONFIG_EVIDENCE_2026-11-13.md` §1。
- **「確認後才重新考慮」**：條款確認後，是否授權小範圍唯讀對帳（DPE-3 的 B）**仍須客戶另行明示裁示**，不會自動轉換、不會因條款確認而自動生效。
- **不碰任何資料**：本條不授權連網、登入第三方、抓取或儲存外部資料、新增 API／MCP、動 `data_cache`。
- **與 `DG-LIC` 的關係**：`DG-LIC`（來源授權與再散布）**維持 HOLD、未解除**。DPE-3＝D 與 `DG-LIC` 方案 A 的取證方式相近，但**不是同一個裁示**——客戶沒有答 `DG-LIC` 選 A／B／C，也沒有回答 `I1144-LIC-THREE-QUESTIONS`（商業／公開／個股級來源列）。即使唯讀對帳的條款日後被確認，`DG-LIC` 的其餘部分（呈現／再散布）也不因此解除。

**(四) DPE-6＝B 的有效讀法**

- 客戶選的是 B：**提供**四項設定值（Repository、Branch、Main file path、部署觸發方式）。**不含 C**（日後比對 Cloud 畫面資料日）與 **D**。
- **未收到客戶提供的設定值前，不得宣稱部署正在追蹤 main**；repo 內目前**沒有**任何實際 Cloud 設定紀錄（見證據文件 §2）。
- AI **不得**要求或顯示 Secrets／API Key／Token／密碼；**不得**自行修改 Streamlit Cloud 設定、部署分支、正式入口或環境變數。
- 客戶貼出設定值後，AI 的工作僅限登錄為證據並標明日期與來源類別；是否據以處置資料 PR 仍需 DPE-4／DPE-5 另行裁示。

**(五)「聽你的建議」的含義（不外推）**

客戶訊息以「聽你的建議」作為裁示依據。**其含義僅限客戶訊息所列舉的第 1～7 項**，**不外推**到任何未列項目。下列項目**仍待客戶裁示**，沉默＝維持現狀（承 DEC-176、DEC-177、DEC-178）：DPE-1／DPE-2／DPE-4／DPE-5、VG1／VG2、D6 偵測器程式修復、Q5（`REORG3C-Q5-GATE`）、🗂 Q1～Q7，以及 `DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC` 等接線前決策單項目。

#### 與既有決策的關係

- **DEC-176(a)**（#1124～#1126 方案 A＝維持 HOLD）：維持有效，本條重申；**DEC-176(c)**（DEC-175 不是無條件施工授權）：不受影響。
- **DEC-177**：其末段列舉的其餘項目（含 VG1／VG2、DPE-3／DPE-6 等）原寫為不受影響、仍待裁示；其中 **DPE-3／DPE-6 自本條起更新為「DPE-3＝D、DPE-6＝B 已裁示，尚待客戶補件」**；DEC-177 原文**不改**（以本條說明為準）。DEC-177 的「🗂 實作停在安全點」與 Q1～Q7 待裁示狀態不受影響。
- **DEC-178**：不受影響（三 Agent、Quality Batch 1～3 結果、P3 候選）；BACKLOG 舊列 `DEC178-NEXT-AFTER-QB3` 的「唯一 NEXT」自本批同步起以新追加段為準（舊列原文不改）。**提醒**：`grep` 「唯一 NEXT」會先命中 BACKLOG 舊列 `DEC178-NEXT-AFTER-QB3`（`BACKLOG.md` 約 L2664），其「等待客戶對 DPE-3／DPE-6 裁示」已過期（兩者已有裁示，見上），以本條與 BACKLOG 檔尾 DEC-179 段為準。
- **`CLAUDE.md` §-2、§-1、§-1.5**：不受影響；本條與其同批證據均為單組撰寫＋待非作者獨立 QA（QA 結果由總管於 PR 補記；本條**不得被引用為「已 QA PASS」**）。

#### DEC-179 範圍外與 NOT VERIFIED

- **本條不解除任何 Gate／HOLD**：`DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC`、`I1144-*`（含 `I1144-WIRING-GATE`、`I1144-LIC-THREE-QUESTIONS`）、`G-F2`～`G-F6`、外資 L3、`REORG3C-Q5-GATE`、D6 偵測器、Old UI 移除、OneBrain 正式接線、投資公式／Risk Cap／System Action、新增 API／cron／Secrets、`.claude/settings*`、`SHOWN_FOLDS`／UI 契約／測試 allowlist，均未動。
- **本條不授權**：任何外部對帳、連網、登入第三方、抓取或儲存外部資料、修改 `data_cache`、合併／關閉／rebase #1124～#1126、處置 #1164、清理 #1119、修改或刪除不明 worktree、UI 施工、施工六項 P3 候選。
- **更早紀錄**：DPE-3／DPE-6 的選項與 AI 推薦（先 D、再 B；DPE-6 選 B）出自 `DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md`（RECOMMENDATION，非裁示）；客戶（經訊息轉述）**採納其中 DPE-3 的 D 與 DPE-6 的 B**；推薦中「**D 之後的 B**」（條款確認後選 DPE-3 的 B 做小範圍唯讀對帳）**未被採納**，仍待客戶在條款確認後另行明示。
- **NOT VERIFIED**：fence 與客戶原訊息的逐字一致性；客戶「聽你的建議」原始回覆（repo 內無）；「資料優先方案 A」提案全文（repo 內無）；DPE-3 所涉各來源的條款原文（僅 FinMind 有 PARTIALLY VERIFIED 原文，見證據文件 §1）；Streamlit Cloud 的實際 Repository／Branch／Main file path／部署觸發方式（見證據文件 §2）。本條 AI 整理與本批證據文件為單組撰寫，**未經第二組獨立複驗（`CLAUDE.md` §-2 規則 6），不得被引用為「已 QA PASS」**。

### DEC-180｜客戶 2026-11-13「DPE-6 Cloud 證據補登與 NAS／舊 UI 取數路徑稽核」授權轉錄：Cloud 啟動日誌資訊補登（分級）、唯讀稽核五假說 A–E（2026-11-13；只追加；非 QA PASS）

> 2026-11-13 補登（ID 取下一個未用號；落盤前 `git grep -n "DEC-180" docs/DECISIONS.md` 0 命中，DEC-179 為上一號）。**來源類別 D：客戶 2026-11-13 訊息，經派工訊息轉錄；原始對話 repo 內 NOT VERIFIED，逐字一致性 NOT VERIFIED**（同 DEC-177～179 的標示方式）。下方 fence 收錄派工訊息所附客戶訊息檔的**全文**（含標題、Model／Mode／Effort／Repository 抬頭行與各段之間的空行），未改一字；fence 內不含首尾 fence 行與結尾換行。
> **特別注意（來源鏈）**：訊息所述「客戶提供的 Cloud 啟動日誌」——**日誌原文不在 repo**，本條只收錄客戶訊息對日誌內容的轉述（Repository／Branch／Main file／Python／Streamlit 五項），日誌的日期、commit SHA、repo owner 訊息均未給。
> **sha256 算法**：對 fence 內文（以換行連接各行，不含首尾 fence 行與結尾換行）以 UTF-8 計算，**與 DEC-173～179 同一算法**（本組先以同法重算 DEC-179 的 fence，得 `beb57044…e6951e6`，與其登記值相符；DEC-178 得 `3479c09d…a924b473`，亦相符，後才套用於本條）。

- **決策者**：**客戶**（2026-11-13，經上述轉錄）。｜**效力日期**：2026-11-13 起。
- **客戶原文（逐字，fence 內未改一字；具約束力；但見上方來源鏈提醒）**：fence 內容 sha256＝`3e0ee8f12e2ba53bb0d2fcafe562aac84f74ba607b43109dfc867a01c34dc19f`（撰寫時計算；尚未由測試釘住）。

```
股票儀表板｜DPE-6 Cloud 證據補登與 NAS／舊 UI 取數路徑稽核
Model：Claude Sonnet 5.5
Mode：靜默自主巡航
Effort：High
Repository：linchen-20200325/my-stock-dashboard
客戶新增正式資訊：
Cloud App：
https://my-stock-dashboard-fh2pfdgs2amdtlgvkxvest.streamlit.app/
客戶提供的 Cloud 啟動日誌顯示：

* Repository：my-stock-dashboard
* Branch：main
* Main file：app_ui2.py
* Python：3.14.10
* Streamlit：1.59.2

客戶確認：

* 部署更新需要手動 Reboot／重新部署。

請標明客戶陳述、日誌觀測與尚未驗證的事項，不要將其混成同一級證據。
新增調查要求：
「New UI2 抓不到資料，是否沒有使用 NAS 中繼站？請參考舊 UI 的方式。」
本次授權：
① GitHub-first，核實最新 main、PR、CI、DEC-179 與相關 Gate。
② 將 DPE-6 新證據按既有 SSOT 規範補登。不得把客戶對部署方式的說明冒充 Cloud 自動部署機制的實測。
③ 進行唯讀技術稽核，直接比對：

* app.py 舊 UI 的實際資料取得流程。
* app_ui2.py New UI2 的 Preview／Real Feed。
* proxy_helper.fetch_url。
* NAS Squid 與 nas_relay_fetch。
* 既有 L1 fetcher／L3 canonical services。
* New UI2 已接線及未接線的資料欄位。
* GitHub 資料發布 PR 與本地 parquet 的關係。

特別確認以下假說：
A. New UI2 預設為 FAKE Preview。
B. New UI2 Real Feed 不連網，只讀已發布資料。
C. NAS 未配置或不通造成舊 UI 的部分資料失敗。
D. 資料 PR HOLD 使 main 快取過期。
E. Cloud 未重新部署造成畫面版本落後。
逐項標 FACT／INFERENCE／NOT VERIFIED。
交付一份最小資料流對照：
來源 → NAS／Proxy → L1 → L3 → 快取／資料契約 → New UI2 → 畫面
區分「資料未抓到」「資料尚未發布」「尚未接線」「部署版本未更新」，不得混為同一原因。
禁止：

* 修改 NAS／Proxy／Secrets。
* 顯示任何憑證值或含密碼 URL。
* 修改 app.py 或 app_ui2.py。
* 修改正式資料接線、UI、資料契約或 allowlist。
* 外部 API 探測、資料回補。
* Merge／Close／Rebase #1124～#1126。
* 自行解除 DG-LIC、WIRING-GATE 或其他 HOLD。

若需要文件留證，沿用既有 QA／CI／Merge Gate 流程；不要建立第二套 SSOT。
最終回報：

1. New UI2 缺資料的已確認原因。
2. NAS 在舊 UI 與 New UI2 的實際位置。
3. 哪些問題只需資料發布，哪些需要正式接線。
4. 最小、安全、可重用的建議架構。
5. 尚待客戶裁示的 Gate。
6. 是否需要客戶再提供資訊。

不施工正式接線，完成後停在安全點。
```

#### AI 整理（非客戶原文；本組依上方原文逐項對應；**不得據以擴大授權**）

**(一) 本次授權範圍與禁止清單（逐條對照，原樣不增不減）**

| 客戶原文 | 本組整理 |
|---|---|
| ① GitHub-first，核實最新 main、PR、CI、DEC-179 與相關 Gate | 授權（前置核實）。本組基準：`origin/main`＝`587e1944f546df142fb134578b3f64887b451026`（`git rev-parse` 實查；時點快照，以最新 GitHub 為準）。main push CI run `43425164513`（head_sha＝587e194）：completed／success（**總管 2026-11-13 查，本組未連網重取**）；CI success ≠ 資料已更新 ≠ Production 有效 |
| ② 將 DPE-6 新證據按既有 SSOT 規範補登；不得把客戶對部署方式的說明冒充 Cloud 自動部署機制的實測 | 授權（登錄）。分級見 (二)。客戶「部署更新需要手動 Reboot／重新部署」**登錄為客戶陳述**，**不是** Cloud 設定頁實測，**不證明** Cloud 自動部署或不自動部署 |
| ③ 唯讀技術稽核，直接比對：`app.py` 舊 UI 實際取得流程；`app_ui2.py` New UI2 Preview／Real Feed；`proxy_helper.fetch_url`；NAS Squid 與 `nas_relay_fetch`；既有 L1 fetcher／L3 canonical services；New UI2 已接線及未接線欄位；GitHub 資料發布 PR 與本地 parquet 的關係 | 授權（**唯讀**：讀碼、讀 repo 內文件、讀 git 物件）。結論見 (四)，細節見證據文件 `docs/vnext/UI2_NO_DATA_ROOT_CAUSE_NAS_AND_DPE6_CLOUD_EVIDENCE_2026-11-13.md` |
| 特別確認假說 A～E，逐項標 FACT／INFERENCE／NOT VERIFIED | 見 (四) 判定表 |
| 交付最小資料流對照（來源→NAS／Proxy→L1→L3→快取／資料契約→New UI2→畫面），區分「資料未抓到」「資料尚未發布」「尚未接線」「部署版本未更新」，不得混為同一原因 | 見證據文件 §6、§8 |
| 若需要文件留證，沿用既有 QA／CI／Merge Gate；不要建立第二套 SSOT | 遵守：決策只在本條；證據文件是證據不是決策來源 |

禁止清單（客戶原文「禁止」段，逐項原樣對照；**本組全部遵守，無一項被放寬**）：修改 NAS／Proxy／Secrets；顯示任何憑證值或含密碼 URL；修改 `app.py` 或 `app_ui2.py`；修改正式資料接線、UI、資料契約或 allowlist；外部 API 探測、資料回補；Merge／Close／Rebase #1124～#1126；自行解除 `DG-LIC`、`WIRING-GATE` 或其他 HOLD。另依客戶「不施工正式接線，完成後停在安全點」。

**(二) 客戶新資訊分級（客戶明示「不要混成同一級證據」）與 DPE-6 四欄位更新讀法**

| 級別 | 內容 | 說明 |
|---|---|---|
| **客戶陳述** | Cloud App 網址（完整網址見 fence；子網域前綴 `fh2pfdgs2am…`）；「部署更新需要手動 Reboot／重新部署」 | 客戶說的話；**不是** Cloud 設定頁實測、不是機制證明 |
| **日誌觀測**（客戶提供的 Cloud 啟動日誌；**原文不在 repo、經客戶訊息轉述；觀測日期未給；未含 commit SHA、repo owner**） | Repository＝`my-stock-dashboard`；Branch＝`main`；Main file＝`app_ui2.py`；Python 3.14.10；Streamlit 1.59.2 | 仍屬客戶轉述：**日誌本身不在 repo，無法複驗**；不是設定頁（其證據力是否高於「客戶陳述」＝INFERENCE，不據以升級） |
| **NOT VERIFIED** | repo owner（可能是 fork）；實際部署 commit；日誌日期；該 app 是否即客戶畫面所見的 app；Cloud Secrets 是否配置 NAS；Cloud 是否自動部署；畫面實際版本 | 全部待客戶補件，見 (六) |

一致性（FACT，本組核對）：Streamlit 1.59.2 落在 `requirements.txt:60` 的 `streamlit>=1.56.0,<1.60.0` 範圍內（只證明在範圍內）；Python 3.14.10 與 `ARCHITECTURE.md:613`、`STATE.md:3398` 的「Cloud 3.14」記載一致，但 `.python-version` 內容為 `3.12`、所有 workflow 為 3.11（CI 綠不證明 Cloud 3.14 行為；Cloud 是否採用 `.python-version` 無文件，NOT VERIFIED）。**INFERENCE**：新網址前綴 `fh2pfdgs2am…`（repo 內此前 0 命中）與 repo 內舊記載前綴 `namd8rh9b8s…`（`STATE.md:663` 等）不同，很可能是兩個不同的 app（舊 `app.py` 站 vs 新建 `app_ui2.py` Preview 站；無平台證據）。

**DPE-6 四欄位更新讀法**（針對「產生該日誌的那個 app」；**取代** `DPE3_TERMS_AND_DPE6_CLOUD_CONFIG_EVIDENCE_2026-11-13.md` §2.3 的「全部 NOT VERIFIED」讀法，該文件原文不改）：

| 欄位 | 更新後讀法 |
|---|---|
| Repository | 客戶轉述日誌：`my-stock-dashboard`；**owner NOT VERIFIED**（不能排除 fork） |
| Branch | 客戶轉述日誌：`main`；**日誌日期與部署 commit NOT VERIFIED** |
| Main file path | 客戶轉述日誌：`app_ui2.py`；**至少存在一個此入口的 app**；是否另有 `app.py` 的 app NOT VERIFIED |
| 部署觸發方式 | **客戶陳述**「需手動 Reboot」；非實測、非設定頁證據 |

**仍不得宣稱部署追蹤 main 最新提交；仍不得宣稱 Cloud 自動部署，也不得宣稱不自動部署。**

**(三) 本條不是新的施工授權；對 DEC-179 的關係**

- 本條授權範圍僅限 (一) ③ 的**唯讀稽核**與文件登錄。**不解除任何 Gate／HOLD**（`DG-LIC`、`I1144-WIRING-GATE`、`DG-SCOPE`／`DG-COV`／`DG-PIT`、DPE-1／2／4／5、DEC-177 Q1～Q7、`REORG3C-Q5-GATE`、D6、Old UI 移除、OneBrain 接線、投資公式／Risk Cap／System Action、新增 API／cron／Secrets、`.claude/settings*`、`SHOWN_FOLDS`／UI 契約／測試 allowlist 均未動）。
- **DEC-179**：DPE-6＝B 的裁示維持。客戶本次提供的是**部分補件**（三級分類見 (二)），**仍未達性質 iv（Cloud 設定頁證據）**。DEC-179 原文不改；其「DPE-6 尚待客戶補件」自本條起讀作「已有部分補件（日誌轉述＋客戶陳述），設定頁證據與 owner／commit 仍缺」。DPE-3＝D 不受影響，仍 BLOCKED。DEC-179 對「聽你的建議」不外推的限制不受影響。
- 本條單組撰寫，**待非作者獨立 QA**（QA 結果由總管於 PR 補記；本條**不得被引用為「已 QA PASS」**）。

**(四) 稽核結論摘要（假說 A～E；單組、唯讀、未連網、未執行任何程式）**

| 假說 | 判定 | 要點 |
|---|---|---|
| A. New UI2 預設為 FAKE Preview | **FACT（程式碼層）** | `src/ui2/shell/app.py:86-87` 預設 `FEED_FAKE`；預設場景 cold；切換只在 `?ui2_dev=1`；Cloud 實際畫面是否為 FAKE＝NOT VERIFIED（需客戶看頂部標示） |
| B. Real Feed 不連網，只讀已發布資料 | **FACT（UI2 呼叫路徑）** | `real_feed.read_real_snapshot` 只呼叫三個唯讀 reader；UI2 目錄 grep 網路／proxy／secrets 關鍵字 0 命中；有守衛 G2F。**UI2 不用 NAS 是設計並有守衛強制，不是漏接**。測試是否 PASS＝NOT VERIFIED（未執行） |
| C. NAS 未配置或不通造成舊 UI 部分資料失敗 | **NOT VERIFIED** | repo 內「NAS 變數皆未設定」的 2026-11 紀錄描述的是 AI 沙箱，不是客戶 Cloud，不可外推；最後一筆 Cloud 側「NAS 狀態」紀錄在 2026-07-13（`STATE.md:2953-2955`），其後 2026-08 的 Cloud 紀錄（`STATE.md:663` 實機驗收、`HANDOFF_2026-08-15.md`）未涉及 NAS 配置；即使 NAS 正常 UI2 也不呼叫它 |
| D. 資料 PR HOLD 使 main 快取過期 | **分層**：main 資料停在 2026-11-09＝FACT；較新資料在 PR 分支＝FACT；「PR 未併入是原因」＝INFERENCE；「因此畫面完全沒資料」**不成立**（INFERENCE） | 台股卡讀 main 的 11-09，距今 4 天 ≤ 日頻門檻 7 天，顯示資料日但不出現過期警示（時點註記：僅 2026-11-13 成立；2026-11-17 起 age_days＝8 將轉為過期；UI2 實際 as_of 來自 parquet 最後一列〔未直接讀，沙箱無 pyarrow〕，此處用 metadata 自陳值）；`finmind_m1m2`＝NO_NEW_DATA（請求窗口內無新月份，非連線／抓取失敗）、`tw_pmi`＝UNDETERMINED（最近一次抓取結果無法判定：無新資料或 parser 略過，metadata `fetch_evidence` 寫「parser 略過列數無從核對」；定義見 `shared/upstream_state.py:37`）；故 tw_pmi 不歸入「資料未抓到」，也不確認為「資料已是最新」；二者皆非 PR HOLD 造成 |
| E. Cloud 未重新部署造成畫面版本落後 | **NOT VERIFIED** | repo 無 deploy／webhook workflow；UI2 畫面無 commit／版本字串，無從分辨「舊部署」與「新部署但資料舊」；客戶陳述需手動 Reboot 僅為陳述 |

**一句話答覆客戶問題「New UI2 抓不到資料，是否沒有使用 NAS 中繼站？」**：**New UI2 沒有用 NAS，這是設計（並有守衛強制），不是漏接**；Cloud 上的 UI2 即使配好 NAS 也不會用。要讓 UI2 顯示更多真資料，路徑不是「讓 UI2 走 NAS」，而是 (1) 資料發布（cron 用 NAS 抓→PR 併入 main），(2) 正式接線（L3 唯讀 adapter＋白名單），**兩者皆是 Gate 項**。畫面「沒資料」最可能的直接原因（INFERENCE，未實機驗）：預設 FAKE cold 的「尚未載入」＋Real 模式下絕大多數欄位尚未接線＋位階狀態檔在 Cloud 不存在；資料落後（11-09）是次要，且不會顯示成空白（11-17 起轉過期，屆時需重評）。四類原因（資料未抓到／資料尚未發布／尚未接線／部署版本未更新）**不得混為一談**，對照見證據文件 §8。

**(五) 建議架構方案 A／B／C（RECOMMENDATION，非裁示；全部未獲授權）**

| 方案 | 做法 | 結論 |
|---|---|---|
| A（總管推薦） | 維持 UI2 無網路架構：先解資料發布（DPE-1／2／4／5 另案）→逐欄位走 WIRING-GATE 接線（重用既有 `*_fact_service`）→位階狀態檔改由 cron 發布到 `data_cache`→UI2 加「版本＋資料日」小標（需線框草稿 Gate）。**前置 Gate**：②外資／融資／板塊接線除 `I1144-WIRING-GATE` 外，另受 `DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE` 阻塞（見 BACKLOG「Quality Batch 1 完成同步」段）；③位階狀態檔改由 cron 發布涉及新增發布流程＝「新增 API／cron／Secrets」類 HOLD，需另行裁示，且單獨**不保證**位階顯示——位階還需 session `warroom_summary` 來源（`real_feed.py:11`、ISSUE1110）且 `BREADTH_PROXY_SCORING_ENABLED=False`（`shared/signal_thresholds.py:277`；`real_canonical.py:303-305`），即使狀態檔發布，位階仍可能是灰「尚缺市場廣度」，需另案裁示 | 推薦；多個客戶裁示、速度慢 |
| B | 讓 UI2 Real Feed 在 Cloud 直接呼叫 L1 fetcher（走 proxy_helper／NAS） | **不建議**：違反 G2F 守衛與「UI 不抓資料」，牽涉 `DG-LIC`，NAS 配置未驗。A 與 B 呈現的 TWSE／FinMind／Yahoo 資料同樣受 `DG-LIC` 約束（呈現與再散布面）；B 的額外問題是 Cloud 執行期自動化存取（Cloud 側可能被來源擋〔`STATE.md:2859-2873` 記載 2026-07-14 雲端 proxy 對 FRED 回 403〕、timeout 64 秒〔`ISSUE1110_DATA_AVAILABILITY_MATRIX_2026-11-10.md` 的 `fetch_url` 順序段〕、200 錯誤頁被快取 300 秒）與需放寬 G2F 守衛（放寬 allowlist 屬禁區） |
| C | 只改文案／標示（FAKE cold 理由句與 CTA、部署版本標），不接新資料 | 可併入 A 的草稿；屬 UI 文案／版面 Gate，需草稿 |

比較（正確性、風險、速度、Token／成本）見證據文件 §11。**A／B／C 皆為 RECOMMENDATION，皆未獲授權**；客戶本次明示「不施工正式接線」。

**(六) 尚待客戶裁示的 Gate 與需客戶再提供的資訊**

- **Gate（本條不授權、不施工）**：`DG-LIC`（DPE-3＝D 進行中，BLOCKED）；`I1144-WIRING-GATE`（逐欄位正式接線）；DPE-1／2／4／5（**不得自行推進、不得 merge #1124～#1126**）；UI 草稿 Gate（FAKE cold 理由句與 disabled CTA 文案／互動語意；UI2 版本＋資料日標示；🗂 資料新鮮度總覽 Q1～Q7）；位階狀態檔發布方式；`DEC178-QB3-*` P3 候選仍未授權。
- **需客戶再提供（最小；全部排除 Secrets／API Key／Token／密碼）**：(1) 打開該 Cloud 網址（不加 `?ui2_dev=1`），頂部第一列是「示意資料（FAKE）」還是「Real-data Preview」（或截圖頂部＋台股卡）；(2) 啟動日誌日期，以及 Manage app 內可見的 repo owner（owner/repo）與部署 commit 前 7 碼（看得到才填）；(3) 舊 app（前綴 `namd8rh9b8s…`）是否仍存在、Main file 是否 `app.py`；(4) （選填）Cloud Secrets 內 `PROXY_URL`、`NAS_PROXY_URL`、`PROXY_HOST`、`NAS_BASE_URL`、`NAS_API_KEY` 是否非空——只要「是／否」，**不要貼任何值**。可複製回覆範本見證據文件 §13。

#### DEC-180 範圍外與 NOT VERIFIED

- **範圍外**：本條不修改 NAS／Proxy／Secrets、`app.py`／`app_ui2.py`、`src/`、`tests/`、`shared/`、`scripts/`、`.github/`、`data_cache`、`.claude/`；不授權外部 API 探測、資料回補、對帳；不授權合併／關閉／rebase #1124～#1126；不授權 UI 施工；舊 UI 觀察到的資料問題 P1～P9 僅登記為 backlog 候選觀察（P3），**不修、不登為授權工作**。
- **NOT VERIFIED**：fence 與客戶原訊息的逐字一致性；Cloud 啟動日誌原文、日期、commit、owner；客戶畫面實際版本與頂部標示；Cloud 是否自動部署；Cloud Secrets 內容（含 NAS 配置）；GitHub 端 secret 是否有值；舊 app 現況；parquet 最後一列日期（沙箱無 pyarrow，資料日為 metadata 自陳值）；相關測試是否通過（未執行任何測試／程式）；UI2 卡片實際走哪套新鮮度門檻；GitHub Issue #1107／#1108 與 Deployments／Environments 未檢視；本地為淺層複製。四組稽核皆單組，總管另親驗 3 點（見證據文件 §0）。本條 AI 整理與本批證據為單組撰寫，**未經第二組獨立複驗（`CLAUDE.md` §-2 規則 6），不得被引用為「已 QA PASS」**。

### DEC-181｜客戶 2026-11-13「資料更新到最新交易日的安全處理」授權轉錄：客戶 Cloud 實測（口述）登錄、最新有效交易日與更新程序規劃（2026-11-13；只追加；非 QA PASS；非施工授權）

> 2026-11-13 補登（ID 取下一個未用號；落盤前 `git grep -n "DEC-181" docs/DECISIONS.md` 0 命中，DEC-180 為上一號）。**來源類別 D：客戶 2026-11-13 訊息，經派工訊息轉錄；原始對話 repo 內 NOT VERIFIED，逐字一致性 NOT VERIFIED**（同 DEC-177～180 的標示方式）。下方 fence 收錄派工訊息所附客戶訊息檔的**全文**（含標題、Model／Mode／Effort／Repository 抬頭行、段落間空行），未改一字；fence 內不含首尾 fence 行與結尾換行。fence 內**沒有**任何 Cloud 網址全文。
> **sha256 算法**：對 fence 內文（以換行連接各行，不含首尾 fence 行與結尾換行）以 UTF-8 計算，**與 DEC-173～180 同一算法**（本組先以同法重算 DEC-180 的 fence，得 `3e0ee8f1…c19f`，與其登記值 `3e0ee8f12e2ba53bb0d2fcafe562aac84f74ba607b43109dfc867a01c34dc19f` 相符；DEC-179 得 `beb57044…e6951e6`，亦相符，後才套用於本條）。
> **同批關係**：本條與下一條 DEC-182（同日客戶訊息「恢復正常 CI 工作流程與資料優先續工」）在同一個尚未推送的 commit；**Actions 可用性（含任何「帳務」相關敘述）一律以 DEC-182 為準**，本條不留與之矛盾的說法。

- **決策者**：**客戶**（2026-11-13，經上述轉錄）。｜**效力日期**：2026-11-13 起。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：fence 內容 sha256＝`57ad41cf13b93c39e55cc46333d3151e9cad584990b7c0adda47109671d66040`（撰寫時計算；尚未由測試釘住）。

```
股票儀表板｜資料更新到最新交易日的安全處理
Model：沿用目前專案模型
Mode：GitHub-first／靜默自主巡航
Effort：High
Repository：linchen-20200325/my-stock-dashboard
客戶已提供 Cloud 實測：

* 預設畫面：FAKE。
* 切換 Real-data Preview：成功。
* 台股加權指數：41,661.70。
* 畫面資料日：2026-11-09。
* 日 K 正常顯示，其他指標多數尚未接線。
* Cloud 啟動日誌顯示 main／app_ui2.py。
* Cloud 部署更新方式：客戶表示需手動 Reboot。
* Cloud 實際部署 commit、舊 App 現況及 NAS Secrets 配置仍 NOT VERIFIED。

客戶採納資料優先架構方案 A，希望知道能否安全強制更新至最新完整交易日。
請執行：

1. GitHub-first 核實最新 main、#1188 合併後狀態、CI，以及 #1124～#1126 最新 head。
2. 唯讀核對 main 和 #1124 的台股資料日期、欄位完整性、來源及 PIT 缺口。
3. 確認既有 update_macro_history.yml 手動觸發與 dry-run 的實際行為，釐清它會寫哪些資料、更新哪個分支，以及 GitHub Actions 帳務是否影響執行。
4. 提出最小的一次性資料更新與發布程序，清楚列出哪些 Gate 必須先通過。
5. 優先考慮既有資料來源、既有 NAS、既有 L1／L3；不得改為 New UI2 直接連網。
6. 將客戶 Cloud 畫面實測列入既有交接紀錄，與程式碼推論分開。

限制：

* 目前只授權唯讀稽核與更新程序規劃。
* 不實際觸發抓取、bootstrap 或資料回補。
* 不合併、不關閉、不 rebase #1124～#1126。
* 不修改 NAS、Secrets、資料契約或正式 UI。
* 不繞過 DG-LIC、DG-PIT、DG-COV、DPE-4／5 或 CI Gate。
* 若 CI 因 Billing 無法啟動，保留證據，勿反覆重跑。
* 不重做 DEC-180 已完成稽核，不為進度重複開文件 PR。

最終只需回報：
① 目前可取得的最新有效交易日。
② 最快安全更新台股卡的做法。
③ 更新前必須解除哪些 Gate。
④ 是否需要客戶進一步裁示。
完成後停在安全點。
```

#### AI 整理（非客戶原文；本組依上方原文逐項對應；**不得據以擴大授權**）

**(一) 本次授權範圍與禁止清單（逐條對照，原樣不增不減）**

| 客戶原文 | 本組整理 |
|---|---|
| 1. GitHub-first 核實最新 main、#1188 合併後狀態、CI，以及 #1124～#1126 最新 head | 授權（前置核實）。本組基準：`origin/main`＝`138e081bbec24f5b20f1301c1da634d4ab8d9551`（`git rev-parse` 實查）；#1124 head `3cd3f525…`、#1125 head `cf4739c5…`、#1126 head `1654ae60…`（本地 `origin/auto/*` ref 實查，與總管 2026-11-13 22:20 台北的 GitHub 查詢相同；時點快照，cron 每日推進）。main push CI run `43437741216`（head_sha＝138e081）completed／success＝**總管 2026-11-13 查，本組未連網重取**；CI success ≠ 資料已更新 ≠ Production 有效 |
| 2. 唯讀核對 main 和 #1124 的台股資料日期、欄位完整性、來源及 PIT 缺口 | 授權（**唯讀**：`git show` 讀本地 ref，scratchpad 內 pyarrow 讀 parquet）。結果見 (三) 與證據文件 §2 |
| 3. 確認既有 `update_macro_history.yml` 手動觸發與 dry-run 的實際行為，釐清寫哪些資料、更新哪個分支，以及 GitHub Actions 帳務是否影響執行 | 授權（讀碼，未執行）。結果見 (三) 與證據文件 §4、§5；Actions 可用性以 DEC-182 為準 |
| 4. 提出最小的一次性資料更新與發布程序，清楚列出哪些 Gate 必須先通過 | 授權（規劃）。結果見 (四) 與證據文件 §6、§8；**RECOMMENDATION，未獲授權執行** |
| 5. 優先考慮既有資料來源、既有 NAS、既有 L1／L3；不得改為 New UI2 直接連網 | 遵守：程序中 NAS／Proxy 只留在 cron producer 端，UI2 維持只讀 `data_cache`（承 DEC-180 G2F 守衛） |
| 6. 將客戶 Cloud 畫面實測列入既有交接紀錄，與程式碼推論分開 | 見 (二)；HANDOFF、PROJECT_STATE §70.23、BACKLOG 同步 |

禁止清單（客戶原文「限制」段，逐項原樣對照；**本組全部遵守，無一項被放寬**）：目前只授權唯讀稽核與更新程序規劃；不實際觸發抓取、bootstrap 或資料回補；不合併、不關閉、不 rebase #1124～#1126；不修改 NAS、Secrets、資料契約或正式 UI；不繞過 `DG-LIC`、`DG-PIT`、`DG-COV`、DPE-4／5 或 CI Gate；若 CI 因 Billing 無法啟動，保留證據、勿反覆重跑（**此原則保留**，其「帳務」前提的現況讀法見 DEC-182）；不重做 DEC-180 已完成稽核，不為進度重複開文件 PR。另依客戶「完成後停在安全點」。

**(二) 客戶 Cloud 實測（口述）與程式碼推論——分欄，不得混成同一級證據**

| 客戶陳述／實測（性質＝客戶口述；repo 內不可驗） | 程式碼／資料推論（寫入組；不升級） |
|---|---|
| 預設畫面＝FAKE | FACT（程式碼層）：預設 `FEED_FAKE`（DEC-180 假說 A）；與口述一致 |
| 切換 Real-data Preview 成功 | 與 DEC-180 假說 B 一致（INFERENCE：口述未述切換方式） |
| 台股加權指數 41,661.70；畫面資料日 2026-11-09 | **FACT（資料）**：`origin/main` 的 `twii_ohlcv.parquet` 最後一列＝2026-11-09、close＝41661.699219。與口述**吻合**；INFERENCE：弱旁證「部署的檔案至少含 main 的 11-09 資料」，**不能證明**部署 commit＝最新 main，也**不能證明**自動部署 |
| 日 K 正常顯示；其他指標多數尚未接線 | 與 DEC-180 §4 一致（FACT，程式碼層）；日 K 通過契約為 INFERENCE（未實機驗） |
| Cloud 啟動日誌顯示 main／app_ui2.py | 客戶口述的日誌觀測，日誌原文不在 repo；日期、commit、owner NOT VERIFIED |
| 部署更新需手動 Reboot | 客戶陳述；非 Cloud 設定頁證據；**不證明**自動部署或不自動部署 |
| （NOT VERIFIED） | Cloud 實際部署 commit、舊 App 現況、NAS Secrets 配置 |

**客戶「採納資料優先架構方案 A」的含義**：對應 DEC-180 (五) 建議架構方案 A（維持 UI2 無網路架構，先解資料發布，再逐欄位走 WIRING-GATE 接線；亦與 DEC-179 整體策略「方案 A，資料優先」同名）。客戶訊息未逐字指明是哪一份，**對應關係為本組解讀（INFERENCE）**。其效力＝客戶對**方向**的採納；**不是**任何 Gate 的授權、不授權施工、不授權觸發抓取／bootstrap／回補、不解除任何 HOLD。

**(三) 稽核結論摘要（單組、唯讀、未連網、未執行任何程式；細節見證據文件 `docs/vnext/LATEST_TRADING_DAY_REFRESH_PROCEDURE_2026-11-13.md`）**

- **最新有效交易日**：main（Cloud 所見）**2026-11-09**（FACT）；repo 內已存在的最新價格完整日 **2026-11-11**，但**只在 #1124 分支**（FACT；11-10、11-11 OHLC 全有值且自洽，價格真實性未對外部核對）；理論可信上限 11-12（INFERENCE），但**任何已知 ref 上都沒有 11-12 的台股列**（原因 NOT VERIFIED）；11-10～11-12 是否為交易日 NOT VERIFIED（G-07）。三資料集最新日不齊：twii 11-11、inst／margin 11-12（分支）。
- **資料品質觀察**：11-10 volume 先空後補寫（`d0f14437`→`fc447def`，`fetched_at` 不變）；inst 外資 11-11 −7.66 億、11-12 −6.85 億，比最近 60 列 |值| 中位數（約 417 億）小約兩個數量級，標為**可疑，NOT VERIFIED**；`finmind_m1m2`＝NO_NEW_DATA、`tw_pmi`＝UNDETERMINED（皆非 PR HOLD 造成）。
- **workflow 行為（FACT，讀碼）**：預設手動 dispatch＝真實發布；`dry_run=true` 仍連外抓取、只跳過發布；`bootstrap=true` 整檔覆寫，**本批與日後都不得用於更新到最新日**；發布分支固定 `auto/data-macro-history`、PR 對 main、不直推；#1124 的 head 只在有實質新資料（新資料列、新 `last_error` 或 `fetch_outcome` 變化）時前進——僅揮發欄位變動時發布腳本還原工作樹、不開 PR（`scripts/publish_data_pr.py` L125-141、L833-851；沒有新交易日的執行預期不 commit，INFERENCE，未實測）；cron 與手動都不會讓 main 前進。
- **Actions 可用性**：以 **DEC-182** 為準（客戶陳述公開 Repository、Actions 可正常執行；repo 內近期 run 皆正常完成為 INFERENCE 支持；不再列為阻擋事項）。
- **Gate 對照（INFERENCE，依 docs 適用範圍）**：阻擋＝客戶 HOLD（#1124）、DPE-4、DPE-5；部分＝DPE-3／DG-LIC、DG-PIT、DPE-1；不阻擋＝DG-SCOPE／DG-COV／WIRING-GATE、DPE-2、DPE-7。完整表見證據文件 §6。

**(四) 更新程序（RECOMMENDATION，非裁示；未獲授權執行；AI 不觸發任何抓取）**

總管推薦：**不手動 dispatch、不 bootstrap；等下一輪 schedule（預期台北 11-13 約 23:30～11-14 約 03:45）把 11-12 寫進 `auto/data-macro-history` 後，在「同一個 head」上走既有路徑**：S0 AI 唯讀檢核→S1 客戶裁示→S2 客戶於同 head 觸發 CI（DPE-5）→S3 非作者唯讀審閱→S4 客戶明示 merge→S5 客戶手動 Reboot Cloud→S6 依客戶回報核對資料日。替代路徑 A（合併現 head）／C（客戶端手動 dispatch）／D（不處理）與禁止路徑的比較，以及每步的授權狀態（已授權／待核准／禁止），見證據文件 §8。**11-17 起 UI2 台股卡 `age_days`＝8 轉過期警示**（若合併 as_of 11-11 的資料則推遲到 11-19）。

**(五) 尚待客戶裁示項與需客戶提供資訊（沉默＝維持現狀）**

DPE-4＝B（**僅 #1124** 進放行評估；注意 GAPS 文件原 B 範本是 #1124＋#1125，本程序要的是變體，須客戶明示）；DPE-3／DG-LIC 與 DG-PIT 取捨（等條款確認，或明示承擔風險——效力以客戶原文與後續 DEC 為準，AI 不自行認定已解除）；DPE-5（客戶於同 head 觸發 CI）；merge 明示；是否整包接受 inst 11-11／11-12 可疑值；是否授權客戶端手動 `workflow_dispatch`（路徑 C，不建議）；Cloud 手動 Reboot 後回報畫面資料日。**請勿貼 Secrets／API Key／Token／密碼；截圖遮蔽 NAS 網址與主機名。** 可複製回覆範本見證據文件 §10。

**(六) 與既有決策的關係**

- **DEC-176(a)／DEC-179／DEC-180**：#1124～#1126 維持 HOLD；DPE-3＝D（BLOCKED）、DPE-6＝B（部分補件）不受影響。DPE-6 現況：本批客戶口述再補（預設 FAKE、Real 切換、41,661.70／11-09、需手動 Reboot），**仍無 Cloud 設定頁證據**；仍不得宣稱部署追蹤 main 最新提交，也不得宣稱 Cloud 自動部署或不自動部署。
- **DEC-180**：假說 A（預設 FAKE）、B（Real 只讀已發布資料）、D（main 停 11-09、PR 分支較新）在客戶**畫面層**得到口述印證；E（Cloud 版本落後）與 C（NAS 配置）仍 NOT VERIFIED。DEC-180 原文不改。
- **DEC-156 A**：不核准新 live API、cron、publisher 或第二個 writer——本程序只走既有 producer 路徑。
- **`CLAUDE.md` §-2、§-1、§-1.5**：不受影響；本條與證據文件為單組撰寫＋待非作者獨立 QA（QA 結果由總管於 PR 補記；**本條不得被引用為「已 QA PASS」**）。

#### DEC-181 範圍外與 NOT VERIFIED

- **本條不解除任何 Gate／HOLD**，不授權：觸發任何抓取／bootstrap／回補／手動 workflow、合併／關閉／rebase #1124～#1126、處置 #1164、修改 NAS／Secrets／Branch Protection／資料契約／`app.py`／`app_ui2.py`／UI、新增 API／cron／Secrets、施工 `DEC178-QB3-*`／`DEC180-*`／`DEC181-*` Candidate 列。
- **NOT VERIFIED**：fence 與客戶原訊息的逐字一致性；客戶 Cloud 實測的任何一項（口述）；Cloud 實際部署 commit、日誌日期、repo owner；Cloud 是否自動部署；Cloud Secrets 內容；GitHub 端 secret 是否有值；CI run id 與結論（總管轉述）；11-10～11-12 是否為交易日；11-12 台股缺列原因；inst 11-11／11-12 的真值；Yahoo／FinMind 原始回應；相關測試是否通過（未執行任何測試／程式）。三組稽核皆單組，本條 AI 整理與證據文件**未經第二組獨立複驗（`CLAUDE.md` §-2 規則 6），不得被引用為「已 QA PASS」**。

### DEC-182｜客戶 2026-11-13「恢復正常 CI 工作流程與資料優先續工」授權轉錄：Actions 可用性澄清、已授權步驟與待核准事項分界（2026-11-13；只追加；非 QA PASS；非施工授權）

> 2026-11-13 補登（ID 取下一個未用號；落盤前 `git grep -n "DEC-182" docs/DECISIONS.md` 0 命中，DEC-181 為上一號，與本條同一個尚未推送的 commit）。**來源類別 D：客戶 2026-11-13 訊息，經派工訊息轉錄；原始對話 repo 內 NOT VERIFIED，逐字一致性 NOT VERIFIED**（同 DEC-177～181）。下方 fence 收錄客戶訊息檔**全文**，未改一字；fence 內不含首尾 fence 行與結尾換行。
> **sha256 算法**：與 DEC-173～181 同一算法（fence 內文以換行連接各行，不含首尾 fence 行與結尾換行，UTF-8）。

- **決策者**：**客戶**（2026-11-13，經上述轉錄）。｜**效力日期**：2026-11-13 起。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：fence 內容 sha256＝`c1111a7d792847ffbd3976530db0227a45ee7a5a0f7559e341b846c8085f03c1`（撰寫時計算；尚未由測試釘住）。

```
股票儀表板｜恢復正常 CI 工作流程與資料優先續工
Model：沿用目前專案模型
Mode：GitHub-first／靜默自主巡航
Effort：High
Repository：linchen-20200325/my-stock-dashboard（Public）
客戶已澄清：本專案是公開 Repository，GitHub Actions 可以正常執行。其他私有專案的帳務限制不得套用於本專案。
ChatGPT 最新獨立核實：

* main：138e081bbec24f5b20f1301c1da634d4ab8d9551
* #1188 已合併。
* #1188 head a18b481 的原生 CI run 43434257213：五項 success。
* #1124、#1125、#1126、#1164 仍開啟，維持原有 HOLD。

請從上一批「安全更新台股資料」三組稽核的既有進度繼續，不要重新派工或重做已完成的稽核。
本批最多三項：

1. 整合已完成的資料日期稽核、workflow 行為稽核、Gate 與有效交易日判準。缺少結果時，繼續既有任務，不另建重複工作。
2. 提出讓台股資料從 2026-11-09 安全更新到最新有效交易日的最小方案，包括資料抓取、PIT、來源授權、驗證、發布到 main、Cloud 重新部署與資料日期確認。清楚區分可以立即執行的已授權步驟和仍待核准的事項。
3. 在既有授權範圍內完成必要的證據及交接同步，沿用現行獨立 QA、同 head CI 與 Merge Gate。無須因其他專案帳務問題停工。

禁止：

* 未經裁示合併、關閉或 rebase #1124～#1126。
* 繞過 DG-LIC／DG-PIT／DG-COV／DG-SCOPE／WIRING-GATE。
* 直接讓 New UI2 呼叫 NAS 或 L1 抓取程式。
* 更改 Secrets、GitHub Actions 預算、Branch Protection 或正式資料契約。
* 自行啟動新的資料回補或 Production 接線工作。

如果發現某個已確認的工程缺陷且只有一個安全修法，可依專案既有常設授權與 Gate 處理；不明確的資料發布或架構決策仍須客戶裁示。
僅在整批驗收完成或真正遇到 Decision Gate 時回報。
正式恢復股票儀表板專案續工。
```

#### AI 整理（非客戶原文；**不得據以擴大授權**）

**(一) 客戶澄清（客戶陳述；repo 內無法驗證）與核對結果**

| 客戶陳述／轉述 | 本組核對 |
|---|---|
| 本專案是公開 Repository，GitHub Actions 可正常執行；其他私有專案的帳務限制不得套用於本專案 | **客戶陳述**。repo 內無可驗證的可見性或帳單資料（AI 讀不到 repo 設定頁與帳單頁）。支持性 INFERENCE：`update_macro_history` schedule 最近 6 次（run #193～#198）皆 success、pr-check 2026-11-13 多次正常啟動並完成（總管查，本組未連網重取） |
| ChatGPT 最新獨立核實（客戶轉述）：main `138e081bbec24f5b20f1301c1da634d4ab8d9551` | **FACT**：`git rev-parse origin/main` 實查相同 |
| #1188 已合併 | 與 main 138e081 的提交標題「…(#1188)」一致（`git log` 實查）；合併狀態以 GitHub 為準 |
| #1188 head `a18b481` 的原生 CI run 43434257213：五項 success | 本地可核對：提交 `a18b4815`（「docs: #1188 Delta QA 最小修正…」）存在。**run id 與五項 success＝總管轉述（總管 2026-11-13 查：run 43434257213 為 #1188 head a18b4815 的 pull_request run，五項 check 皆 success），本組未連網重取** |
| main push CI | 總管 2026-11-13 查：run 43437741216（head_sha＝138e081）completed／success；本組未重取。CI success ≠ 資料已更新 ≠ Production 有效 |
| #1124、#1125、#1126、#1164 仍開啟，維持原有 HOLD | 本地 ref 核對 #1124／#1125／#1126 head 與總管查詢相同；開啟狀態與 #1164 draft 以 GitHub 為準（總管查） |

**(二) 本批授權（逐條轉錄，不擴張）**

| # | 客戶原文要點 | 登錄結果 | 這不是 |
|---|---|---|---|
| 1 | 從上一批三組稽核既有進度繼續，整合資料日期稽核、workflow 行為稽核、Gate 與有效交易日判準；缺少結果時繼續既有任務，不另建重複工作 | 已整合於 DEC-181 與證據文件 `LATEST_TRADING_DAY_REFRESH_PROCEDURE_2026-11-13.md`；**未重新派工、未重做 DEC-180 稽核** | 不是新的稽核授權 |
| 2 | 提出讓台股資料從 2026-11-09 安全更新到最新有效交易日的最小方案（抓取、PIT、來源授權、驗證、發布到 main、Cloud 重新部署、資料日期確認），**清楚區分可以立即執行的已授權步驟和仍待核准事項** | 見證據文件 §8（S0–S6 逐步標註「授權狀態：已授權／待核准／禁止」）；RECOMMENDATION | 不是執行授權 |
| 3 | 在既有授權範圍內完成必要的證據及交接同步，沿用現行獨立 QA、同 head CI 與 Merge Gate；無須因其他專案帳務問題停工 | 文件與交接同步已列為**已授權**；QA／CI／Merge Gate 流程不變 | 不是放寬任何 Gate |

**(三) 禁止清單（原樣對照；本組全部遵守）**：未經裁示不得合併、關閉或 rebase #1124～#1126；不得繞過 `DG-LIC`／`DG-PIT`／`DG-COV`／`DG-SCOPE`／`WIRING-GATE`；不得讓 New UI2 直接呼叫 NAS 或 L1 抓取程式；不得更改 Secrets、GitHub Actions 預算、Branch Protection 或正式資料契約；不得自行啟動新的資料回補或 Production 接線工作。**「已確認工程缺陷且只有一個安全修法」** 可依專案既有常設授權與 Gate 處理；**不明確的資料發布或架構決策仍須客戶裁示**。客戶要求僅在整批驗收完成或真正遇到 Decision Gate 時回報。

**(四) 對先前敘述的更新讀法（不改既有 DEC 原文；本條與 DEC-181 同一未推送 commit，故 DEC-181／證據文件／BACKLOG／HANDOFF／PROJECT_STATE 已直接以本條為準撰寫，不留兩套說法）**

- **Actions 可用性**：客戶已澄清公開 Repository、Actions 可正常執行（客戶陳述）；repo 內近期 run 皆正常完成（INFERENCE 支持）；帳單頁與 repo 設定頁 AI 仍讀不到（NOT VERIFIED），但**不再列為阻擋事項，也不得因「帳務」停工**。保留原則：**若 CI 因任何平台原因無法啟動，保留證據、勿反覆重跑**。BACKLOG 列由 `DEC181-ACTIONS-BILLING-NOT-VERIFIED` 改寫為 `DEC181-ACTIONS-AVAILABILITY`（同一未推送 commit，故直接用新名，不留舊名）。
- **#1124 的 `action_required`／jobs 0**：仍是 Actions 核准機制（NOT VERIFIED 其設定），不是啟動失敗，也不因本條改變；DPE-5 仍需客戶動作。

**(五) 本條不是新的施工授權；「已授權步驟」與「仍待核准」的分界**

| 類別 | 項目 |
|---|---|
| **可立即執行的步驟（視為已授權〔AI 解讀〕；僅此）** | (a) **S0 唯讀檢核**：下一輪 schedule 後重查 `auto/data-macro-history` 的資料與 PR 狀態，**不連外抓資料**；(b) 文件與交接同步（沿用獨立 QA、同 head CI、Merge Gate）；(c) **非作者唯讀審閱 #1124 diff**（head 漂移時重做） |
| **仍待核准（客戶）** | DPE-4＝B（僅 #1124）；DPE-3／DG-LIC 與 DG-PIT 取捨；DPE-5（客戶於同 head 觸發 CI）；merge 明示；Cloud 手動 Reboot 後回報資料日；是否整包接受 inst 11-11／11-12 可疑值；是否授權客戶端手動 `workflow_dispatch`（路徑 C） |
| **禁止** | 觸發任何抓取／bootstrap／回補；合併、關閉、rebase #1124～#1126；直推 main；關 PR＋刪分支重建；只含 twii 的新發布流程；讓 UI2 呼叫 NAS／L1 |

**授權依據（解讀，非客戶逐項點名）**：AI 解讀為落在客戶「唯讀稽核與更新程序規劃」授權內（DEC-181 限制段；DEC-182 第 3 項「證據及交接同步」）；客戶未逐項點名 S0／diff 審閱；不含任何抓取或 Gate 動作；(b) 文件與交接同步則有客戶原文第 3 項為據。**本條不解除任何 Gate／HOLD**，不授權觸發抓取／bootstrap／回補、不授權合併 #1124。

#### DEC-182 範圍外與 NOT VERIFIED

- **NOT VERIFIED**：fence 與客戶原訊息的逐字一致性；Repository 的公開／私有狀態與 Actions 設定（客戶陳述）；GitHub 帳單頁；CI run id 與結論（總管轉述）；#1124～#1126、#1164 的開啟狀態（以 GitHub 為準）。
- 本條 AI 整理單組撰寫，**未經第二組獨立複驗（`CLAUDE.md` §-2 規則 6），不得被引用為「已 QA PASS」**；QA 結果由總管於 PR 補記。

### DEC-183｜客戶 2026-11-14「#1124 發布 Gate 與歷史規則保存」有條件裁示轉錄：#1124 僅進技術放行評估、同 head 原生 CI 由客戶操作、授權與 PIT Gate 不解除、最小外部對帳；Batch 1 規則補登（#1119 Run 保留／#1138 優先序／#1110 資料重用）（2026-11-14；只追加；非 QA PASS；非授權擴張）

> 2026-11-14 補登（ID 取下一個未用號；落盤前 `git grep -n "DEC-183" docs/DECISIONS.md` 0 命中，DEC-182 為上一號）。**來源類別 D：客戶 2026-11-14 訊息，經派工訊息轉錄；原始對話 repo 內 NOT VERIFIED，逐字一致性 NOT VERIFIED**（同 DEC-177～182 的標示方式）。下方 fence 收錄客戶訊息檔的**全文**（含標題、Model／Mode／Effort／Repository 抬頭行、段落間空行），未改一字；fence 內不含首尾 fence 行與結尾換行。fence 內**沒有**任何 Cloud 網址全文；內含的兩個官方頁面網址是客戶訊息自帶（`finmind.github.io`、`help.yahoo.com`、`www.twse.com.tw` 公開頁），不含帳密。
> **sha256 算法**：對 fence 內文（以換行連接各行，不含首尾 fence 行與結尾換行）以 UTF-8 計算，**與 DEC-173～182 同一算法**（本組先以同法重算 DEC-182 的 fence，得 `c1111a7d…f03c1`，與其登記值 `c1111a7d792847ffbd3976530db0227a45ee7a5a0f7559e341b846c8085f03c1` 相符；DEC-181 得 `57ad41cf…66040`，亦相符，後才套用於本條）。
> **本條不是 QA PASS，也不是授權擴張**：客戶原文第一句即「這是有條件授權，不是全面解除 HOLD」。本條下方所有「AI 整理」「核實」「Coverage」皆**單組撰寫，待非作者獨立 QA**（QA 結果由總管於 PR 補記；**本條不得被引用為「已 QA PASS」**）。

> **TL;DR（AI 摘要，非客戶原文；細節以下方全文與 fence 為準）**
>
> | 項 | 一句話 |
> |---|---|
> | 授權了什麼 | #1124 進**技術放行評估**（不是合併）；DPE-5 同 head 原生 CI 驗證（**客戶本人操作**）；唯讀查核公開官方頁面；docs-only 規則補登（#1119／#1138／#1110＋Batch 2） |
> | 沒授權什麼 | #1125／#1126 與 #1124 合併（HOLD）；DG-LIC／DPE-3、DG-PIT 不解除；Merge／Cloud Reboot；AI 代操作；刪分支；新增 API／付費來源／cron／下載／回填；刪任何 Run／Artifact／YAML |
> | 客戶待辦兩件 | ① DPE-5：確認 head SHA、白天操作、Close→Reopen（保留分支）、回報 head SHA＋run id（見 (三)「客戶照做版」）；② 裁示 DG-LIC／DPE-3 與 DG-PIT（CI 全綠不會解除它們） |
> | 仍缺的 Merge Gate | 同 head 原生 CI 全綠；非作者 QA；授權 Gate；PIT Gate；0 unresolved threads；mergeability 合格（客戶原文五項，詳 (二) 2.5） |
> | #1124 資料品質結論 | 內部一致＋部分官方公開頁佐證（twii 收盤 11-09～11-12、外資 11-11／11-13）；**發布層 NOT VERIFIED**；不是「資料已驗證完整」 |
> | 往哪看 | (二) 2.5（Merge Gate 現況）、(三)（客戶操作步驟與風險） |

- **決策者**：**客戶**（2026-11-14，經上述轉錄）。｜**效力日期**：2026-11-14 起。
- **客戶原文（逐字，fence 內未改一字；具約束力）**：fence 內容 sha256＝`11112fda9e5e8161a1fa28d90b3357482e7da5ed4fcaf8532db906e824d9bd8c`（撰寫時計算；尚未由測試釘住）。

```
股票儀表板｜#1124 發布 Gate 與歷史規則保存正式裁示

Model：依 PROJECT_RULES §9 選 Minimum Sufficient Model，建議 Claude Sonnet 5.5
Mode：靜默自主巡航
Effort：High（純文件校驗可降 Medium）

Repository：linchen-20200325/my-stock-dashboard

請 GitHub-first 核對最新 main／Open PR／head SHA／CI／QA／branches／正式 DEC 後，依以下裁示執行。

這是有條件授權，不是全面解除 HOLD。

一、#1124 資料發布

1. DPE-4：同意僅 #1124 進入技術放行評估。

#1125、#1126 維持 HOLD。

#1124 的合併 HOLD 尚未解除，不得擅自 Merge。

2. DPE-5：同意進入同 head 原生 CI 驗證。

由客戶本人在確認最新 head SHA 後，避開既有排程時段，使用既有安全操作方式觸發。

優先評估 Close→Reopen，但不得刪分支；不得由 AI 代替操作、繞過 required checks 或改 branch protection。

若最新 head 已變更，重新檢查差異，舊 QA／CI 不沿用。

若尚未取得本次操作所需的客戶實際操作確認，AI 只提供最小步驟與風險提示，不自行操作。

3. DG-LIC／DPE-3：不解除。

新增需查核的官方證據：

FinMind：
https://finmind.github.io/Disclaimer/

Yahoo Finance：
https://help.yahoo.com/kb/finance/article-exchanges-data-delays-sln2310.html

FinMind 限制原始資料對外再散布；Yahoo Finance 亦有限制再散布的官方聲明。

因 #1124 會把 parquet 提交至公開 repository，應確認完整使用權限、是否屬原始資料再散布、原始來源機關授權及相關例外。

不得把 CI 綠燈、資料為公開資訊或客戶自行承擔風險當成已取得合法授權。

如授權無法確認，保持合併 HOLD，提出合法的最小替代方案；不自行修改資料發布架構。

4. DG-PIT：維持未解除。

11-12 台股 OHLC 通過契約只是資料層合格。

"fetched_at" 不等於來源 "published_at"。沒有權威可得時間證據時不得聲稱 PIT 完整通過。

5. 外資與資料真值：進行最小外部對帳。

ChatGPT 已發現以下參考證據：

- 11-11 外資約 −7.66 億。
- 11-12 外資約 −6.85 億。
- 11-13 官方外資約 +288.37 億。
- 11-12 加權指數收盤 43,091.87。

官方參考：

https://www.twse.com.tw/fund/BFI82U?response=html&type=day

https://www.twse.com.tw/exchangeReport/FMTQIK?response=html

另外，11-11、11-12 數據有公開市場統計支持，並非單純因數字偏小即可判定異常。

請對照最新 #1124 parquet 的日期、欄位、單位、統計口徑與來源；公開網頁的參考資訊不得直接視為分支資料已驗證。

允許唯讀查核公開官方頁面，不授權新增 API、付費來源、cron、下載與回填流程。

6. DG-SCOPE／DG-COV／WIRING-GATE：

本次不涉及新的 UI 程式接線，因此不要求重做 UI 接線工程。

但三個 Gate 原有適用範圍不變，不宣告全面解除；外資／融資資料涉及的正式資料品質與授權限制仍須遵守。

7. Merge／Cloud：暫不授權。

#1124 只有在同 head 原生 CI 全綠、非作者 QA 通過、授權及適用 PIT Gate 解決、0 unresolved threads、mergeability 合格後，才能再提出明確合併請求。

不得自行合併或 Reboot Cloud。

二、正式規則補登：核准最小 docs-only 工作

沿用 PROJECT_RULES §15 的五份 SSOT 職責。

分批處理，每批最多三項，盡量整合為一個最小必要 docs-only PR；若與 #1164 的 BACKLOG／歸檔內容衝突，停止重疊修改，不處置 #1164。

Batch 1：優先正式補登

A. #1119

確認並補登這個使用者決策：

- Actions Run 以最近 30 天作一般保留方向。
- 重要 CI、PIT、Risk Cap、安全、未完成 PR 與重大事故等證據例外保留。
- 不自動變更 GitHub 全域 retention。
- 不可逆刪除須另行逐批明確核准。

本次只授權規則保存，絕不授權刪除任何 Run、Artifact 或 YAML。

原留言 "6822675191" 為 AI 轉述來源，須如實標記原始逐字來源未保存在 repo；本次客戶重新確認的內容可作為新的授權依據，不得冒稱舊留言已逐字查證。

B. #1138

確認「先收尾已授權且可驗收的既有工作，再進一步優化 UI」的工作優先序。

與 DEC-174、175、176、177、178 及更新決策對照。

這項優先序不取消 UI／資料契約雙軌推進；已證明受外部條件阻塞的 HOLD，可以保留追蹤，不必等待其全面解除才能進行其他合法工作。

不重新制定既有 UI Gate。

C. #1110

補強資料架構原則：

GitHub Actions 已可靠取得、驗證並落地的 canonical 資料，UI2 應優先唯讀重用，不應為同一指標無理由在 Streamlit Cloud 再建立一套重複抓取。

這是資料架構方向，不代表禁止任何經核准的 Cloud 取數，也不授權新增 API、cron、adapter 或正式接線。

Batch 2：最小追溯補強

1. #1107：在既有 BACKLOG 補足精簡的 PASS／PARTIAL／NOT VERIFIED 驗收項目，不重抄研究。
2. #1124～#1126：在既有治理或資料發布 Gate 紀錄中，註明自動 PR body 的「關 PR 並刪分支」指示不是客戶授權；不可直接執行不可逆刪除。不修改 publisher 或自動 PR 模板。
3. #1105：查清客戶裁示與 AI 編擬出處不一致，保留原文及證據，必要時用最小勘誤補正；無法確定時標 NOT VERIFIED。

#1042 pandas 2.0.0 相容風險僅列低優先 Candidate，不進本批程式施工。

三、文件 PR 驗收及結案

所有補登遵守：

- 每批最多三項。
- 客戶正式裁示與 AI 推論分開。
- 不重複已有 SSOT。
- 非作者多組獨立 QA。
- 同 head 五項原生 CI 全綠。
- Merge Gate、review threads 及分支保護不繞過。
- 如無新的實質補登，不為湊 PR 製造文件變更。

在內容能忠實追溯、無新 Gate、無越權，且滿足既有 Auto-Ship 規則時，准許合併核准範圍的最小文件 PR。

#1164 維持 Draft。

#1119、#1138、#1116、#1110、#1107 五個 Issues 暫不關閉。

#1124～#1126 維持 Open；#1124 只解除唯讀放行評估及限定的 CI 前置準備限制，沒有合併授權。

四、回報規則

先完成 #1124 最新資料／CI 前置核實，再進行正式規則補登；不得因文件工作延誤必要的資料安全檢查。

只在以下情況回報：

- 客戶必須親自操作 CI。
- 發現阻擋資料發布的實質授權或品質問題。
- 新 Gate／規則衝突需要裁示。
- 一批完成且 CI／QA 有可驗證結論。

完成後報告：

1. #1124 最新 head、CI、QA 和仍缺的 Merge Gate。
2. 已補登的正式規則與 PR／merge SHA。
3. 仍保留的 Open Issues／PR。
4. 唯一下一個安全動作。

沒有取得新資料 PR 合併授權之前，停在 Decision Gate。

開始執行已核准的安全範圍。
```

#### AI 整理（非客戶原文；本組依上方原文逐項對應；**不得據以擴大授權**）

**(一) 裁示逐條轉錄對照表（狀態標示只用「已授權」「維持不授權」「維持 HOLD」三種，外加『不適用』）**

| 客戶原文位置 | 客戶原文要點（節錄；全文以 fence 為準） | 狀態 | 本組備註（AI 整理；不擴張） |
|---|---|---|---|
| 開頭 | 「這是有條件授權，不是全面解除 HOLD。」 | — | 本條全文以此句為總綱；下列任何「已授權」皆限該列字面範圍 |
| 一、1 DPE-4 | 同意**僅 #1124** 進入技術放行評估；#1125、#1126 維持 HOLD；#1124 的合併 HOLD 尚未解除，不得擅自 Merge | **已授權**（僅「#1124 進技術放行評估」）；**維持 HOLD**（#1125、#1126、#1124 合併） | 這是 DEC-179／DEC-181 §S1 待核准項（DPE-4）的**部分**解除，且**僅限評估**；不是合併授權 |
| 一、2 DPE-5 | 同意進入同 head 原生 CI 驗證；由**客戶本人**在確認最新 head SHA 後、避開既有排程時段、用既有安全操作方式觸發；優先評估 Close→Reopen，**不得刪分支**；不得由 AI 代為操作、繞過 required checks 或改 branch protection；head 已變更則重新檢查差異，舊 QA／CI 不沿用；尚未取得客戶實際操作確認時，AI 只提供最小步驟與風險 | **已授權**（進入同 head 原生 CI 驗證，**操作者＝客戶本人**）；AI 代操作＝**維持不授權** | 客戶實際操作確認**尚未取得**（截至本條撰寫）→ AI 只提供步驟與風險，見 (三)。Close→Reopen 只是「優先評估」，不是指定 |
| 一、3 DG-LIC／DPE-3 | 不解除；新增需查核官方證據（FinMind、Yahoo Finance 兩頁）；因 #1124 會把 parquet 提交至公開 repository，應確認完整使用權限、是否屬原始資料再散布、原始來源機關授權及相關例外；不得把 CI 綠燈、資料為公開資訊或客戶自行承擔風險當成已取得合法授權；授權無法確認則保持合併 HOLD、提出合法最小替代方案、不自行修改資料發布架構 | **維持不授權／維持 HOLD** | 兩頁已唯讀查核，見 (二) 2.4；**結論仍是授權未確認**，替代方案只列不實作，見 (二) 2.6 |
| 一、4 DG-PIT | 維持未解除；11-12 台股 OHLC 通過契約只是資料層合格；`fetched_at` 不等於來源 `published_at`；無權威可得時間證據不得聲稱 PIT 完整通過 | **維持 HOLD** | #1124 PR body 自身寫 `published_at`＝n/a（來源未提供）；本組未取得任何權威可得時間證據 |
| 一、5 外資與資料真值 | 進行最小外部對帳（客戶列四個參考值與兩個官方頁網址）；對照最新 #1124 parquet 的日期、欄位、單位、統計口徑與來源；公開網頁參考資訊不得直接視為分支資料已驗證；允許**唯讀查核公開官方頁面**，**不授權新增 API、付費來源、cron、下載與回填流程** | **已授權**（僅唯讀查核公開官方頁面）；新增 API／付費來源／cron／下載／回填＝**維持不授權** | 已執行，結果見 (二) 2.3；本組只讀取兩個官方網頁，頁面全文存 scratchpad，**未進 repo** |
| 一、6 DG-SCOPE／DG-COV／WIRING-GATE | 本次不涉及新的 UI 程式接線，不要求重做 UI 接線工程；三個 Gate 原有適用範圍不變，不宣告全面解除；外資／融資資料涉及的正式資料品質與授權限制仍須遵守 | **不適用**（本次不重做接線）；Gate 範圍＝**維持原狀** | 不是「這三個 Gate 已解除」；只是本次沒有 UI 接線工作要過它們 |
| 一、7 Merge／Cloud | 暫不授權；#1124 僅在「同 head 原生 CI 全綠、非作者 QA 通過、授權及適用 PIT Gate 解決、0 unresolved threads、mergeability 合格」後才能**再提出明確合併請求**；不得自行合併或 Reboot Cloud | **維持不授權** | 上列五項前提（客戶原文五項；(二) 2.5 表為便於核對，將『授權及適用 PIT Gate 解決』拆為兩列，共六列）是「才能再提出請求」的條件，**不是**達成即自動授權 |
| 二（總綱） | 沿用 PROJECT_RULES §15 五份 SSOT 職責；分批、每批最多三項、盡量整合為一個最小必要 docs-only PR；若與 #1164 的 BACKLOG／歸檔內容衝突，停止重疊修改，不處置 #1164 | **已授權**（docs-only 規則補登，限下列 A／B／C 與 Batch 2 字面範圍） | #1164 衝突檢查已做：無重疊，見 (六) |
| 二、Batch 1 A（#1119） | 確認並補登四點使用者決策（30 天一般保留方向；重要 CI／PIT／Risk Cap／安全／未完成 PR／重大事故等證據例外保留；不自動變更 GitHub 全域 retention；不可逆刪除須另行逐批明確核准）；**本次只授權規則保存，絕不授權刪除任何 Run、Artifact 或 YAML**；舊留言 6822675191 為 AI 轉述來源，須如實標記；客戶本次重新確認可作新授權依據，不得冒稱舊留言已逐字查證 | **已授權**（僅規則保存）；刪除任何 Run／Artifact／YAML＝**維持不授權** | 見 (五) A |
| 二、Batch 1 B（#1138） | 確認「先收尾已授權且可驗收的既有工作，再進一步優化 UI」的工作優先序；與 DEC-174、175、176、177、178 及更新決策對照；不取消 UI／資料契約雙軌推進；已證明受外部條件阻塞的 HOLD 可保留追蹤，不必等其全面解除才進行其他合法工作；不重新制定既有 UI Gate | **已授權**（僅規則保存與對照） | 見 (五) B |
| 二、Batch 1 C（#1110） | 補強資料架構原則：GitHub Actions 已可靠取得、驗證並落地的 canonical 資料，UI2 應優先唯讀重用，不應為同一指標無理由在 Streamlit Cloud 再建立重複抓取；不禁止經核准的 Cloud 取數；不授權新增 API／cron／adapter／正式接線 | **已授權**（僅規則保存）；新增 API／cron／adapter／正式接線＝**維持不授權** | 見 (五) C |
| 二、Batch 2 第 1 項（#1107） | 在既有 BACKLOG 補足精簡 PASS／PARTIAL／NOT VERIFIED 驗收項目，不重抄研究 | **已授權**（docs-only） | 另一個 commit（Batch 2）；見本條後「DEC-183 後續註記（Batch 2）」 |
| 二、Batch 2 第 2 項（#1124～#1126 PR body 警語） | 註明自動 PR body「關 PR 並刪分支」指示不是客戶授權；不可直接執行不可逆刪除；**不修改 publisher 或自動 PR 模板** | **已授權**（僅註記）；改 publisher／PR 模板＝**維持不授權** | 同上（Batch 2） |
| 二、Batch 2 第 3 項（#1105） | 查清客戶裁示與 AI 編擬出處不一致，保留原文及證據，必要時最小勘誤；無法確定標 NOT VERIFIED | **已授權**（僅最小勘誤） | 同上（Batch 2） |
| 二、#1042 | pandas 2.0.0 相容風險僅列低優先 Candidate，不進本批程式施工 | **已授權**（僅登 Candidate）；程式施工＝**維持不授權** | 同上（Batch 2） |
| 三 驗收規則 | 每批最多三項；客戶正式裁示與 AI 推論分開；不重複已有 SSOT；非作者多組獨立 QA；同 head 五項原生 CI 全綠；Merge Gate、review threads 及分支保護不繞過；無新的實質補登則不為湊 PR 製造文件變更；內容能忠實追溯、無新 Gate、無越權且滿足既有 Auto-Ship 規則時，**准許合併核准範圍的最小文件 PR** | **已授權**（限「核准範圍的最小文件 PR」，且須全部條件成立）；#1124～#1126、#1164 不在此列 | 合併動作由總管依既有 Auto-Ship 條件判斷；本條**不代表**該 PR 已通過任何驗收 |
| 三（Issues／PR 處置） | #1164 維持 Draft；#1119、#1138、#1116、#1110、#1107 五個 Issues 暫不關閉；#1124～#1126 維持 Open；#1124 只解除唯讀放行評估及限定的 CI 前置準備限制，沒有合併授權 | **維持不授權**（關閉 Issues／處置 #1164）；**維持 HOLD**（#1124 合併） | 本批對五個 Issues 只追加紀錄，不建議結案 |
| 四 回報規則 | 先完成 #1124 最新資料／CI 前置核實，再進行正式規則補登；僅在四種情況回報；完成後報告四項；沒有新資料 PR 合併授權前停在 Decision Gate | 流程指示（非授權） | 本條 (二) 即該核實；仍須客戶親自操作 CI，故屬回報情況之一 |

**補充（INFERENCE）**：客戶一、5 的唯讀公開頁最小外部對帳，為對 DPE-3＝D（DEC-179：先確認來源條款）的**明示、限唯讀公開頁的局部例外**（本組解讀）；`DG-LIC`／DPE-3 仍未解除，B（正式對帳）仍待條款確認後另行明示。

**方案代號／選項字母防混淆（寫死；引用本條時一律須帶 DEC 編號）**
- 本條 DPE-4 的「同意僅 #1124 進入技術放行評估」，在 DEC-181 (五) 的記法是「DPE-4＝B（**僅 #1124**）」——那是 AI 在 DEC-179／DEC-181 提出的**變體**，**不是** GAPS 文件（`DATA_PR_EVIDENCE_GAPS…`）原 DPE-4 選項 B（#1124＋#1125 範本）的全案；客戶本條原文**沒有寫字母**，字母對應是本組解讀（INFERENCE）。**#1125、#1126 維持 HOLD。**
- DPE-5 在此＝「同 head 原生 CI 驗證，由客戶本人操作」，與 DEC-170 的 CI 環境修復「方案 A→B」、DEC-174 的「方案 B＝雙軌」、DEC-171 的「同意方案 B＝資料曝露唯讀稽核」皆**不同義**。
- DG-LIC 在此仍是「呈現／再散布授權」，與 DPE-3（外部對帳條款）互相關聯但不同；本條兩者都**不解除**。「DPE-3＝D」（DEC-179：先確認來源條款）的狀態**不因本條改變**。

**(二) #1124 最新核實（單組；事實層級分開；本批唯讀；未觸發任何抓取／CI／workflow；時點 2026-11-14 約 08:00～08:30 台北，會漂移，一律重查）**

*2.1 發布層（GitHub 讀取＋本地 ref；FACT 為讀取當下）*

- PR #1124：`state`＝open、非草稿、`merged`＝false、`mergeable_state`＝blocked；head `f87866eda26d40cef66dd8107e25eff52a16333a`（分支 `auto/data-macro-history`，最後 commit 時間 2026-11-13T17:03:55Z〔`git` 實查〕）；base `main` `d607acb8dd51c80e5316f525f22817b80e3a09f9`；7 commits、5 changed files、+9／−9；PR 作者＝`github-actions[bot]`。
- **該 head 的 check runs＝0**（`get_check_runs` 讀取）。該 head 唯一已見 workflow run＝`43469025728`（`event`＝pull_request、發起者 `github-actions[bot]`、`conclusion`＝`action_required`；本組以 `get_workflow_run` 讀取，**未列 jobs**〔素材稱 jobs＝0，本組未另重取〕）。**`action_required` 是 Actions 核准機制，不是 CI 失敗，也不是 CI 通過；設定本身 NOT VERIFIED。**
- main push CI `43447327744`（head `d607acb8`，`event`＝push）：`completed`／`success`（本組以 `get_workflow_run` 讀取）。**CI success ≠ 資料已更新 ≠ Production 有效。**
- #1124 PR body 自述：`published_at`（來源發布時間）＝n/a（來源未提供）；`fetched_at`＝2026-11-13T17:03:47.560404+00:00；各檔最後資料日：`finmind_inst`／`finmind_margin` 2026-11-13、`twii_ohlcv` 2026-11-12。

*2.2 資料層檢核（本組以 `git show` 取 `origin/main` 與 `f87866ed` 的 blob，pyarrow 讀取；FACT）*

- 變更檔恰為 5 個：`data_cache/finmind_inst.parquet`、`finmind_margin.parquet`、`macro_last_good/tw_pmi.json`、`metadata.json`、`twii_ohlcv.parquet`（`git diff --stat origin/main f87866ed` 實查：9 insertions、9 deletions）。無程式、測試、workflow。
- 三個 parquet 與 `origin/main` 的**重疊列全欄位（含 `source`、`fetched_at`）零差異**；新增列 `twii_ohlcv` 4913→4916（11-10、11-11、11-12）、`finmind_inst`／`finmind_margin` 4939→4943（11-10～11-13）。schema 相同（`twii_ohlcv`：date、open、high、low、close、volume、source、fetched_at）。
- `metadata.json` 的 `row_count`／`last_updated` 與 parquet 一致（twii 4916／2026-11-12；inst、margin 4943／2026-11-13）；`finmind_m1m2`＝`NO_NEW_DATA`、`tw_pmi`＝`UNDETERMINED` 原樣保留（非本 PR 造成）。
- `twii_ohlcv` 11-10 的 `volume`：commit `d0f14437` 為空、`fc447def` 起為 4,766,000，列內 `fetched_at` 仍為首次寫入時間（2026-11-10T16:55:08.780479+00:00；兩個 blob 本組皆已讀）→ `fetched_at` 不代表列內各欄一次定稿（已登 BACKLOG `DEC181-TWII-PIT-VOLUME-BACKFILL-OBS`）。
- 新列 `fetched_at`（UTC 時間戳字串，已讀）換算台北：11-10 列＝11-11 00:55、11-11 列＝11-13 01:29、11-12 列＝11-14 01:03 —— 皆晚於各自交易日 17:00。**這只是 `fetched_at`（抓取時間），不是 `published_at`（來源發布時間）**，不能據以宣稱 PIT 通過（DG-PIT 維持）。
- `shared/twii_ohlc_contract.py` 契約：素材稱獨立兩組重驗整窗通過；**本組未重跑**（不執行 repo 腳本），以 NOT VERIFIED 登記，僅引用。`twii` 缺 11-13 屬預期（Yahoo T+1 規律，INFERENCE）；交易日曆 NOT VERIFIED（G-07）。

*2.3 官方對帳（客戶本批授權的最小外部對帳；唯讀讀取證交所公開頁；**只描述「與官方公開頁的逐日對照」，不是「資料已驗證完整」**）*

(a) 發行量加權股價指數：證交所 FMTQIK 頁（頁面標題「115年11月市場成交資訊」）vs `twii_ohlcv.close`（f87866ed）

| 日期 | FMTQIK 發行量加權股價指數 | parquet `close` | 對照結果 |
|---|---|---|---|
| 2026-11-09 | 41,661.70 | 41661.699219 | 相符（至小數 2 位） |
| 2026-11-10 | 42,711.92 | 42711.921875 | 相符 |
| 2026-11-11 | 44,257.15 | 44257.148438 | 相符 |
| 2026-11-12 | 43,091.87 | 43091.87109375 | 相符（與客戶參考值 43,091.87 一致） |
| 2026-11-13 | 43,675.12 | （分支無此列） | 官方頁有值；分支缺列屬預期，非對照失敗 |

另：11-05（41,574.72）、11-06（39,701.64）亦與分支既有列相符（本組順帶比對，非客戶要求範圍）。FMTQIK 頁不含高、低、開價，**開高低未對帳**。

(b) 成交量：FMTQIK「成交股數」vs `twii_ohlcv.volume`

| 日期 | FMTQIK 成交股數 | parquet `volume` | 比值 |
|---|---|---|---|
| 2026-11-10 | 12,827,159,729 | 4,766,000 | 約 2,691 |
| 2026-11-11 | 11,518,562,054 | 4,012,900 | 約 2,870 |
| 2026-11-12 | 13,624,025,071 | 5,242,800 | 約 2,599 |

比值**非常數** → **parquet 的 `volume` 不是證交所成交股數**，其定義 NOT VERIFIED；UI2 的日 K 讀取不含 `volume`（`src/data/macro/macro_cache_reader.py` `TWII_OHLC_COLUMNS`＝open／high／low／close／fetched_at，本組實查）。對照 `CLAUDE.md` §1.A 第 1 點「加權指數日 K 成交量全為 0 → 隱藏該欄」：本批 `volume` 非全 0，該點不適用，但**不得把此欄當成交股數使用**。

(c) 外資：證交所 BFI82U「三大法人買賣金額統計表」列「外資及陸資(不含外資自營商)」（單位元）vs `finmind_inst.foreign_buy`

| 日期 | 官方買進（元） | 官方賣出（元） | 官方買賣差額（元） | 換算（÷1e8，億元） | parquet `foreign_buy` | 結果 |
|---|---|---|---|---|---|---|
| 2026-11-11 | 339,713,407,087 | 340,479,850,423 | −766,443,336 | −7.66443336 | −7.66443336 | **逐位相符** |
| 2026-11-13 | 378,483,644,345 | 349,646,958,294 | +28,836,686,051 | +288.36686051 | +288.36686051 | **逐位相符** |
| 2026-11-12 | **未取得** | | | | −6.84503883 | 客戶參考值「約 −6.85 億」與分支值量級一致，但那是**客戶提供的參考值，不是本批驗證**；官方值 NOT VERIFIED |
| 2026-11-10 | **未取得** | | | | −341.16689906 | 官方值 NOT VERIFIED（客戶未列此日） |

兩個已取得日期上，「外資自營商」列皆為 0；單位推論 `foreign_buy`＝外資及陸資(不含外資自營商)買賣差額÷1e8（兩個日期精確吻合；INFERENCE 高信心，**只限這兩日**）。**客戶所述「11-11、11-12 數據有公開市場統計支持，並非單純因數字偏小即可判定異常」，就 11-11 已獲官方公開頁佐證；11-12 仍未取得官方值。** `DEC181-INST-1111-1112-ANOMALY` 所列「量級離群＝可疑」的前提因此被削弱（11-11 不是資料錯誤的證據）；其 NOT VERIFIED 部分（11-12 官方值、歷史上其他 \|值\|<10 列）仍在。

(d) 證交所公開頁對本組部分請求回傳安全封鎖頁（**事實描述；不下因果與法律結論**）：本組對指定 11-12、11-13 日的 BFI82U 請求，伺服器回傳 947 byte 的固定頁，文字為「因為安全性考量，您所執行的頁面無法呈現（FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED）」；11-11 指定日與不帶指定日期的最新日請求則成功。**原因 NOT VERIFIED（可能與請求頻率有關，屬推論）**；本組在觸發後**停止重試**（不繞過、不換來源）。11-13 的內容由不帶指定日期的「最新」頁取得（頁面標題「115年11月13日 三大法人買賣金額統計表」）。此事實是否與 DG-LIC／DPE-3 的自動化存取條款議題有關，NOT VERIFIED；**證交所『交易資訊使用管理辦法』全文本批未讀到**。封鎖頁內的錯誤代碼與 IP 回顯**不登錄**。

(e) 融資（`finmind_margin`）：客戶未提供官方頁，**未對帳**；結構檢核通過、真值 NOT VERIFIED。

(f) 結論（單組；**非 QA PASS**）：**資料層＝內部一致，加部分外部佐證**（twii 收盤 11-09～11-12、inst 外資 11-11 與 11-13 已與證交所公開頁逐日對照相符）；**發布層＝NOT VERIFIED**（check runs＝0、`action_required`、無 head CI）；**授權（DG-LIC／DPE-3）與 PIT（DG-PIT）Gate 未解除**。仍 NOT VERIFIED：11-12 與 11-10 外資官方值、`volume` 語意、margin 真值、交易日曆、`published_at`。

*2.4 授權官方頁面（客戶本條新增需查核；本組唯讀讀取，頁面全文存 scratchpad，不進 repo）*

- **FinMind「免責聲明與資料授權說明」**（`finmind.github.io/Disclaimer/`；頁面載明版本日期 2026-10-31，與先前記載版本相同，此次是直接讀官方頁）。逐字關鍵句：「本服務之授權不包含將本服務提供之資料對外再散布、轉售，或建置實質等同於本服務之鏡像服務。」；「使用者如有將資料對外公開、再散布或提供予第三方之需求，應自行確認並取得原資料來源機關所要求之相應授權；此類授權非 FinMind 所能授予或代為取得。」；「FinMind 之合法使用基礎為上述公開授權架構，以及與資料來源機關另行簽訂之資訊使用契約；FinMind 不代表任何來源機關之立場。」；「本服務所提供之臺灣證券交易所交易資訊，資訊來源：臺灣證券交易所「TWSE」，本資訊由芬麥數據股份有限公司處理提供。」；「使用者須遵守臺灣證券交易所『交易資訊使用管理辦法』等交易資訊管理相關規定。」；「使用者如將透過本服務取得之資料用於對外用途，亦應依相關授權條款，以適當方式標示原資料提供機關。」；「本文件如與 FinMind 使用條款有歧異，以使用條款為準。」——**FinMind 使用條款本身未讀（NOT VERIFIED）**。
- **Yahoo Finance「Exchanges and data providers」說明頁**（`help.yahoo.com/kb/finance/article-exchanges-data-delays-sln2310.html`；本組抓取文字中未見頁面日期，NOT VERIFIED）。逐字關鍵句：「Do not redistribute information - Yahoo Finance provides all information as is. You must not redistribute information displayed on or provided by Yahoo Finance.」。表列 Taiwan Stock Exchange (TWSE) 後綴 `.TW` 延遲 20 min、Taiwan OTC Exchange `.TWO` 延遲 20 min，資料提供者皆為 ICE Data Services；表中**未見** `^TWII` 指數列 → 該列是否適用於本專案取數的 `^TWII` chart 端點＝NOT VERIFIED。這是說明頁，**不是服務條款全文**；Yahoo 完整服務條款未讀（NOT VERIFIED）。
- **判斷（INFERENCE，不下法律結論）**：兩家官方頁都含「不得再散布」類聲明；#1124 會把 Yahoo／FinMind 來源的 parquet 提交到**公開** repository；故 **DG-LIC／DPE-3 不能由 CI 綠燈、資料為公開資訊或客戶自行承擔風險解除**（此點與客戶原文一致，非本組新增）。證交所原始來源機關的授權／「交易資訊使用管理辦法」仍**零原文**。**DG-LIC／DPE-3 不解除。**

*2.5 仍缺的 Merge Gate（客戶原文一、7，原文五項，本表為便於核對拆為六列；逐項現況，不是授權）*

| 客戶要求的前提 | 現況 |
|---|---|
| 同 head 原生 CI 全綠 | **未達**：head `f87866ed` 的 check runs＝0；待客戶 DPE-5 操作 |
| 非作者 QA 通過 | **未達**：本條 (二) 為單組檢核；#1124 的非作者 QA 須在最終 head 上做（head 漂移則重做） |
| 授權（DG-LIC／DPE-3）解決 | **未達**：見 2.4 |
| 適用 PIT Gate 解決（DG-PIT） | **未達**：`published_at`＝n/a；`fetched_at`≠`published_at` |
| 0 unresolved threads | 本組未重查 review threads（NOT VERIFIED；以 GitHub 為準） |
| mergeability 合格 | **未達**：`mergeable_state`＝blocked（讀取當下） |

*2.6 授權無法確認時的「合法最小替代方案」（客戶原文一、3 要求提出；**只列不實作，不自行修改資料發布架構**，皆待客戶／法務）*

(a) 維持合併 HOLD，等 DPE-3 條款確認（現狀）；(b) 向來源機關／法務取得書面確認後再放行；(c) 不把個股級／原始序列提交公開 repository，改只發布衍生／聚合指標，或把資料放私有儲存庫／私有分支（涉及資料契約與發布架構變更，需另案裁示，DEC-156 邊界）；(d) 讓 UI2 台股卡維持走現狀 main 既有路徑（現為 11-09）直到 (b) 完成（註：依 DEC-181，11-17 起該卡 `age_days`＝8 轉過期警示，時點會漂移）。以上為 AI 列舉，**不是推薦已被採納，也不是客戶裁示**。

**(三) DPE-5 客戶操作最小步驟與風險（AI 不代做；客戶實際操作確認尚未取得）**

| 步驟 | 內容 |
|---|---|
| S-a | 在 PR #1124 頁確認**最新 head SHA**，並與審閱用 SHA 一致（本條撰寫時為 `f87866ed`；cron 會推進，一律重查） |
| S-b | **避開排程時段**：`update_macro_history.yml` 的 cron 為 UTC 09:00（台北 17:00），但實際常延遲數小時；DEC-181 (四) 的預期窗約台北 23:30～03:45。**建議白天操作**。（延遲 6.5～10.7 小時為素材觀察值，本組未重驗） |
| S-c | 優先評估 **Close→Reopen**；**保留分支，不得刪分支**。若改用 Update branch 會產生**新 head**（merge main），須在新 head 重做審閱與 CI |
| S-d | 觀察該 head 的 `pull_request` run 是否出現 `ui2-browser-gate` 與五項檢查，且 head SHA 與 S-a 相符 |
| S-e | 若 Close 期間排程剛好執行，bot 可能另開新 PR（找不到 open PR 時請回報），屆時回報，不要自行處理 |
| S-f | 完成後回報「**head SHA＋run id**」，AI 才能做同 head 審閱 |

**風險**：head 漂移使 CI／審閱失效（舊 QA／CI 不沿用，客戶原文）；Close 期間分支仍在但 PR 暫非 open；Reopen 後以客戶帳號觸發的 `pull_request` 事件是否真的跑完 `ui2-browser-gate`，先例為 #1103（見 Batch 2 勘誤：該次執行者出處 NOT VERIFIED）。**不得**刪分支、不得繞過 required checks、不得改 branch protection、不得由 AI 代操作。**客戶同時需要處理的是 DG-LIC／DPE-3 與 DG-PIT 的裁示——CI 全綠不會解除它們。**

**客戶照做版（AI 提供的最小步驟與風險提示，**不是 AI 操作**；沿用 #1103 先例，該次執行者出處 NOT VERIFIED）**
1. 建議操作時段：台北 08:00–16:00（避開排程時段）。
2. 開 PR #1124 頁，核對 head SHA（撰寫時為 `f87866ed`，會漂移）。
3. 頁面底部按 Close pull request，**立刻** Reopen pull request（**保留分支、不刪分支**）。
4. 到 Actions 找 PR Check（pytest fast + AppTest slow）、`event`＝pull_request 的 run；run id＝網址 `/actions/runs/` 後的數字。
5. 確認該 head 出現 `ui2-browser-gate` 與五項檢查。
6. 回報「head SHA＋run id＋結果」。
7. 若 head 在你操作前後改變（分支 commit 變多）→回報新 head，AI 重做審閱；若出現 `action_required`／jobs 0／沒有 `ui2-browser-gate`→**不要重複 Close／Reopen**，回報現象與時間；若 Close 期間 bot 另開了新 PR→回報。

**head 穩定性預期（INFERENCE，未實測）**：2026-11-14（六）、11-15（日）無新交易日時，依 `publish_data_pr.py` 揮發鍵規則（僅揮發欄位變動時不開 PR／不 commit，見 DEC-181），#1124 head 預期穩定；11-16（一）起排程可能帶入新列使 head 前進。

**(四) 環境設定事實（據實登記；非 Secrets、非 Actions 預算、非 Branch Protection 的變更）**

為讀取客戶授權的公開官方頁面，經 session 內核准提示，建立個人（personal）環境（名稱同專案；環境識別碼不登錄），並**僅**允許三個主機：`www.twse.com.tw`、`finmind.github.io`、`help.yahoo.com`（外加預設的套件源／MCP 主機）。原預設環境 Default 的允許主機為 `data.sec.gov`、`www.sec.gov`，與本專案無關，未使用。此為執行環境的網路白名單設定，**不是**專案 Secrets／Actions 預算／Branch Protection／NAS／Cloud 設定的變更；本批**未**觸發任何 workflow／CI／抓取／回填，**未** merge／close／reopen／rebase／update branch 任何 PR。

**(五) Batch 1 Coverage 結論與本次補登內容（A／B／C；每項：Source｜Type｜Current SSOT｜Coverage｜補登內容｜來源鏈限制）**

*通則（來源鏈）*：舊 GitHub 留言一律是**AI 轉述／AI 稽核報告**，客戶逐字原話不在 repo；**客戶本次（2026-11-14）重新確認的內容才是本條的新授權依據**，且本條自身也只是「經派工訊息轉錄、逐字 NOT VERIFIED」。以下不冒稱舊留言已逐字查證。

**A. #1119 Actions Run 保留規則**

| 欄 | 內容 |
|---|---|
| Source | (1) 客戶本條原文二、Batch 1 A（本次重新確認，**新授權依據**）；(2) 舊來源：Issue #1119 留言 `6822675191`（2026-11-12T11:44:11Z；作者帳號 `linchen-20200325`〔`author_association`＝OWNER〕；抬頭「客戶裁示｜Actions Run 歷史紀錄 30 天保留方案：第一輪唯讀稽核（2026-11-12）」；本組以 `issue_read get_comments` 逐字讀取）；(3) 留言 `6768487486`（2026-11-10T13:24:03Z，同帳號，「Action等儀表板好了 刪死碼時候再一起刪除」，已在 DECISIONS 約 L7999 登記）|
| Type | (1) 客戶裁示（經派工訊息轉錄）；(2) **AI 撰寫的稽核報告**（內容為 3,034／2,032／1,002 等統計與 C1～C3 候選，文風為稽核報告；『客戶明確選擇：保留最近 30 天…』一句是**轉述**，客戶原話不在 repo；**實際撰寫者 NOT VERIFIED**〔帳號為 OWNER，但本組只能就內容推論為 AI 撰寫，INFERENCE〕）|
| Current SSOT | `docs/DECISIONS.md`：DEC-175（Actions 清理延到收尾；其註記約 L8423 僅把留言 `6822675191` 當「脈絡佐證、未證實等同」）、DEC-179 禁止清單（約 L9227）含「清理 #1119 Actions」（DEC-180～182 禁止清單同類條目，本組未逐條重核）；`docs/BACKLOG.md` `WORKFLOW-SLIM-AUDIT-1`、`DEC175-CLEANUP-DEFER`；`PROJECT_RULES.md`（延後與逐批授權索引，約 L1157）。本組 grep：`保留最近 30 天`、`30 天保留` 等**作為決策規則**在正式 SSOT 中無登錄（僅 DEC-175 註記與 crosswalk 底稿提到留言標題）|
| Coverage | 19 YAML 延後＝**完整保存**；30 天一般保留方向＝**缺漏**；例外保護清單＝**缺漏**；不改全域 retention＝**缺漏**；不可逆刪除逐批核准＝**部分保存**（DEC-175 等寫「延後、不執行刪除」，但無「逐批明確核准」成文規則）|
| 補登內容 | 依客戶本次原文，登記四點：① **Run 歷史以最近 30 天為一般保留方向**（方向，不是已執行的刪除規則）；② **例外保留**：客戶本次列示「重要 CI、PIT、Risk Cap、安全、未完成 PR 與重大事故」等證據；舊留言（AI 轉述）較詳細列出的保護類（未合併 PR 的所有 run、DEC／Gate 可回查的 run ID、WIF 權限、重大 fail 與首次成功／修復基線、資料寫入或真實發布驗證、唯一證據 artifact）**列為參考，不當成客戶已逐項確認的清單**——其中「重大事故」只見於客戶本次原文，舊留言抬頭未出現同詞；③ **不自動變更 GitHub 全域 retention**（舊留言並稱：在完成獨立封存與客戶再次裁示前不得更改全域 retention，並引 GitHub Docs 說明改設定不追溯已存在紀錄；該官方文件說明為舊留言所引，**本組未重讀 GitHub Docs**，NOT VERIFIED）；④ **不可逆刪除須另行逐批明確核准**。**BACKLOG 新列 `RUN-RETENTION-30D-HOLD`（deferred）**。不重抄舊留言的統計數字（AI 當時的時點快照，會漂移）|
| 來源鏈限制 | 舊留言＝AI 轉述，不冒稱逐字查證；客戶本次重新確認＝新授權依據；本條只授權「規則保存」|
| **不授權** | 刪除任何 Run、Artifact、YAML；變更全域 retention；執行任何清理腳本；把 30 天界線當成「2,032 筆可刪」。workflow YAML 清理與 Run 歷史清理是**兩件事**（crosswalk 底稿已區分），兩者目前都**沒有刪除授權** |

**B. #1138 工作優先序**

| 欄 | 內容 |
|---|---|
| Source | (1) 客戶本條原文二、Batch 1 B（**新授權依據**）；(2) 舊來源：Issue #1138 留言 `6818780219`（2026-11-12T08:34:08Z；作者帳號 OWNER；抬頭「客戶最新優先順序裁示｜2026-11-12（依本次 ChatGPT 對話直接轉錄意旨）」；本組逐字讀取）|
| Type | (1) 客戶裁示（經派工訊息轉錄）；(2) 轉錄者整理：客戶逐字**只有**被該留言引用的一句「好 我希望把這些項目完成後，再來繼續優化UI」（引文來源為該留言自身，原始對話 repo 內 NOT VERIFIED）；其「第一階段」「第二階段」清單與條件是**轉錄者整理**|
| Current SSOT | `docs/vnext/UI2_OPEN_ISSUES_PR_SSOT_CROSSWALK_2026-11-12.md` 約 L66（底稿，**自述非正式**）；DEC-174／175／176／177／178／179～182 各自的優先序敘述（見下表）。**留言本身未成為 DEC**|
| Coverage | **部分保存→本批補登**：優先序意旨散見於 DEC-174～182，但「先收尾已授權且可驗收的既有工作，再進一步優化 UI」這句裁示本身與其和既有 DEC 的關係，無單一正式落點 |
| 補登內容 | 優先序：**先收尾已授權且可驗收的既有工作 → 再繼續進一步優化 UI**；**不取消 UI／資料契約雙軌推進**（DEC-174）；**已證明受外部條件阻塞的 HOLD 可保留追蹤，不必等待其全面解除才進行其他合法工作**；**不重新制定既有 UI Gate**（Gate 原樣：文字線框草稿先行、G-1～G-10 等仍依各 DEC）。**BACKLOG 新列 `UI2-1138-PRIORITY-RULE`（結論列，非工作項）**；並在新列追加一行註記：#1139 已合併（見下）|
| 來源鏈限制 | 舊留言的第一／第二階段清單是轉錄者整理，**不是客戶逐項點名**；其「第二階段條件」在後續 DEC 中**未被引用也未被取代**（本組 grep `第二階段` 在 DECISIONS 僅命中 DEC-178 的另一個「第二階段：六項品質補強」，與該留言無關；INFERENCE）|

與既有決策的對照（INFERENCE；標「兼容／補充／無關」；本組依標題與已讀段落判讀，DEC-178 只抽讀）：

| DEC | 相關內容 | 與本次優先序的關係 |
|---|---|---|
| DEC-164（2026-11-11） | G-1～G-10 正式裁示、融資＋板塊唯讀 L3 與兩項獨立安全修復授權 | **無關／兼容**：早於優先序留言；其授權範圍不因本序改變。本組**未逐項核對**其各授權項是否已完成 |
| DEC-174（2026-11-12） | UI 與資料契約**雙軌推進**，每批最多三項，不突破既有資料及接線 Gate | **兼容（補充）**：客戶本次明寫「不取消雙軌」；本序只補「同批內先收尾再優化」的順序 |
| DEC-175（2026-11-12） | 先處理 UI＋資料庫；Actions／死碼清理延後到最後；跨對話持續落盤 | **兼容**：本序的「收尾」不含 Actions 清理（該項仍延後，見 A）|
| DEC-176(c)（2026-11-12） | DEC-175 是已生效的優先序／架構／交接治理，**不是**無條件施工授權 | **兼容**：同理，本序也**不是**施工授權 |
| DEC-177（2026-11-12） | UI 主線恢復，允許最小 UI 第一版實作、不解除任何 Gate，預防性交接 | **補充**：UI 主線「恢復」的時機＝本序「收尾後」；Gate 不變 |
| DEC-178（2026-11-13） | 三個專業 Agent、六項品質補強分三批 | **兼容／無關**（抽讀）：品質補強屬「收尾」類工作；未見衝突 |
| DEC-179～DEC-182（2026-11-13） | 資料優先、#1124～#1126 維持 HOLD、DPE-3＝D、DPE-6＝B、更新程序規劃、Actions 可用性澄清 | **兼容**：這些 HOLD 正是「已證明受外部條件阻塞者」的實例，可保留追蹤；本序同意不必等其解除才做其他合法工作 |
| DEC-183（本條）一 | #1124 僅進技術放行評估等 | **兼容**：同為「HOLD 保留追蹤、其餘合法工作照做」|

結論：**未發現與 DEC-174～182 的真正衝突**（單組 INFERENCE，待非作者 QA）。

**陳舊事實註記（只追加，不改舊行）**：HANDOFF 約 L237–248 與 BACKLOG 約 L2163 的 Issue #1138 段仍寫「PR 號待補」；**#1139 已併入 main**（`ba9821f3`，commit 時間 2026-11-11T16:45:40+08:00；`git log` 實查）。稽核組另指測試數（31／27 vs 35／27）不一致——**本組未重數**，NOT VERIFIED。

**C. #1110 資料架構原則（GitHub canonical 資料 UI2 優先唯讀重用）**

| 欄 | 內容 |
|---|---|
| Source | (1) 客戶本條原文二、Batch 1 C（**新授權依據**）；(2) 舊來源：Issue #1110 留言 `6765231976`（2026-11-10T10:40:52Z；作者帳號 OWNER；抬頭「2026-11-10 GitHub-first 唯讀稽核補充：GitHub 取數優先、Cloud 不重複認證（研究，不是施工授權）」；本組逐字讀取）|
| Type | (1) 客戶裁示（經派工訊息轉錄）；(2) AI 研究留言：其「客戶方向：若 GitHub Actions 已可使用 API Key 取得、驗證並落地資料，New UI2 不必另以 Streamlit Cloud Secret 重複連外取得同一份資料」是 **AI 對客戶方向的釋義**，客戶逐字 NOT VERIFIED；同一留言載明「方向性同意不等於授權新增來源／cron／改寫正式公式／OneBrain／Risk Cap」|
| Current SSOT | 僅 `docs/vnext/UI2_OPEN_ISSUES_PR_SSOT_CROSSWALK_2026-11-12.md` 約 L68（釋義，底稿）；結構面有 G2F 守衛（`tests/test_ui2_guards.py` `G2F_IMPORT_ALLOWLIST`）、DEC-180（New UI2 不用 NAS 是設計）、DEC-182 禁止「直接讓 New UI2 呼叫 NAS 或 L1 抓取程式」|
| Coverage | **部分保存→本批補登**：結構守衛有，**「優先唯讀重用已落地 canonical 資料、不重複抓取」這個資料架構方向本身**無正式登錄 |
| 補登內容 | **原則**：GitHub Actions 已可靠取得、驗證並落地的 canonical 資料（即 `data_cache` 等已進 repo 的落地檔），New UI2 應**優先唯讀重用**，不應為**同一指標**無理由在 Streamlit Cloud 再建立一套重複抓取。**限定**：(i) 這是**資料架構方向**，不代表禁止任何經核准的 Cloud 取數；(ii) **不授權**新增 API、cron、adapter 或正式接線；(iii) 「已可靠取得、驗證並落地」不是推定——Key 已配置≠認證成功、API 可用≠語意有效、落地≠UI2 已接線（#1110 既有結論，只引用不重登）；(iv) 重用仍受 `DG-LIC`／`DG-PIT`／`DG-COV`／`DG-SCOPE`、`I1144-WIRING-GATE` 與 G2F 守衛拘束。**BACKLOG 新列 `DATA-REUSE-GITHUB-CANONICAL-RULE`（原則，非工作項）**。其餘 #1110 原則（D6 已完成不重做；D1～D5〔#1110 題號〕未裁示）已完整保存，不重登；注意 D1～D5 有兩組同名不同義（#1110 題號 vs DEC-172 治理 D1–D5，DECISIONS 已消歧）|
| 來源鏈限制 | 舊留言的「客戶方向」是釋義；本次客戶重新確認為新授權依據；本條不冒稱舊留言逐字查證 |

**(六) 範圍外、衝突檢查與 NOT VERIFIED**

- **#1164 衝突檢查（寫入前已做）**：#1164（draft）以 `get_files` 讀取，僅改 2 個檔：`docs/BACKLOG.md`（hunk `@@ -227,46 +227,9 @@`，基底 `7eb48d6c` 的第 227～272 行範圍，將 Data Health 批 A 等已結案列搬至歸檔索引）與 `docs/archive/historical/BACKLOG_CLOSED_HISTORY_2026-11-12.md`。本批對 BACKLOG／DECISIONS／HANDOFF／PROJECT_STATE **皆只在檔尾追加**，不碰上述行區間與歸檔檔 → **無重疊**。#1164 維持 Draft，未處置。
- **本條不解除任何 Gate／HOLD**，不授權：觸發任何抓取／bootstrap／回補／手動 workflow、合併／關閉／重開／rebase／update branch #1124～#1126、處置 #1164、刪除任何 Run／Artifact／YAML／分支、修改全域 retention、修改 NAS／Secrets／Branch Protection／資料契約／`app.py`／`app_ui2.py`／UI、新增 API／cron／Secrets／adapter、改 publisher／PR 模板、關閉 #1119／#1138／#1116／#1110／#1107、Cloud Reboot。
- **NOT VERIFIED**：fence 與客戶原訊息的逐字一致性；客戶是否已實際操作 DPE-5；11-12 與 11-10 外資官方值；`twii` `volume` 語意；`margin` 真值；交易日曆；`published_at`；證交所『交易資訊使用管理辦法』全文；FinMind 使用條款；Yahoo 完整服務條款與 `^TWII` 適用性；GitHub Docs 的 retention 說明（舊留言引用，本組未重讀）；#1124 review threads 數；`shared/twii_ohlc_contract.py` 本組未重跑。
- **單組聲明**：本條 (二)～(六) 的核實與判讀為單組撰寫，**未經非作者獨立 QA（`CLAUDE.md` §-2 規則 6）**；CI 與 QA 結果由總管於 PR 補記；**不得被引用為「已 QA PASS」**。

#### DEC-183 後續註記（Batch 2；2026-11-14；只追加；DEC-183 上文一字未改；決策者 AI 總管〔事實更新／勘誤〕；**非新客戶裁示**；授權依據為客戶 2026-11-14 原文二、Batch 2 第 2、3 項；非 QA PASS）

**(Z1) #1124～#1126 自動 PR body「關 PR 並刪分支」指示——不是客戶授權（客戶 Batch 2 第 2 項；僅註記，不修改 publisher 或 PR 模板）**

- **事實（FACT）**：`scripts/publish_data_pr.py` 約 L676–677 產生的資料 PR body 含一段「人工處理（cron 發布 fail-closed 時）」——「若每日排程在『發布資料』步驟持續失敗：① 關閉本 PR（不合併）；② 刪除分支 `auto/data-…`；③ 下次排程會從 main 重建。」（#1124 現行 PR body 已讀取，分支名為 `auto/data-macro-history`）。另 `HUMAN_ACTION` 常數（約 L152）「請人工處理：關閉該資料 PR 並刪除分支，或回報 ChatGPT 決定契約。」被多個 fail-closed 錯誤訊息引用。#1126 的 PR body 本組已讀取，含同一段（分支名為 `auto/data-macro-forward-test`）；#1125 的 PR body 本組未重讀，依同一腳本與同一模板推論亦含此段（INFERENCE）。
- **判定**：該段是**腳本產生的自動文字，不是客戶授權**。它與 `PROJECT_RULES.md` §4 表第 8 項（約 L243：不可逆操作含刪除 branch；DEC-009、DEC-012、DEC-020）及 §10（約 L426：既有遠端分支刪除不得自主執行，須客戶核准清單，DEC-012）**衝突**。任何 AI／接手者**不得照做**，不得直接執行不可逆刪除；「關 PR＋刪分支重建」已列 DEC-182 (五) 禁止清單。DPE-5 的 Close→Reopen **保留分支**，與該段 ② 的刪分支是**兩件事**。
- **不做**：不修改 `scripts/publish_data_pr.py`、不改自動 PR 模板、不改 fail-closed 行為（資料契約疑義仍應回報客戶，不硬刪資料）。

**(Z2) #1105／#1103 出處勘誤（客戶 Batch 2 第 3 項；保留原文，不改舊字；無法確定者一律 NOT VERIFIED）**

- **兩處標示衝突（FACT）**：(a) 本檔 DEC-156 段之後「治理裁示紀錄（2026-11-10 追加）」（約 L7965）稱「僅紀錄 owner 於 #1105 留言所給裁示，非 AI 新決策」「owner／ChatGPT 治理裁示」；(b) `docs/vnext/DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md`（約 L100、L365）稱「原文為 ChatGPT 編擬，是否等同客戶正式裁示仍待客戶確認」。
- **GitHub 逐字讀取（本組以 `pull_request_read get_comments` 取得）**：#1105 留言 `6754457744`——`created_at` 2026-11-09T23:38:51Z（台北 11-10 07:38）、作者帳號 `linchen-20200325`（`author_association`＝OWNER）、抬頭「**ChatGPT 獨立治理裁示**（2026-11-10）— PIT 不接受／NO MERGE」；內文含「拒絕以現有證據合併 #1105」「請先保存本 PR diff／QA 證據，然後依 PR 自帶的 fail-closed 人工處理機制，關閉**不合併**並清理 `auto/data-macro-forward-test` 分支…在關閉／刪分支前需 GitHub 重查…」。#1103 留言 `6754456437`（2026-11-09T23:38:46Z，同帳號，抬頭同為「ChatGPT 獨立治理裁示」）；留言 `6754511702`（2026-11-09T23:42:06Z，同帳號）自稱「**ChatGPT 按** PR 內建安全恢復路線 Close→Reopen（未合併、未改檔案或 head）」，並記該 head 新的原生 CI run `42722497312`；留言 `6755593793`（2026-11-10T00:45:57Z，同帳號）為「非作者獨立 QA」，署名 Claude Code，稱同 head 五項 success。
- **勘誤（讀法）**：這些留言的**抬頭自稱「ChatGPT」，卻張貼在客戶（owner）帳號下**；內文是否經客戶審閱、是否為客戶逐字意旨，**repo 內無法判定（NOT VERIFIED）**。因此上列 (a) 的「owner 裁示」措辭**不得讀成客戶逐字裁示**；較忠實的讀法是「owner 帳號下、自稱 ChatGPT 編擬的治理裁示留言；是否等同客戶正式裁示 NOT VERIFIED」（與 (b) 一致）。舊字（含 L7965）一字未改，本註記為最小勘誤。
- **#1105 留言指示「清理 `auto/data-macro-forward-test` 分支」**：本組在 repo 內**查無** `PROJECT_RULES.md` §10／DEC-012 要求的**客戶核准清單**（NOT VERIFIED）；該分支現存於遠端（現為 #1126 的 head，`git` 實查），其刪除屬不可逆操作，本註記**不授權**任何刪除。
- **#1103 Close→Reopen 的執行者**：留言 `6754511702` 自稱「ChatGPT 按…」，帳號為 owner；而 `docs/vnext/LATEST_TRADING_DAY_REFRESH_PROCEDURE_2026-11-13.md` 的 S2 行與 DEC-181／DEC-182 把 DPE-5 寫為「客戶於同 head 觸發」且「Close→Reopen 僅限客戶操作」→ 兩者**不一致**；#1103 當時**實際按下者 NOT VERIFIED**（需 GitHub 事件時間軸或稽核紀錄才能確證，本組工具讀不到）。**影響**：以 #1103 作為「Reopen 後原生 CI 確實會跑完 `ui2-browser-gate`」的先例時，**先例本身成立與否（該 run 的五項 success 為上列非作者 QA 留言所述）與「是誰按的」是兩件事**；後者 NOT VERIFIED，不影響 DEC-183 要求 DPE-5 由客戶本人操作的規定。
- **不改**：#1103（已合併）與 #1105（已關閉未合併）的結果，以及 DECISIONS 上述舊註記、vnext 文件的原文。
