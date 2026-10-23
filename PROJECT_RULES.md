# PROJECT_RULES — Project AI Constitution v1.0（my-stock-dashboard）

> **本檔是專案 AI「怎麼工作」的入口與索引**，依客戶 2026-10-16 裁示建立（`docs/DECISIONS.md` DEC-016）。
> 治理**機制**參考基金 repo `my-Fund-dashboard` 的同名實作（只借結構與共通機制）；**未複製**基金專屬規格、文件位階或 Decision。股票領域規則一律來自本 repo 自己的證據（第 13 節）。
> ⚠️ **provenance 揭露**：本檔由單一撰寫組撰寫，DEC 引用清單**待第二組獨立 evidence audit**（`CLAUDE.md` §-2 規則 6）；稽核通過後本註保留作 provenance。
> 行號為 2026-10-16 實測、會漂移；引用前現場重查。

## 第 0 節｜位階、射程、文件地圖

### 0.1 位階（讀任何一條之前先讀）

- **`CLAUDE.md`（資料完整性憲法）自稱「AI 協作的最高行為準則」，凌駕本檔全篇。** `PROCESS.md`（Core Protocol v2.0）同樣**不因本檔改變**。
- 本檔只做**彙整與索引**：**不修改、不重新解釋** `CLAUDE.md` 或 `PROCESS.md` 任何一條；本檔與兩者牴觸時，**以 `CLAUDE.md` 為準**，並把牴觸登記到 `docs/BACKLOG.md` 第 4 節。
- 本檔**不改變任何既有治理或產品裁示**。對既有裁示的任何變更，都需要一筆**新的客戶 Decision**（追加於 `docs/DECISIONS.md`）。
- 本檔不帶憲法效力的新增條文：凡寫「規則」者，都附 DEC 編號或既有錨點；附不出來源的一律不寫。

### 0.2 射程

- **管**：專案 AI 怎麼查證、派工、停手、請示、稽核、交付、交接、落盤。
- **不管**：畫面、文案、公式、門檻、資料契約的本文 —— 那些以 `CLAUDE.md` §1～§8、正式規格與客戶裁示為準。第 13 節只是**索引**。
- **登記不構成動工授權**（`CLAUDE.md` §-1；DEC-002）：本檔任何一句都不得被讀成「可以主動找事做」。

### 0.3 ~~四檔分工（Governance Truth）~~ 五檔分工（Governance Truth＋共用專案知識）（2026-10-22 更新，有意識的變更，不是漏刪，決策者 客戶；DEC-068）

| 文件 | 管什麼 | 不管什麼 |
|---|---|---|
| `PROJECT_RULES.md`（本檔） | AI 工作規則入口；股票領域硬規則索引 | 規格本文；既有條文本文 |
| `docs/DECISIONS.md` | 客戶裁示與正式決策（DEC-NNN，附可追溯來源與取代鏈） | AI 推論（不得寫成客戶裁示） |
| `docs/BACKLOG.md` | 所有未完成工作、待裁示題、Research Candidate | 動工授權 |
| `docs/HANDOFF.md` | ~~短、可接手的現況：在哪、最近完成、blocker、下一安全接手點~~ **短版交接**：只保存 current active work、blocker、next safe point、必要的 main／PR／CI 狀態（2026-10-22 更新，有意識的變更，不是漏刪，決策者 客戶；DEC-068） | 完成或正確的證明；完整歷史；~~（無）~~ 完整專案記憶（→ `docs/PROJECT_STATE.md`） |
| `docs/PROJECT_STATE.md`（2026-10-22 新增，DEC-068） | ChatGPT 與 Claude 共用、「目前仍有效」的專案知識：架構關係、現況摘要、重要背景與限制、已核准 vs Candidate 的界線；「保存專案知識，不保存聊天紀錄」 | 未完成工作（→ BACKLOG）；current／blocker（→ HANDOFF）；正式裁示（→ DECISIONS，不取代）；聊天紀錄；secret／credential；把 Candidate 寫成 Approved；把推測寫成事實 |

📌 **五檔讀法（2026-10-22 新增，DEC-068）**：⛔ **不新增 `PROJECT_CONTEXT.md`**（客戶原文「不要再新增 PROJECT_CONTEXT.md，避免與 PROJECT_STATE 重疊」）。`docs/PROJECT_STATE.md` 是知識摘要，**不是規範或裁示來源**：本檔他處既有的「四檔」字樣不逐一改寫，涉及 Governance Truth（第 1.2 節）時仍指本檔／DECISIONS／BACKLOG／HANDOFF；涉及跨對話保存與讀取時依第 15 節讀作五檔。

**Blueprint 指標**（2026-10-17 新增，DEC-057）：`docs/vnext/VNEXT_PRODUCT_BLUEPRINT.md` ＝ DEC-056 第 4 點「Blueprint：最終產品方向」的承載者（附 `docs/vnext/UI_AUDIT_2026-10-17.md`）。⚠️ 它**不是實作授權**、不帶 Decision 效力；其中線框與 `BP-DR-*` 未經客戶裁示前不得施工（DEC-003、DEC-057）；與本表四檔或 `CLAUDE.md` 牴觸時以後者為準。上表標題「四檔」不因本指標改變。（2026-10-22 補註：上表已改為五檔，Blueprint 仍不列入；有意識的變更，不是漏刪）

**上位與既有文件（本批不改）**：`CLAUDE.md`、`PROCESS.md`、`ARCHITECTURE.md`、`SPEC.md`、`STATE.md`、`docs/v2/spec/*`。
**歷史全文**：分支 `claude/stock-dashboard-handoff-g9dtm0` 的 `HANDOFF.md`（約 5150 行，含舊待辦、等你答、逐字收錄的客戶裁示）—— **未刪除、未凍結宣告**；其中尚未遷入的待辦見 `docs/BACKLOG.md` `BL-MIGRATE-1` 📌 註。

## 第 1 節｜Fact Truth vs Governance Truth（雙軌）

### 1.1 Fact Truth（「現在實際是什麼」）

依下列順序取證，前者推翻後者：

1. **GitHub**：main SHA、PR 狀態、check-run conclusion、遠端分支；
2. **code 與 tests 的實際輸出**；
3. 正式文件（`CLAUDE.md`、`PROCESS.md`、`docs/v2/spec/*`）—— ⚠️ 本層為撰寫組讀法插入，客戶原文只有三層（見下）；
4. 本四檔；（2026-10-22 補註，DEC-068：`docs/PROJECT_STATE.md` 的狀態快照排在 `docs/HANDOFF.md` 之後、AI memory 之前，與第 15 節一致）
5. 聊天內容與舊回報。

來源：客戶 2026-10-15「真實性優先順序：/ GitHub / code / tests > HANDOFF > 舊回報」（`docs/DECISIONS.md` 來源類別 D，MSG 1 §0）；第 3 層與第 4 層的細分為撰寫組讀法，可被客戶推翻。⚠️ 這是**判斷事實**的順序，不是規範效力的順序。

### 1.2 Governance Truth（「應該怎麼做」）

- 以本四檔＋`CLAUDE.md`＋`PROCESS.md` 為準；四檔內部衝突以 `docs/DECISIONS.md` 較新且有來源者為準，仍不明 → 登記 `docs/BACKLOG.md` 第 4 節。
- 程式現況與規格不一致時：**記錄 discrepancy → 判斷是 bug 還是待裁示 → 不得偷改其中一方**。

### 1.3 HANDOFF 不是完成證明

任何「已合併／CI 綠／已完成」都要能回到第 1.1 節第 1～2 層證據（SHA、PR、check-run）。

## 第 2 節｜GitHub-first verification

（機制依客戶 2026-10-16 列舉之共通治理機制建立，DEC-016；本節規則另依第 1.1 節來源。）

