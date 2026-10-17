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

### 0.3 四檔分工（Governance Truth）

| 文件 | 管什麼 | 不管什麼 |
|---|---|---|
| `PROJECT_RULES.md`（本檔） | AI 工作規則入口；股票領域硬規則索引 | 規格本文；既有條文本文 |
| `docs/DECISIONS.md` | 客戶裁示與正式決策（DEC-NNN，附可追溯來源與取代鏈） | AI 推論（不得寫成客戶裁示） |
| `docs/BACKLOG.md` | 所有未完成工作、待裁示題、Research Candidate | 動工授權 |
| `docs/HANDOFF.md` | 短、可接手的現況：在哪、最近完成、blocker、下一安全接手點 | 完成或正確的證明；完整歷史 |

**Blueprint 指標**（2026-10-17 新增，DEC-057）：`docs/vnext/VNEXT_PRODUCT_BLUEPRINT.md` ＝ DEC-056 第 4 點「Blueprint：最終產品方向」的承載者（附 `docs/vnext/UI_AUDIT_2026-10-17.md`）。⚠️ 它**不是實作授權**、不帶 Decision 效力；其中線框與 `BP-DR-*` 未經客戶裁示前不得施工（DEC-003、DEC-057）；與本表四檔或 `CLAUDE.md` 牴觸時以後者為準。上表標題「四檔」不因本指標改變。

**上位與既有文件（本批不改）**：`CLAUDE.md`、`PROCESS.md`、`ARCHITECTURE.md`、`SPEC.md`、`STATE.md`、`docs/v2/spec/*`。
**歷史全文**：分支 `claude/stock-dashboard-handoff-g9dtm0` 的 `HANDOFF.md`（約 5150 行，含舊待辦、等你答、逐字收錄的客戶裁示）—— **未刪除、未凍結宣告**；其中尚未遷入的待辦見 `docs/BACKLOG.md` `BL-MIGRATE-1` 📌 註。

## 第 1 節｜Fact Truth vs Governance Truth（雙軌）

### 1.1 Fact Truth（「現在實際是什麼」）

依下列順序取證，前者推翻後者：

1. **GitHub**：main SHA、PR 狀態、check-run conclusion、遠端分支；
2. **code 與 tests 的實際輸出**；
3. 正式文件（`CLAUDE.md`、`PROCESS.md`、`docs/v2/spec/*`）—— ⚠️ 本層為撰寫組讀法插入，客戶原文只有三層（見下）；
4. 本四檔；
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
- **只有三種情況可以主動打斷客戶**：
  1. **完整階段完成**：implementation＋tests＋audit＋CI＋merge＋main verification 已達該階段完成條件（第 7 節）；精簡回報，原則 ≤5 行（完整證據在 PR，DEC-060）。
  2. **真正需要客戶裁示**：即第 4 節「必須停下問客戶」表（客戶 2026-10-17 清單的逐項對映見該表下方註）；已經有正式 DEC 的問題不得重新詢問（DEC-013）。可超過 5 行，但只保留完成裁示所需資訊（DEC-060）。
  3. **需要切換 Effort**：僅依第 9 節 Minimum Sufficient Effort 規則，在安全停點提醒。
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
- **確認清單**：working tree 是否乾淨、main SHA（附時間）、open PR、main CI、未提交內容與殘留 worktree／stash、四檔是否同步、下一步。
- ⚠️ 已知「現存未處理物件」：舊 UI 壓測 `stash@{0}` **不恢復、不提交、不推送**（DEC-019）；只在原容器本機，接手者不得嘗試還原。

## 第 7 節｜Definition of Done

implementation → relevant tests（含真實引擎路徑 regression）→ independent audit／red team → required fixes → push → PR → CI → merge → **main verification**（main SHA＋main CI conclusion）→ 更新 `docs/BACKLOG.md`（結案列附 PR＋merge sha＋main CI run）、`docs/DECISIONS.md`（若有新裁示）、`docs/HANDOFF.md`。

- 沒跑的就寫沒跑；不得虛構驗證；不得把自己的結果寫成第二組已複驗。
- 來源：客戶 MSG 1 §24、MSG 2 第 6 點（研究 → 實作 → tests → independent audit → push → PR → CI → fix → merge → main verification → handover）；`docs/BACKLOG.md` 0.3 第 1 條；`CLAUDE.md` §-2 規則 3、6。

## 第 8 節｜Independent Audit／Red Team

- 實作者不得自己驗收自己；調查與稽核獨立分派、多組不同角度，不由同一組自己查自己（DEC-001；`CLAUDE.md` §-2 規則 3／4）。
- **稽核組數下限依 `CLAUDE.md` §-2 規則 4**：同一件事至少派**多組不同角度**的獨立 agent，調查與稽核尤其不可單點、不可自己查自己；本檔不另設較低門檻。QA 分級沿用 DEC-010（A／B／C）、跨級取最高，但分級**不得**低於 §-2 規則 4 的下限。
- **治理文件**：C 級原為「自驗不派稽核」，但客戶 2026-10-16 明令本批派獨立第二組 evidence audit（DEC-016）；是否全面適用未裁示 → `CV1-DR-02`。在客戶裁示前，**動到四檔的 Decision／硬規則索引時比照本批派獨立稽核**（暫行取嚴）。

## 第 9 節｜Model／Mode／Effort 自主管理（DEC-014；Effort 部分由 DEC-059 強化）

~~每個下一完整階段開始前自行判斷目前模型／模式／Effort 是否合適；**只有切換有明顯品質或額度效益時才中斷**。~~（2026-10-17 整合進下方 9.1～9.3，決策者客戶，DEC-059；有意識的整合，不是漏刪 —— 「階段開始前自判」保留於 9.1，「有明顯效益才中斷」保留於 9.3（模型／模式），Effort 改依 9.2「明顯應使用不同 Effort 即主動提醒」）

