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

> 📌 **例外登記（非取代）BY DEC-117 Q7**（2026-10-30；決策者 **客戶**（DEC-117）；append-only，本條原文一字未改）：四「第一屏五問」③主要圖、十一「📊 市場頁設計方向」第一屏優先「主要市場圖」、附錄（同日前序指示 15:18Z）「四、目前三頁修正方向 📊 市場」第一屏優先「小型台股趨勢圖」——📊 市場頁**手機版**由客戶核准合理 mobile exception（Primary Visual 可位於第一屏下方；手機第一屏優先序＝今日結論 > 核心狀態 > 是否需行動 > Primary Visual；Primary 須緊接 L1 決策區、不得被 L2／L3 插隊）。例外**只豁免 Primary**：五問④「是否需要行動」在手機仍須在第一屏（線框 §10 C1-10，AI 總管內部判定）。桌機與其餘各頁、本條其餘各項全部照舊（附錄「今日結論必須在第一屏可見」由 DEC-117 Q5 同向加強）。

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

> 2026-10-29 **補登**（ID 取下一個未用號；**補登，來源＝程式碼註解 `src/ui/views/page_today.py`**；本裁示此前只存在程式碼註解與測試 docstring，`docs/**` grep 0 命中）。**非客戶逐字全文**：下列引文為程式碼註解內所記之客戶裁示字句（撰寫組照錄註解原字，未見客戶原訊息）。

- **決策者**：客戶（2026-09-24；經程式碼註解轉述）。｜**日期**：2026-09-24。｜**範圍**：UI／呈現（新版 v2 卡面：今天頁三要素卡）。｜**取代鏈**：DEC-111 →（位置）DEC-109 七；內容仍有效。｜**狀態**：**部分取代 BY DEC-109**（2026-10-29 有意識的政策變更，不是漏刪，決策者 客戶（DEC-109））——三要素的**位置**（卡面常駐）被取代；三要素**內容**（`Note` 三段非空、不得消失）維持。
- **來源**（類別 **E**：程式碼註解轉述；約 L 僅參考）：`page_today.py` 約 L2933「🔴 **2026-09-24 客戶裁示：三要素要在卡面上看得到，⛔ 不是只剩一條指路 ＋ hover。**」；約 L2683／L2689「2026-09-24 客戶裁示批 1……客戶 2026-09-24 看過對照之後裁示「三張同版」」；約 L2764／L2775「客戶 2026-09-24 裁示：放棄分批，一次整頁卡化」。
- **兩邊理由並陳**：舊做法（三要素上卡面）最不會讓「為什麼沒有／去哪補」被忽略，且明確反對「只剩 hover」——**理由仍成立**；新做法（DEC-109）勝出的原因：三要素常駐使畫面成為文字牆（客戶 DEC-108／DEC-109 自承偏差），且與 DEC-091 §一 客戶原文「禁止：大量三要素文字卡＋…全部同層」張力未調和；DEC-109 以「保留、可取得、可展開、預設下沉」同時滿足兩者。
- **仍有效部分**：「⛔ 只剩 hover」的禁令（延伸到手機：必須可點開）；「三張同版」作為今天頁（legacy 可達）既有設計。

### DEC-112｜（補登）客戶 2026-09-25 裁示 1～4：v2 卡面三列短句（裁示 2）＋K1 原文摘錄＋「⛔ 完整原文不得只剩 hover」＋16 燈卡三列出處收進「▸ 詳細」（客戶 2026-09-25）

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