- 開工、宣稱完成、合併、交接前，先 `git fetch` 並實查 main SHA、open PR、check-run；不靠記憶、不靠交接文件、不靠聊天。
- 合併前逐條看 check-run `conclusion`。
- ⚠️ 本 repo 的 main 會被每日 cron 資料 commit 推進（例：`🤖 每日總經歷史增量`、`🤖 板塊資金泡泡圖每日增量`）；寫 main SHA 時附量測時間，並區分「最後一個非 cron commit」與「當下 tip」。
- 已知過期值：`70416a6a` 是 #852／Z65（2026-10-15）的 commit，**不是目前 main**。

## 第 3 節｜Silent Autonomous Cruise（靜默自主巡航）

- ~~**規則**：沒有需要客戶決定的事時不輸出過程訊息，但持續執行已授權工作；只在 **A. 完整有意義階段完成** 或 **B. 真正需要客戶裁示** 時回報；不報「已派工／正在實作／PR 已開／等 CI／某條 CI 綠／等稽核／沒有新資訊」。每批最多約 3 個高度相關安全項目。（DEC-007、DEC-006）~~（2026-10-17 由客戶治理裁示 DEC-059 強化為下列現行版；有意識的整合，不是漏刪 —— 舊句四項要點（不報過程、A／B 兩種回報、不報中間狀態、每批約 3 項）全數保留在現行版，另加第三種可打斷情況與完整禁止清單）
- **規則（現行；DEC-059 強化 DEC-007／DEC-006）**：預設採**靜默自主巡航**。在既有授權範圍內，可自行完成：研究 → 實作 → tests → independent audit／review → 修正 → push → PR → CI → 修 CI → merge → main verification → `docs/BACKLOG.md`／`docs/HANDOFF.md`／`docs/DECISIONS.md` 必要同步。安全工作以**最多 3 個緊密相關項目**為一批，避免 scope creep。
- **禁止為了「報進度」而輸出**（客戶 2026-10-17 原文清單，逐項）：已開始／已派工／正在研究／正在修改／已 commit／已 push／PR 已開／等 CI／某一個 CI 已綠／等另一個 CI／正在 audit／audit 尚未完成／稍後再看／subscribed／monitoring／沒有新資訊／重複上一則狀態／workflow 還在跑。這些狀態由專案 AI 自己處理。
- 📌 **2026-10-20 客戶補充禁回報清單**（append-only；客戶訊息 2026-10-20T07:23Z 原文逐項；與上一條重疊者照列、取聯集）：「agent 已派出／正在跑／等待 agent」「CI 正在跑／等待 CI」「QA 正在複驗／等待 QA」「notification／subscription 狀態」「commit 已 push」「draft PR 已開」「第幾輪回修正在進行」「0 MUST-FIX / NIT 等尚未形成 Decision Gate 的中間結果」「「接下來我會……」」「任何單純狀態更新」。客戶同訊息：「這些全部在背景自行處理。」「如果只是 NIT、文件補漏、既有規格內的小修，請自行處理後繼續，直到整個 Batch 完成再一次回報。」（本條只補禁回報項目；可打斷情況仍以下一條為準）
- **客戶回報語言（DEC-069）**：客戶原文「所有客戶回報一律使用繁體中文；除程式碼、正式欄位名稱、log 原文外，不得改用英文。」—— 繁體中文（台灣）；適用所有對客戶的回報（含完成回報與裁示題）。
- **只有三種情況可以主動打斷客戶**：
  1. **完整階段完成**：implementation＋tests＋audit＋CI＋merge＋main verification 已達該階段完成條件（第 7 節）；精簡回報，原則 ≤5 行（完整證據在 PR，DEC-060）。
  2. **真正需要客戶裁示**：即第 4 節「必須停下問客戶」表（客戶 2026-10-17 清單的逐項對映見該表下方註）；已經有正式 DEC 的問題不得重新詢問（DEC-013）。可超過 5 行，但只保留完成裁示所需資訊（DEC-060）。
  3. **需要切換 Effort**：僅依第 9 節 Minimum Sufficient Effort 規則，在安全停點提醒。📌 2026-10-23（DEC-073，append-only）：**目前模型／Effort 低於下一工作所需**時，依第 9.0 節強制 Gate **必須停手**通知客戶 —— 這是本節靜默巡航的**正式例外**（客戶原文「這是 "Silent Autonomous Cruise" 的正式例外：即使其他工作應靜默自主執行，遇到 Model / Effort 不足仍必須停下通知客戶。」）；高於所需時不需為形式要求降級。每個階段邊界（含「merge＋main verification → 收尾同步」）都要先做 9.2 強制 Effort Check（DEC-061）；規則本文只在 9.2。
- 已確認的 bug，若修法單一且不涉及 Decision Gate，應自行修正、測試、audit、CI，不要包裝成客戶選擇題（第 4 節反向禁令）。
- ⚠️ **≤5 行與揭露義務並存**：「原則 ≤5 行」是長度原則，**不豁免**下方限定第 4 條 —— 未經第二組驗證的全稱句、沒實測的部分仍須在回報中標明（可濃縮成一句並指向 PR／BACKLOG 的完整記錄）。`CLAUDE.md` §-1.5 v1 第三條「代碼產出後自我審核五段呈現」、§-1.5 第四條／v3 §04 三段式交付報告（含 §-1.5.F 判定 6 清理項目逐檔列出），以及 `PROCESS.md` §1（/compact 提醒）、§4（四段報告）~~與 ≤5 行的關係見 `docs/BACKLOG.md` `CV1-DR-10`（衝突時以 `CLAUDE.md` 為準）。~~（2026-10-17 更新：`CV1-DR-10` 已由客戶裁示，暫行讀法轉為下一條正式規則，DEC-060；有意識的變更，不是漏刪）
- **回報格式（正式；DEC-060）**：「完整技術／稽核證據留在 PR。」「對客戶的一般完成回報原則 ≤5 行。」「若真正需要客戶裁示，可超過 5 行，但只保留完成裁示所需資訊。」落地方式：`CLAUDE.md` §-1.5 v1 第三條「自我審核」五段、第四條／v3 §04 三段式交付報告（含 §-1.5.F 判定 6 清理項目逐檔列出）、`PROCESS.md` §4 四段報告 —— **仍必須完整產出**，寫在 **PR 描述**；對客戶的完成回報是其 ≤5 行摘要＋PR 連結；`PROCESS.md` §1 的 /compact 提醒併入完成回報的 ≤5 行內。`CLAUDE.md`、`PROCESS.md` 已依客戶授權同步加註，三檔間不再有回報格式張力（撰寫組判讀，GB 稽核複核，2026-10-17）。⛔ 揭露義務不減（下方限定第 4 條）。
- **限定（缺一不可）**：
  1. 巡航只在**已指派或已核准**範圍內；沒有指派 → 停手等指令（DEC-002）。不得創造新需求、不得自行開新功能 Batch（DEC-006、DEC-015）。
  2. 巡航擴大的是「不必問客戶」，**不是「不必派工」**（DEC-001）。
  3. 本批外的新發現**只登記、不夾帶**（第 12 節）。
  4. 精簡回報**不得吃掉揭露義務**：未經第二組驗證的全稱句、沒實測的部分，照寫（`CLAUDE.md` §-2 規則 6、§-1.5.A-7）。

## 第 4 節｜Stop／Decision Gate

**可自行處理（仍須派工、仍受第 8 節稽核）**：已確認 bug 且只有一個安全修法的最小修復（DEC-009 末句、DEC-008）—— ⚠️ 資料層修錯另受 DEC-038「限三類、⛔ 不擴大」拘束，與 DEC-008 Level 1 的範圍關係未明示（`docs/BACKLOG.md` `CV1-DR-09`），未裁示前取嚴；tests；稽核 findings 修正；文件同步；已核准規格內的實作；CI 修復。