### 9.1 Minimum Sufficient Effort（推理強度夠用即可；DEC-059）

**原則**：使用「**能可靠完成下一完整階段的最低 Effort**」，避免不必要 token／額度浪費。不得因為 High 比較強就預設 High；若 Low 足夠，不使用 Medium；若 Medium 足夠，不使用 High。專案 AI 在每個「下一完整工作階段」開始前，必須自行判斷所需 Effort：

| Effort | 適用（客戶 2026-10-17 原文清單） |
|---|---|
| **Low** | GitHub 狀態確認；HANDOFF／BACKLOG 一般同步；已知答案的機械性文件修改；小型、低風險、規格完全明確的工作 |
| **Medium** | 一般 UI／UX 實作；Blueprint／UX Audit；單一模組正常 bug fix；一般測試與低風險 wiring；有一定推理需求、但不涉及核心投資語意的工作 |
| **High**（只在明顯需要時） | 投資公式；Risk Cap；選股核心邏輯；Action／Position Sizing 核心規則；Thesis 正式判定規則；financial／data semantics；Point-in-Time／look-ahead correctness；跨模組重大架構；高風險 correctness 問題；多個合理方案需要深入權衡 |

- 等待 CI、等待 audit、等待 workflow 等待狀態，**不得**要求提高 Effort。
- ⚠️ Effort 只決定推理強度，**不改變**派工、獨立稽核與揭露義務（`CLAUDE.md` §-2 規則 1／4／6；第 3 節限定第 2、4 條）：Low 不等於免派工、免稽核。

### 9.2 Effort 主動提醒（DEC-059）

如果「下一完整階段」明顯應使用不同 Effort（較高**或較低**），專案 AI 必須在**安全停點**（第 6 節）主動提醒客戶，不得等客戶詢問。格式固定精簡為（客戶 2026-10-17 原文格式）：

```
⏸️ 建議切換推理強度
下一階段：___
建議 Effort：Low / Medium / High
原因：___
切換完成後請回覆「改好了」。
```

- **雙向提醒**：提醒可升可降。客戶 2026-10-17 追加原文：「若客戶目前選擇的 Effort 高於下一階段實際所需，且已到安全停點，也應主動提醒「可以降低 Effort」，以避免不必要的 token／額度消耗。」降低提醒同受下方時機限制。範例（客戶原文，逐字）：

```
⏸️ 建議切換推理強度
下一階段：一般文件同步
建議 Effort：Low
原因：工作機械性且規格明確，目前 High 無必要。
切換完成後請回覆「改好了」。
```

- ~~若目前 Effort 已足夠：不要提醒；不要每次重複報告目前 Effort；直接工作。~~（2026-10-17 同批客戶追加「可以降低 Effort」提醒後改讀，決策者客戶，DEC-059；有意識的修改，不是漏刪 —— 「已足夠」會把「高於所需」也算進去而不提醒，與降低提醒衝突）
- 若目前 Effort **恰好合適**：不要提醒；不要每次重複報告目前 Effort；直接工作。
- 不得在下列時機要求切換：未 commit 的實作中途；PR 尚在修正中途；CI 正在跑；一個不可安全中斷的完整工作階段中。
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
- 不要頻繁切換；模型／模式／Effort 切換**不算**客戶裁示題。

## 第 10 節｜Branch／PR Lifecycle

- merge PR 屬常設授權（DEC-004）；前置條件不得省：獨立稽核無必修、CI 綠、改動範圍與派工相符。
- ⛔ 不 force push、不改寫已推送歷史、不為對齊報告改寫 Git history（客戶訊息 2026-10-16T13:48Z〈MSG 9〉第 8 點：「禁止：…- force push - 為了對齊報告而改寫 Git history」；該訊息的前提已被 MSG 10 更正，但第 8 點禁令為客戶原文、仍有效，見 `docs/DECISIONS.md` 0.1）。
- ⛔ **既有遠端分支刪除不得自主執行**，須客戶核准清單（DEC-012）。`main`、`data`、`v2`、`auto/recalibrate-20261001`、`claude/stock-dashboard-handoff-g9dtm0` 保留；handoff 分支是否已滿足「安全遷移」未裁示（`CV1-DR-05`）。
- 不恢復已刪除的舊 audit branch（DEC-012）。

## 第 11 節｜Conversation／Context Lifecycle

（機制依客戶 2026-10-16 列舉之共通治理機制建立，DEC-016。）

- 完整階段（milestone）結束時是建議換對話的時點；換對話前先達到 Safe Checkpoint（第 6 節）並更新四檔。
- 新對話依序讀：`CLAUDE.md` → 本檔 → `docs/HANDOFF.md` → `docs/BACKLOG.md` → `docs/DECISIONS.md`；舊脈絡查 handoff 分支 `HANDOFF.md`（只讀）。做新 UI／產品方向相關工作時另讀 `docs/vnext/VNEXT_PRODUCT_BLUEPRINT.md`（2026-10-17 新增；依據 DEC-056 第 4 點、DEC-057）。
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

📌 **2026-10-17 指標（append-only）**：新 UI 產品方向「投資決策 OS／Investment Inbox」由客戶核准**方向**（不是實作授權）→ `docs/DECISIONS.md` **DEC-056**；方向項目 → `docs/BACKLOG.md` **第 5 節（`VN-*`）**。

## 第 14 節｜未調和的衝突

不在本檔裁定。全部登記於 `docs/BACKLOG.md` 第 4 節（`CV1-DR-*` Decision Required、`CV1-RC-*` Research Candidate），並由 `docs/DECISIONS.md` 第 6 節索引。暫行讀法：**任一套規則要求停下就停下**。