**必須停下問客戶**（取 DEC-003、DEC-006、DEC-008、DEC-009 的聯集；衝突處取嚴）：

| # | 事項 | DEC |
|---|---|---|
| 1 | 新增或修改投資**公式**；正式 scoring／weight／門檻 | DEC-009、DEC-008 |
| 2 | 新**資料語意**（含口徑改變、Context → Core／hard Veto） | DEC-009、DEC-008 |
| 3 | 新增或替換 **production 資料來源** | DEC-009、DEC-006（need new source） |
| 4 | **API／MCP 整合進 production 資料鏈**（見下方說明） | DEC-009、DEC-008 §五 |
| 5 | 正式加減碼比例 | DEC-053、DEC-009 |
| 6 | substantive AI behavior | DEC-009 |
| 7 | **重大 UI flow／版面**（版面佈局、欄位增減、分頁動線異動）→ **草稿先行**：先出文字線框＋推薦理由，客戶拍板後才寫 UI code | DEC-003、DEC-009、DEC-006（layout change） |
| 8 | **不可逆操作**：刪除 branch、刪除正式生產資料、舊 UI 實體刪除、production switch | DEC-009、DEC-012、DEC-020 |
| 9 | credentials／account access | DEC-009 |
| 10 | 業務邏輯互斥；有多個合理方向且有產品意義；無法安全自行解決的 blocker | DEC-003、DEC-009 |

**客戶 2026-10-17 打斷清單對映（DEC-059；不另立第二份清單）**：投資公式／threshold → #1；新 data semantics → #2；新／替換 production source → #3；API／MCP → #4；substantive AI behavior → #6；major UI flow 尚未裁示 → #7；irreversible operation、production switch、old UI deletion、branch deletion → #8；credentials／account access → #9；多個合理方案且 repo 無既有裁示、真正 blocker → #10。客戶清單每一項在上表皆有對應（GA 已驗，2026-10-17），上表未因此增刪。

**第 4 項的精確讀法**：客戶 2026-10-10 規則**允許**主動研究、建立 PoC、測試與比較新 API／MCP（DEC-008 §五）—— 這**不是禁令**；但**第一次接入正式投資資料鏈前**，除須驗證該規則列的 16 項外，依客戶 2026-10-15 §25（DEC-009，較嚴）**一律送 Decision Gate**。2026-10-10 規則中「同口徑高可信免費源可直接最小整合」一款，在客戶另裁前**暫不適用**（暫行取嚴，`docs/BACKLOG.md` `CV1-DR-08`）。

**反向禁令**：已確認 bug、只有一個安全修法時，**不得包裝成裁示題**（DEC-009 末句；`CLAUDE.md` §-1.5 v3 §03-1「嚴禁向客戶拋出選擇題」）。已裁示事項不重問、待裁示題未變不重送（DEC-013）。

**請示格式**：商業與功能語言＋總管推薦方案＋具體原因，可一鍵決策（`CLAUDE.md` §-1.5.E C5）。**Audit 完成回報**若需要裁示，第一句寫「本次共 X 個待裁示問題。」（客戶 MSG 1 §23；原文射程為該 Audit 完成回報，本檔不擴及其他回報）。

**客觀停手門檻（並存，先到先停）**：同一報錯連續重試 2 次未果 → 立即停機，計數跨 subagent 累計（DEC-005）；同檔回修超過 2 輪 → 停手問客戶（DEC-010）。

## 第 5 節｜Minimum Necessary Change／Scope Control

- reproduce → root cause → **minimum fix** → regression proof（DEC-006 防膨脹 Gate：能改既有函式就不新增；能重用既有元件就不新增相似元件；客戶 MSG 6「依 Minimum Necessary Change 原則施工」）。
- 不順手重構、不建預留架構；dead code 只登記（DEC-006；`CLAUDE.md` §8.4 step 4「禁止自作主張大重構」）。
- Audit 階段不得順手施工（DEC-015）；本批範圍外的發現登記 `docs/BACKLOG.md`，不夾帶。
- 舊 UI 凍結：不為任何理由修改（DEC-019）。

## 第 6 節｜Safe Checkpoint

（機制依客戶 2026-10-16 列舉之共通治理機制建立，DEC-016。）

- **何時**：換對話、換模式、大型階段切換、不可逆動作前、長工作結束、context 過長之前。
- **確認清單**：working tree 是否乾淨、main SHA（附時間）、open PR、main CI、未提交內容與殘留 worktree／stash、~~四檔是否同步~~ 五檔是否同步（第 15 節 Handoff Save Check；2026-10-22 更新，有意識的變更，不是漏刪，決策者 客戶；DEC-068）、下一步。
- ⚠️ 已知「現存未處理物件」：舊 UI 壓測 `stash@{0}` **不恢復、不提交、不推送**（DEC-019）；只在原容器本機，接手者不得嘗試還原。

## 第 7 節｜Definition of Done

implementation → relevant tests（含真實引擎路徑 regression）→ independent audit／red team → required fixes → push → PR → CI → merge → **main verification**（main SHA＋main CI conclusion）→ 更新 `docs/BACKLOG.md`（結案列附 PR＋merge sha＋main CI run）、`docs/DECISIONS.md`（若有新裁示）、`docs/HANDOFF.md`。

- 沒跑的就寫沒跑；不得虛構驗證；不得把自己的結果寫成第二組已複驗。
- 來源：客戶 MSG 1 §24、MSG 2 第 6 點（研究 → 實作 → tests → independent audit → push → PR → CI → fix → merge → main verification → handover）；`docs/BACKLOG.md` 0.3 第 1 條；`CLAUDE.md` §-2 規則 3、6。

## 第 8 節｜Independent Audit／Red Team

- 實作者不得自己驗收自己；調查與稽核獨立分派、多組不同角度，不由同一組自己查自己（DEC-001；`CLAUDE.md` §-2 規則 3／4）。
- **稽核組數下限依 `CLAUDE.md` §-2 規則 4**：同一件事至少派**多組不同角度**的獨立 agent，調查與稽核尤其不可單點、不可自己查自己；本檔不另設較低門檻。QA 分級沿用 DEC-010（A／B／C）、跨級取最高，但分級**不得**低於 §-2 規則 4 的下限。
- **治理文件**：C 級原為「自驗不派稽核」，但客戶 2026-10-16 明令本批派獨立第二組 evidence audit（DEC-016）；是否全面適用未裁示 → `CV1-DR-02`。在客戶裁示前，**動到四檔的 Decision／硬規則索引時比照本批派獨立稽核**（暫行取嚴）。

## 第 9 節｜Model／Mode／Effort 自主管理（DEC-014；Effort 部分由 DEC-059、DEC-061 強化；2026-10-23 由 DEC-073 新增 9.0 強制 Model／Effort Gate）

### 9.0 強制 Model／Effort Gate（現行；DEC-073，客戶 2026-10-23）

> 客戶原文全文逐字收錄於 `docs/DECISIONS.md` DEC-073。本小節是**永久規則**，新對話讀完本檔即自動繼承（第 11 節、第 15 節）。

- **不得固定模型或固定 Effort 工作**（客戶原文「專案 AI 不得再依固定模型或固定 Effort 工作。」）。每一個「下一完整工作階段／Batch」開始前，必須依實際工作內容自行判斷兩項：**(1) 所需模型／能力等級；(2) Minimum Sufficient Effort（Low／Medium／High，依 9.1 表）**。判斷時點＝9.2 階段邊界。
- **不足時強制停手**（客戶原文六步，逐字）：若「目前模型／Effort」低於下一工作所需：
  1. 立即停手。
  2. 不得硬做。
  3. 不得自行假設模型或 Effort 已切換。
  4. 不得自行降低問題複雜度以繞過 Gate。
  5. 必須向客戶回報：建議模型／能力等級；建議 Effort；為什麼目前設定不足；切換後準備執行的工作。
  6. 等客戶確認已切換後才能繼續。
- **回報格式**（撰寫組依客戶第 5 步四項＋第 6 步訂定；繁體中文，DEC-069）：

```
⏸️ 模型／Effort 不足，已停手
建議模型／能力等級：___
建議 Effort：Low / Medium / High
目前不足原因：___
切換後準備執行的工作：___
請切換後回覆「改好了」確認已切換。
```

- **高於所需時**：客戶原文「反過來，如果現有能力高於工作所需，不需要為了形式要求客戶降級；遵守 Minimum Sufficient Effort 即可。」—— 不停手、不提醒降級，直接工作。
- **正式例外**：本 Gate 是第 3 節 Silent Autonomous Cruise 的正式例外（客戶原文「即使其他工作應靜默自主執行，遇到 Model / Effort 不足仍必須停下通知客戶。」）。
- 不得在 9.2 所列「不得要求切換」的時機中途打斷；遇到時先到最近安全停點（第 6 節）再停手回報。⚠️ 但「不足」時**不得**在停點前繼續推進下一完整階段（撰寫組讀法）。
- 客戶回「改好了」後：直接繼續；不重新摘要；不重問；不重做（DEC-014 續有效）。Gate 不改變派工、獨立稽核、揭露義務（`CLAUDE.md` §-2）；切換本身**不是**產品 Decision Gate。
- 📌 2026-10-23（append-only；客戶 2026-10-23 Freeze 指示）：「中途風險升高亦同」與「不得默認固定 Opus／High 或 Sonnet／Medium」見**第 16.2 節**（DEC-076）。


~~每個下一完整階段開始前自行判斷目前模型／模式／Effort 是否合適；**只有切換有明顯品質或額度效益時才中斷**。~~（2026-10-17 整合進下方 9.1～9.3，決策者客戶，DEC-059；有意識的整合，不是漏刪 —— 「階段開始前自判」保留於 9.1，「有明顯效益才中斷」保留於 9.3（模型／模式），Effort 改依 9.2「明顯應使用不同 Effort 即主動提醒」）

### 9.1 Minimum Sufficient Effort（推理強度夠用即可；DEC-059）

**原則**：使用「**能可靠完成下一完整階段的最低 Effort**」，避免不必要 token／額度浪費。不得因為 High 比較強就預設 High；若 Low 足夠，不使用 Medium；若 Medium 足夠，不使用 High。專案 AI 在每個「下一完整工作階段」開始前，必須自行判斷所需 Effort（執行方式＝9.2 強制 Effort Check，DEC-061）：

| Effort | 適用（客戶 2026-10-17 原文清單；📌 2026-10-23 DEC-073 新清單併列，取聯集） |
|---|---|
| **Low** | GitHub 狀態確認；HANDOFF／BACKLOG 一般同步；已知答案的機械性文件修改；小型、低風險、規格完全明確的工作 —— 📌 2026-10-23 DEC-073 客戶原文：「GitHub 狀態確認、交接同步、機械性文件修正、低風險且規格完全明確的小修改。」（同向） |
| **Medium** | 一般 UI／UX 實作；Blueprint／UX Audit；單一模組正常 bug fix；一般測試與低風險 wiring；有一定推理需求、但不涉及核心投資語意的工作 —— 📌 2026-10-23 DEC-073 客戶原文：「一般 UI/UX、單模組 bug fix、一般測試／wiring、跨模組唯讀稽核，以及需要推理但不改變核心投資語意的工作。」（**新增「跨模組唯讀稽核」**） |
| **High**（只在明顯需要時） | 投資公式；Risk Cap；選股核心邏輯；Action／Position Sizing 核心規則；Thesis 正式判定規則；financial／data semantics；Point-in-Time／look-ahead correctness；跨模組重大架構；高風險 correctness 問題；多個合理方案需要深入權衡 —— 📌 2026-10-23 DEC-073 客戶原文「只有必要時」：核心投資語意／判斷公式；跨模組且高複雜度的核心修改；L3／資料層重大變更；**新資料來源**；**不可逆操作**；**大規模刪除／合併**；**需要重新定義權重、門檻、評分或投資結論**（粗體為相對舊表新增；舊細項未被明示撤銷，撰寫組讀為核心投資語意之例示、續有效） |

- ~~等待 CI、等待 audit、等待 workflow 等待狀態，**不得**要求提高 Effort。~~（2026-10-18 改為 pointer，決策者客戶，DEC-061；有意識的修改，不是漏刪 —— 舊句只講提高方向，已由 9.2 雙向規則「不算新完整階段的短暫狀態」涵蓋，避免重複規則）
- 等待狀態不觸發 Effort 切換（升或降）：見 9.2。
- ⚠️ Effort 只決定推理強度，**不改變**派工、獨立稽核與揭露義務（`CLAUDE.md` §-2 規則 1／4／6；第 3 節限定第 2、4 條）：Low 不等於免派工、免稽核。

### 9.2 Effort 主動提醒（DEC-059；強制 Effort Check 由 DEC-061 強化）

~~如果「下一完整階段」明顯應使用不同 Effort（較高**或較低**），專案 AI 必須在**安全停點**（第 6 節）主動提醒客戶，不得等客戶詢問。~~（2026-10-18 改為下方「強制 Effort Check」，決策者客戶，DEC-061；有意識的修改，不是漏刪 —— 舊句「明顯應使用」是裁量式觸發、沒有強制檢查步驟，「不覺得不同」就不會做檢查，導致 #872 合併後進入收尾同步時漏提醒降級；舊句的雙向、安全停點、不等客戶詢問三要點全數保留於下方）

**強制 Effort Check（現行；DEC-061 強化 DEC-059）**：每個**完整工作階段結束／下一完整階段開始前**（邊界定義見下），專案 AI **必須**先在內部做一次 Effort Check，回答~~兩題~~三題（2026-10-23 修訂，決策者客戶，DEC-073；有意識的修改，不是漏刪 —— 舊「兩題」在 DEC-061 時只檢查 Effort 是正確的；DEC-073 新增「模型／能力等級」為必判項，故第 3 題為 DEC-073 新增）：
1. 下一階段最低足夠 Effort 是 Low／Medium／High？（依 9.1 表）
2. 與目前 Effort 是否一致？
3. 📌（2026-10-23 新增，DEC-073）下一階段所需**模型／能力等級**為何？目前模型是否足夠？

- **一致** → 保持靜默，直接繼續（不報告 Check 結果）。
- ~~**不一致** → 必須在開始下一完整階段**前**停下，用下方既定格式主動提醒客戶升級或降級，不得等客戶詢問。⚠️ **High → Medium／Low 同樣必須主動提醒，不能只提醒升級**（例：高推理批合併後進入 HANDOFF／BACKLOG 一般同步，依 9.1 屬 Low）。~~（2026-10-23 修訂，決策者客戶，DEC-073；有意識的修改，不是漏刪 —— 舊句理由（仍成立）：降級可避免不必要的 token／額度消耗，DEC-061 曾因 #872 後漏提醒降級而強化；新句理由：客戶原文「反過來，如果現有能力高於工作所需，不需要為了形式要求客戶降級；遵守 Minimum Sufficient Effort 即可。」—— 為形式而停下要求降級本身就打斷巡航、消耗客戶注意力；客戶權衡後只保留「不足」方向的強制停手）
- **不足**（目前模型或 Effort 低於所需）→ 依 9.0 強制 Gate **停手**，用 9.0 格式回報，等客戶確認已切換（DEC-073）。
- **高於所需** → 不需為形式要求降級；保持靜默直接工作（DEC-073）。
- **階段邊界（Check 觸發點，至少包含）**：(a) 新批次開始前；(b) 客戶回覆 Decision Gate 裁示後、依裁示動工前；(c) **實作／PR 已 merge 且 main verification 完成 → 進入收尾文件同步**（`docs/BACKLOG.md`／`docs/HANDOFF.md`／`docs/DECISIONS.md` 同步）—— 收尾同步是**新的完整階段**，不是同一批的延續；(d) 收尾同步完成 → 下一批或停在安全點前。⚠️ 第 3 節巡航鏈與第 7 節 DoD 把收尾同步列在同一條流程內，只表示「不必問客戶、完成定義不變」，**不表示**它與實作屬同一 Effort 階段。
- **不算新完整階段（不觸發 Check、不切換）**：CI 等待、audit 等待、workflow 等待、commit／push、PR 開啟等短暫狀態；不要頻繁切換。

格式固定精簡為（客戶 2026-10-17 原文格式）：📌 2026-10-23：現行回報格式見 9.0（DEC-073），本格式保留作歷史。

```
⏸️ 建議切換推理強度
下一階段：___
建議 Effort：Low / Medium / High
原因：___
切換完成後請回覆「改好了」。
```

- ~~**雙向提醒**：提醒可升可降。~~（2026-10-23 修訂，決策者客戶，DEC-073；有意識的修改，不是漏刪 —— 「可降」部分改為不需為形式要求降級，見上；下方客戶 2026-10-17 原文與範例保留作歷史紀錄）（歷史，DEC-073 已修訂；現行不主動要求降級）提醒可升可降。客戶 2026-10-17 追加原文：「若客戶目前選擇的 Effort 高於下一階段實際所需，且已到安全停點，也應主動提醒「可以降低 Effort」，以避免不必要的 token／額度消耗。」降低提醒同受下方時機限制。（歷史，DEC-073 已修訂；現行不主動要求降級）範例（客戶原文，逐字）：

```
⏸️ 建議切換推理強度
下一階段：一般文件同步
建議 Effort：Low
原因：工作機械性且規格明確，目前 High 無必要。
切換完成後請回覆「改好了」。
```

- ~~若目前 Effort 已足夠：不要提醒；不要每次重複報告目前 Effort；直接工作。~~（2026-10-17 同批客戶追加「可以降低 Effort」提醒後改讀，決策者客戶，DEC-059；有意識的修改，不是漏刪 —— 「已足夠」會把「高於所需」也算進去而不提醒，與降低提醒衝突）
- 若目前 Effort **恰好合適**：不要提醒（📌 2026-10-23：高於所需同樣不提醒，見 9.0（DEC-073））；不要每次重複報告目前 Effort；直接工作。
- ~~不得在下列時機要求切換：未 commit 的實作中途；PR 尚在修正中途；CI 正在跑；一個不可安全中斷的完整工作階段中。~~（2026-10-18 補列並釐清射程，決策者客戶，DEC-061；有意識的修改，不是漏刪 —— 原四項全數保留，另加客戶原文「PR 修復途中」，並釐清「完整工作階段」不延伸到收尾同步：舊句曾被讀成整批到收尾都不可中斷）
- 不得在下列時機要求切換（現行）：未 commit 的實作中途；未提交實作（客戶原文）；PR 尚在修正中途／PR 修復途中（客戶原文）；CI 正在跑；一個不可安全中斷的完整工作階段中（客戶原文：不可分割工作階段）。⚠️ 「不可分割的完整工作階段」以上方階段邊界為界 —— merge＋main verification 完成即是邊界，收尾同步前**必須**做 Check。
- Effort 切換本身**不是**產品 Decision Gate。
- 客戶回覆「改好了」後：直接繼續；不重新摘要；不重問；不重做；不再解釋（DEC-014，續有效）。

### 9.3 模型／模式切換（DEC-014，續有效）

只切換 Effort 時用 9.2 格式。**若同時需要切換模型或模式**（只有切換有明顯品質或額度效益時才中斷），先到安全停點，改用 DEC-014 原格式（客戶 2026-10-16 原文格式），其中 Effort 欄依 9.1 判定：

```
⏸️ 建議切換模式
下一階段：___
建議模型：___
建議模式：___
Effort：Low / Medium / High
原因：___
切換完成後請只回覆「改好了」。
```

然後停止。

- 等待 CI／workflow／稽核時**不得**要求切模式，也不回報等待狀態。
- ~~分級原則（客戶原文要點）：純 GitHub／Backlog／HANDOFF／低風險機械工作 → Low；一般 bug／tests／低風險 UI wiring → Medium；資料語意／財報計算／跨模組 correctness／架構 → High；投資公式／System Risk Cap／look-ahead／重大資料語意 → 高能力模型＋High。~~（2026-10-17 Effort 分級由 9.1 清單取代，決策者客戶，DEC-059；有意識的整合，不是漏刪 —— 舊行的分級方向與 9.1 一致，9.1 更細並加上「最低夠用」原則；舊行「高能力模型」一點仍保留為模型選擇參考，見下一點）
- 投資公式／System Risk Cap／look-ahead／重大資料語意：除 High 外，建議高能力模型（沿用 DEC-014 舊分級中的模型建議）。
- ~~不要頻繁切換；模型／模式／Effort 切換**不算**客戶裁示題。~~（2026-10-18 去重，決策者客戶，DEC-061；有意識的修改，不是漏刪 —— 「不要頻繁切換」已統一寫在 9.2，此處改為 pointer；後半句不變）
- 模型／模式／Effort 切換**不算**客戶裁示題；「不要頻繁切換」見 9.2。

## 第 10 節｜Branch／PR Lifecycle

- merge PR 屬常設授權（DEC-004）；前置條件不得省：獨立稽核無必修、CI 綠、改動範圍與派工相符。
- ⛔ 不 force push、不改寫已推送歷史、不為對齊報告改寫 Git history（客戶訊息 2026-10-16T13:48Z〈MSG 9〉第 8 點：「禁止：…- force push - 為了對齊報告而改寫 Git history」；該訊息的前提已被 MSG 10 更正，但第 8 點禁令為客戶原文、仍有效，見 `docs/DECISIONS.md` 0.1）。
- ⛔ **既有遠端分支刪除不得自主執行**，須客戶核准清單（DEC-012）。`main`、`data`、`v2`、`auto/recalibrate-20261001`、`claude/stock-dashboard-handoff-g9dtm0` 保留；handoff 分支是否已滿足「安全遷移」未裁示（`CV1-DR-05`）。
- 不恢復已刪除的舊 audit branch（DEC-012）。

## 第 11 節｜Conversation／Context Lifecycle

（機制依客戶 2026-10-16 列舉之共通治理機制建立，DEC-016。）

- 完整階段（milestone）結束時是建議換對話的時點；換對話前先達到 Safe Checkpoint（第 6 節）並更新~~四檔~~ 五檔（第 15 節 Handoff Save Check；2026-10-22 更新，有意識的變更，不是漏刪，決策者 客戶；DEC-068）。
- ~~新對話依序讀：`CLAUDE.md` → 本檔 → `docs/HANDOFF.md` → `docs/BACKLOG.md` → `docs/DECISIONS.md`；~~ **新對話的啟動程序、讀檔清單與優先序以第 15 節為準**（2026-10-22 更新，有意識的變更，不是漏刪，決策者 客戶；DEC-068：舊讀序未含 `docs/PROJECT_STATE.md`，且與第 15 節不同）；舊脈絡查 handoff 分支 `HANDOFF.md`（只讀）。做新 UI／產品方向相關工作時另讀 `docs/vnext/VNEXT_PRODUCT_BLUEPRINT.md`（2026-10-17 新增；依據 DEC-056 第 4 點、DEC-057）。
- 本檔（含第 3 節靜默巡航、第 9 節 Effort 自主管理）是**永久規則**：新對話讀完本檔即自動繼承，不需客戶再次提醒；不得只寫在 HANDOFF、對話或單次 prompt（DEC-059）。
- **不得要求客戶重講已落盤資訊**（`PROCESS.md` §1「嚴禁要求使用者重複解釋」；DEC-014「不重新摘要；不重問；不重做」）。
- AI 自動產生的對話壓縮摘要**不是客戶原文**，不得當 Decision 來源（DEC 來源類別規則，`docs/DECISIONS.md` 0.1）。

## 第 12 節｜新發現落盤

| 新發現 | 落盤位置 | 時機 |
|---|---|---|
| bug、data gap、tech debt、research | `docs/BACKLOG.md`（不在本次 scope 也要寫，不得只留在聊天紀錄） | 發現當輪 |
| 客戶裁示 | `docs/DECISIONS.md`（新 DEC，標來源類別）＋ BACKLOG 受影響列 customer decision 欄 | 收到當輪 |
| 現況、最近完成、blocker、下一步 | `docs/HANDOFF.md` | merge 後、milestone、換對話前 |
| evidence | commit、PR 說明、或 repo 內可追溯位置 | 產生當輪 |
| 會影響未來架構判斷的重要背景、研究結論、限制、模組關係（2026-10-22 新增列，DEC-068） | `docs/PROJECT_STATE.md`（只寫摘要＋出處；Candidate 不得寫成 Approved） | 產生當輪；最遲在第 15 節 Handoff Save Check |

來源：客戶 MSG 2 第 9 點「所有本輪發現但不在修復 scope 的事項，寫入正式 Backlog，不得只留在聊天紀錄。」；DEC-011。

## 第 13 節｜Investment Domain Constitution（股票領域硬規則索引）

> 只做索引、不重新定義；本文以各 DEC 的來源為準。全部規則**只來自本 repo 證據與客戶對本 repo 的裁示**。
> ⚠️ 規則有效**不代表 production 已全面合規**；已知違反者登記在 BACKLOG（例：`AUD-C14` 假中性 50）。

| # | 硬規則 | DEC |
|---|---|---|
| D1 | **New UI 是唯一開發主線**；新／舊 UI 以 main 實際 import／call path 判定 | DEC-019 |
| D2 | **舊 UI 凍結**：禁止任何修改；實體刪除屬不可逆操作，須 New UI readiness → 對等驗收 → production switch → 依賴稽核 → 客戶裁示 | DEC-019、DEC-020 |
| D3 | **資料層 ≠ AI 分析層**；AI 只讀已驗證資料 | DEC-027 |
| D4 | **AI 不得生成客觀市場／財務資料**、不得猜缺值、不得自成 primary source、不得把推論寫回客觀資料、不得偷改公式／權重／rule | DEC-027 |
| D5 | **missing ≠ 0**：未觀測 → 缺值；真實 0 → 0；不得 fillna(0)／自估合理值；填補須顯式＋log＋旗標 | DEC-026、`CLAUDE.md` §1 |
| D6 | **unavailable ≠ neutral**：缺資料不得偽裝成中性、利空或利多 | DEC-040、DEC-041 |
| D7 | **not evaluated ≠ safe**：未評估不得宣稱已通過（例：Sahm 無資料源不得宣稱紅線已通過） | DEC-040、DEC-044 |
| D8 | **provenance／as-of／freshness 必須真實**；freshness policy 為資料層／共用層 SSOT；cache 存活 ≠ 資料新鮮；觀測日＝真正所屬交易日 | DEC-040、DEC-029、DEC-028 |
| D9 | **No Look-ahead**：歷史決策不能看到當時尚未公開的資料（release_date／公告日對齊） | DEC-039 |
| D10 | **no fake precision**；不得以另一個百分比冒充缺失建議持股 | DEC-040 |
| D11 | 數值異常（NaN／inf）不顯示、不用替代值續算；統一文案「{項目}資料異常，無法計算，不下結論。」 | DEC-031 |
| D12 | 顏色不是唯一資訊載體 | DEC-040、DEC-051 |
| D13 | 缺有效 System Risk Cap → 建議持股比例「無法判定」；Required Core 任一缺 → 不產生新 Cap（7 天內沿用有效快照）；不得因缺資料放寬風控 | DEC-040、DEC-048、DEC-044 |
| D14 | 已停用訊號（M1B−M2）不得計分、不列「未評估」 | DEC-049、DEC-051 |
| D15 | 凍結的歷史 cohort／Decision 不改寫；方法版本切換須保留 | DEC-050、DEC-049、DEC-052 |
| D16 | 法人口徑統一官方口徑；**官方只缺外資時不跨來源拼 FinMind**，誠實顯示「未取得」（範圍限此情形；既有已核准的 fallback 鏈 —— DEC-008 Level 2、`CLAUDE.md` §2.1 衝突裁決 —— 不受影響） | DEC-033、DEC-035 |
| D17 | 正式加減碼比例未經「資料驗證 → 規則設計 → 回測／Shadow Mode → 客戶裁示」不得進 production | DEC-053 |
| D18 | 公式、資料語意、新／替換 production source、API／MCP 接入 production 資料鏈、重大 UI flow → **Decision Gate**（第 4 節） | DEC-009、DEC-008、DEC-003 |
| D19 | ~~全站不產生直接買賣建議（合規母法）—— ⚠️ 與客戶 2026-10-15 Action Layer 長期目標有**未調和張力**，見 `CV1-DR-01`；裁示前兩者皆不得被引用來推翻對方~~（2026-10-16 更新：`CV1-DR-01` 已裁示）<br>**方向性 Action 允許但有條件**（七種 Action；須可追溯資料＋正式規則、理由、as-of／freshness、關鍵風險；資料不足 →「無法判定」；不得繞過 Risk Cap；禁無證據強斷言；強 Action 不得只靠生成式 AI）；DEC-022 各護欄的去留逐項見 **DEC-054 承接表**（再平衡射程待確認，`CV1-FU-02`）；⚠️ 不是實作授權。~~⚠️ `S1-6_COMPLIANCE_COPY_GUIDE.md` 尚未同步（`CV1-FU-01`）；撰寫組讀法：該指南中由「全面禁止」推導出的判準，在改版前不得被引用來推翻 DEC-054。~~ `S1-6_COMPLIANCE_COPY_GUIDE.md` 已依 DEC-054 同步（2026-10-16，`CV1-FU-01` 結案；客戶訊息 2026-10-16T22:15Z）；再平衡仍依 DEC-022（`CV1-FU-02`）。 | DEC-054、DEC-055（S1-6 對齊；2026-10-17 補指標）、DEC-022（部分取代） |

**產品方向原則（Research Candidate，不是硬規則）**：客戶 2026-10-15 MSG 1 §1～§17 的 Core Decision＋Context Overlay、雙軌 Track A／B、Per-decision Core、Structured Thesis、Decision Log 瘦身、Live／Historical 分離、Safe Effective Cutoff、Event 來源分級、產業雷達不得假精確分數、Mobile 讀最新有效快照等，客戶自陳為方向與候選策略、尚無規格落地 → `docs/BACKLOG.md` `CV1-RC-01`（MSG 1 §18 推播「未來研究方向」與 §26 最終產品原則 → `CV1-RC-07`，2026-10-17 補指標）。施工前須依第 4 節走 Decision Gate。（2026-10-16 加註：MSG 1 §7 的 Action Layer **方向**已由 DEC-054 採用（D19）；DEC-054 稱為「既有風險護欄」的 Thesis、Core Decision／Context Overlay 在本 repo 仍無正式規格 → `CV1-FU-04`；本段其餘不變。）

📌 **2026-10-23 指標（append-only；客戶 2026-10-23 Freeze 指示）**：missing ≠ normal／HOLD、proxy ≠ real data、不得為了讓產品「有答案」而製造結論三條全站通則，見**第 16.1 節**（DEC-076）；上表 D1～D19 不變。

📌 **2026-10-17 指標（append-only）**：新 UI 產品方向「投資決策 OS／Investment Inbox」由客戶核准**方向**（不是實作授權）→ `docs/DECISIONS.md` **DEC-056**；方向項目 → `docs/BACKLOG.md` **第 5 節（`VN-*`）**。

## 第 14 節｜未調和的衝突

不在本檔裁定。全部登記於 `docs/BACKLOG.md` 第 4 節（`CV1-DR-*` Decision Required、`CV1-RC-*` Research Candidate），並由 `docs/DECISIONS.md` 第 6 節索引。暫行讀法：**任一套規則要求停下就停下**。

## 第 15 節｜Handoff Save Check 與跨對話 SSOT（客戶 2026-10-22 頒布；同日 DEC-068 修訂：五檔、PROJECT_STATE、Context Loss Check）

> 客戶 2026-10-22 頒布（經總管轉交；要點逐條收錄）。裁示紀錄見 `docs/DECISIONS.md` DEC-067；同日修訂見 DEC-068（客戶原文：「把以下規則正式納入 PROJECT_RULES，並與現有 §15 / DEC-067 整合，不建立競爭規則」）。本節是跨對話啟動與交接的**唯一**程序；第 11 節讀序以本節為準。

1. GitHub 是跨 ChatGPT、Claude Code 與新舊對話之間的專案共同 SSOT。
2. ~~任何完整工作階段／對話準備結束前，執行 **Handoff Save Check**：永久治理變更 → `PROJECT_RULES.md`；客戶正式裁示 → `docs/DECISIONS.md`；未完成工作 → `docs/BACKLOG.md`；current state／blockers／next safe point → `docs/HANDOFF.md`。~~（2026-10-22 更新，有意識的變更，不是漏刪，決策者 客戶；DEC-068：加第五項）
   **現行**：任何完整工作階段／對話準備結束前，執行 **Handoff Save Check**：
   1. 新永久規則 → `PROJECT_RULES.md`；
   2. 客戶正式裁示 → `docs/DECISIONS.md`；
   3. 所有未完成事項 → `docs/BACKLOG.md`；
   4. current／blocker／next safe point → `docs/HANDOFF.md`（短版）；
   5. 仍有效的完整專案狀態、架構關係、重要背景與限制 → `docs/PROJECT_STATE.md`。
3. ~~任何新 ChatGPT／Claude Code 對話開始時：(1) 先重新取得 GitHub 最新實況；(2) 讀 `PROJECT_RULES.md`／`docs/DECISIONS.md`／`docs/BACKLOG.md`／`docs/HANDOFF.md`；(3) 驗證 main SHA、open／draft PR、CI／QA 與相關 branch；(4) GitHub 實況優先於 HANDOFF、AI memory、舊聊天摘要；(5) 發現不一致時不得自行猜測，依正式證據校正。~~（2026-10-22 更新，有意識的變更，不是漏刪，決策者 客戶；DEC-068：讀檔加 PROJECT_STATE、驗證加 relevant commits／diffs、優先序加 PROJECT_STATE 一層、不一致時必要修正文件）
   **現行**：任何新的 Claude Code 或 ChatGPT 完整專案對話開始時：
   1. `git fetch` 最新 GitHub。
   2. 讀：`PROJECT_RULES.md`、`docs/DECISIONS.md`、`docs/BACKLOG.md`、`docs/HANDOFF.md`、`docs/PROJECT_STATE.md`。⚠️ 撰寫組讀法（非客戶原文）：`CLAUDE.md` 依第 0.1 節是上位憲法，客戶清單未列**不代表免讀**；做新 UI／產品方向工作時另讀 Blueprint（第 11 節）。
   3. 驗證：main SHA、open／draft PR、relevant commits／diffs、CI／QA、relevant branches。
   4. 優先序：**GitHub factual reality > `docs/HANDOFF.md` > `docs/PROJECT_STATE.md` 中的狀態快照 > AI memory／conversation summary**（與第 1.1 節 Fact Truth 同向；這是判斷「現在實際是什麼」的順序，不是規範效力順序）。
   5. 文件與 GitHub 實況不一致時：以 GitHub evidence 為準；不得猜測；必要時修正正式文件。
4. 不得把完整聊天紀錄、腦暴或未裁示想法大量寫入 GitHub；只保存會影響未來工作的正式專案狀態。
5. **Context Loss Check**（2026-10-22 新增，DEC-068）：Claude 或 ChatGPT 的完整專案對話結束前，必須問：「如果下一個 AI 完全看不到目前聊天內容，只讀 GitHub，它能否正確理解目前專案並安全接手？」至少檢查：
   - **A.** 有沒有正式裁示只存在聊天裡？→ 有則分類進 `docs/DECISIONS.md`。
   - **B.** 有沒有未完成工作只存在聊天裡？→ 有則分類進 `docs/BACKLOG.md`。
   - **C.** 有沒有永久治理規則只存在聊天裡？→ 有則分類進 `PROJECT_RULES.md`。
   - **D.** 有沒有目前 blocker／next safe point 只存在聊天裡？→ 有則分類進 `docs/HANDOFF.md`。
   - **E.** 有沒有會影響未來架構判斷的重要背景、研究結論、限制或模組關係，只存在聊天裡？→ 有則分類進 `docs/PROJECT_STATE.md`。
   - **F.**（2026-10-23 新增，DEC-073）`docs/HANDOFF.md` 是否已記錄**下一階段建議模型／能力等級與建議 Effort**？→ 否則補記於 HANDOFF 第 0 節。
   - ⛔ **任何答案為「有」且尚未保存時：不得宣告交接完成。**
   - 分類時：尚未核准的構想一律進 BACKLOG 的 Candidate／Decision Gate，⛔ 禁止升格成 Approved；已正式存在者不重複登記。
6. **Model／Effort Gate 納入啟動與交接**（2026-10-23 新增，DEC-073；客戶原文「並納入 Context Loss Check／交接規則，確保新 Claude 對話也會自動讀到，不再依賴客戶每次提醒。」）：(1) 新對話完成第 3 點啟動程序後、以及每個下一完整階段／Batch 開始前，**必須執行第 9.0 節強制 Model／Effort Gate**；(2) `docs/HANDOFF.md` 第 0 節須記錄**下一階段建議模型／能力等級與建議 Effort**（Context Loss Check F 項）；(3) HANDOFF 記錄的建議只是參考，新對話仍須依實際工作重新判斷，不得當成已切換的證明（客戶原文第 3 步「不得自行假設模型或 Effort 已切換」）。

## 第 16 節｜交接 Freeze 永久規則（客戶 2026-10-23 Freeze 指示）

> 出處：**客戶 2026-10-23 Freeze 指示**（2026-10-23 約 23:05 台北訊息，經總管轉交，撰寫組依轉交全文逐字比對；客戶第 9、13、14、15、16、21、22 節）。裁示紀錄與產品語意部分見 `docs/DECISIONS.md` **DEC-076**。
> 本節**不重寫**既有條文：已存在者只列引用；只有「既有條文未涵蓋」的部分才在此新增（標 🆕）。與既有條文衝突時依第 0.1 節，並登記 `docs/BACKLOG.md` 第 4 節；撰寫組比對未發現硬衝突（單組，⚠️ 待第二組驗，`CLAUDE.md` §-2 規則 6）。

### 16.1 Data ≠ AI Reasoning（客戶第 9 節）

客戶原文：「Data Layer 只負責：acquire、clean、normalize、validate、provenance。AI Layer 只能：讀取已取得、可追溯、已驗證狀態清楚的資料做分析／解釋。」

| 客戶永久規則 | 既有位置 | 狀態 |
|---|---|---|
| Data Layer／AI Layer 分工 | 第 13 節 D3、D4（DEC-027） | 已存在；客戶第 9 節分工清單為本則補充措辭 |
| missing ≠ 0 | D5（DEC-026、`CLAUDE.md` §1） | 已存在 |
| missing ≠ neutral | D6（DEC-040、DEC-041） | 已存在 |
| 🆕 missing ≠ normal | DEC-074 客戶原文「不得把缺少真實 breadth 當成 0、中性或正常」（限 breadth） | **本節擴為全站通則** |
| 🆕 missing ≠ HOLD | 無既有條文 | **本節新增**：缺資料不得被呈現為「維持／續抱／不動作」這類看似已判斷的 Action；應顯示「無法判定／資料不足」（後半句為撰寫組讀法；D10、D13 同向） |
| 🆕 proxy ≠ real data | DEC-037（M1B 代理只顯示不計分）、DEC-062 Q5、DEC-074（代理廣度不得計分） | **本節擴為全站通則**：代理值不得以正式資料的身分顯示或計分；顯示時須標明是代理 |
| 缺資料與真 0 必須區分 | D5 | 已存在 |
| 顏色不得是唯一資訊載體 | D12（DEC-040、DEC-051） | 已存在 |
| 🆕 不得為了讓產品「有答案」而製造結論 | DEC-074「不得因為產品希望「有結論」而補出投資結論」、DEC-075「缺資料不得為了維持畫面結論而補結論」 | **本節擴為全站通則**（不限 breadth／位階） |

### 16.2 Model／Effort Escalation Gate（客戶第 13 節）

- **已存在**：第 9.0 節（DEC-073）＋第 15 節第 6 點；Low／Medium／High 清單見 9.1，與客戶第 13 節清單同向。
- 🆕 客戶第 13 節補充（原文）：「不得：默認固定 Opus / High；默認固定 Sonnet / Medium；靜默用不足能力繼續；假設客戶已切換模型。」
- 🆕 **中途風險升高亦同**（客戶原文「中途風險升高亦同。」）：工作進行中發現風險／複雜度升高到超出目前模型或 Effort 時，同樣適用 9.0 停手規則 —— 先到最近安全停點（第 6 節）再停手回報，⛔ 不得以「已經開始了」為由用不足能力繼續推進。
- 客戶原文：「這是 Silent Autonomous Cruise 的正式例外。」（與 9.0 同向）

### 16.3 Silent Autonomous Cruise（客戶第 14 節）

**已存在**：第 3 節（DEC-007、DEC-059）。客戶第 14 節原文：「已授權、安全、可逆工作：靜默自主執行。不要：每一步回報、每個 agent 回報、每個 CI 狀態都通知、重複「沒有新資訊」。只在：1. 需要客戶裁示；2. 觸發停手條件；3. 完整工作階段真正完成；才回報。」—— 與第 3 節三種可打斷情況同向（「觸發停手條件」含第 4 節表、16.4、9.0 不足停手）；本節不另立規則。

### 16.4 停手條件（客戶第 15 節）

客戶原文：「遇到停手條件：STOP → 說明 → 等客戶裁示。」逐項對照：

| 客戶列舉 | 既有位置 | 狀態 |
|---|---|---|
| layout／information architecture change requiring decision | 第 4 節 #7（DEC-003） | 已存在 |
| irreversible action | 第 4 節 #8 | 已存在 |
| investment semantics | 第 4 節 #1、#2 | 已存在 |
| 🆕 L3 data layer | 第 9.1 節 High 清單（DEC-073）只作 Effort 判斷 | **本節新增為停手條件**：涉及 L3／資料層語意的變更（不含已授權批內的修正）→ 停手請示 |
| new external source | 第 4 節 #3、#4 | 已存在 |
| 🆕 new wording／spec gap requiring customer decision | 無明文 | **本節新增**：規格沒寫、且需要客戶決定的新文案／語意空白 → 停手請示（純技術空白仍內部自決，`CLAUDE.md` §-1.5.A-4 判準） |
| threshold／formula／weight change | 第 4 節 #1 | 已存在 |
| customer decision required | 第 4 節 #10 | 已存在 |
| same-file retry limit | 第 4 節「客觀停手門檻」（DEC-005、DEC-010） | 已存在 |
| 🆕 CI／QA real failure and next fix not already authorized | 無明文 | **本節新增**：CI／QA 出現真實失敗，且下一個修法不在既有授權範圍 → 停手請示；修法單一且在授權內者仍依第 4 節反向禁令自行修 |

### 16.5 舊 UI 不得提前刪除（客戶第 16 節）

- **已存在**：第 13 節 D2（DEC-019、DEC-020）、第 4 節 #8。
- 🆕 客戶第 16 節原文：「新 UI 成立以前，舊 UI 是重要 capability / logic reference。只有完成：capability inventory、new UI mapping、implementation、coverage validation、regression、customer approval 後，才進入舊 UI removal Decision Gate。不得把「新版已經比較漂亮」當作刪除舊 UI 的理由。」
- 讀法（撰寫組）：與 DEC-020 路線**取聯集**，兩邊的前置步驟都要做；DEC-020「不得追求 100% parity 無限延後」不變（客戶第 5 節所稱是「重要能力」承接，不是 100% parity）。追蹤項見 `docs/BACKLOG.md`（Old UI Capability → New UI Coverage Matrix，由 BACKLOG 撰寫組登記）。

### 16.6 Branch 刪除（客戶第 21 節）

- **已存在**：第 10 節、第 4 節 #8（DEC-012）。
- 🆕 客戶第 21 節原文：「客戶既有方向：最後再一次清。本次交接不要為了乾淨而刪歷史 branch。只需記錄：relevant branch、哪些可能是 cleanup candidate、是否存在 unique commit。未來刪除前重新查 GitHub。branch deletion 視為不可逆治理動作。」
- 落點：branch 清單與 cleanup candidate 屬狀態，記在 `docs/HANDOFF.md`／`docs/PROJECT_STATE.md`，⛔ 不是刪除授權。

### 16.7 Production 安全狀態（客戶第 22 節）

- 🆕 客戶第 22 節原文：「重新核實並保存：PRODUCTION_WRITE_APPROVED、Daily Schedule、production write、external side effects。如果仍是：PRODUCTION_WRITE_APPROVED=False 就明確保存。不要因交接而自行開啟。」
- 規則：`shared/risk_cap_history_policy.py::PRODUCTION_WRITE_APPROVED` 的開啟只能走 DEC-066 A 的獨立 PR 流程並經客戶核准；⛔ 交接、Freeze、文件同步、CI 修復**一律不得**改動此旗標；Daily Schedule 仍 NOT APPROVED（DEC-066 F）。現值以程式為準（2026-10-23 Freeze 實查為 `False`，見 `docs/HANDOFF.md`）。

### 16.8 交接優先順序與新 AI 接手（客戶第 1、2、13 節）

- **交接優先順序**：**GitHub 實況 > `docs/HANDOFF.md` > `docs/PROJECT_STATE.md` > AI 記憶／聊天摘要**（客戶第 1 節原文「GitHub 實況 > HANDOFF > PROJECT_STATE > AI 記憶／聊天摘要。若文件與 GitHub 不一致：先修正文件。」）。已存在於第 15 節第 3 點第 4 款、第 1.1 節，同向；本款只重申。
- **新 AI 接手時**：(1) `git fetch` 並實查 GitHub；(2) 必讀五個 SSOT：`PROJECT_RULES.md`、`docs/DECISIONS.md`、`docs/BACKLOG.md`、`docs/HANDOFF.md`、`docs/PROJECT_STATE.md`（上位 `CLAUDE.md` 依第 0.1 節同樣須讀）；(3) **動工前先跑第 9.0 節 Model／Effort Gate**。已存在於第 15 節第 3、6 點；本款只重申。
