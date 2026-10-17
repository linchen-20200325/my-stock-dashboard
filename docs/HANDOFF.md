# HANDOFF — 現行交接（my-stock-dashboard）

> **用途**：只寫「現在在哪、最近完成、blocker／Decision Required、下一安全接手點」，並指向其他三檔。**不是完成證明**（`PROJECT_RULES.md` 第 1.3 節）；接手時先依第 5 節重查 GitHub。
> 本檔由 Constitution v1.0 治理 PR #864 建立（DEC-016）；~~本版隨 DEC-054（`CV1-DR-01` 裁示）治理 PR 一起合併（分支 `claude/stock-cv1-dr01`）。~~ ~~本版隨 `CV1-FU-01`（S1-6 合規指南對齊 DEC-054）PR 一起合併（分支 `claude/stock-cv1-fu01`；2026-10-16 更新）。~~ **本版由對話收尾同步 PR 更新**（分支 `claude/stock-close-sync`；2026-10-17，客戶 2026-10-17T01:31Z「對話結束完整性檢查」；純文件同步）。最後一個功能／治理合併為 #866；本同步 PR 合併後 main 會前進，cron 亦會推進 tip —— **main tip 以 GitHub 為準**。
> **完整歷史**：分支 `claude/stock-dashboard-handoff-g9dtm0` 的 `HANDOFF.md`（`1510f3f0`，約 5150 行；**未刪除**；其 current-state 行寫 main＝`fa26914b`，已過期、不含 #863）。本檔不搬歷史。

## 1. 現況（量測：2026-10-17，`origin/main`＝`2647a0fd`；main CI 與 open PR 由 GitHub REST API 實測）

| 項目 | 現況 |
|---|---|
| 最後一個功能／治理合併（非 cron、非本收尾同步 PR） | `2647a0fd`（#866 squash merge，`治理：CV1-FU-01 合規指南 S1-6 與 DEC-054 對齊（DEC-055）`）；parent `f91dfb56`（#865） |
| main tip | 量測時 tip＝`2647a0fd`。本收尾同步 PR 合併後 tip 會前進；cron 亦會持續推進 tip（例：`🤖 每日總經歷史增量`、`🤖 板塊資金泡泡圖每日增量`、`🤖 總經燈號落地`），引用前重查 |
| main CI | `2647a0fd`：run 38980399324 `success`（Fast checks、Slow tests 兩個 job 皆 success；2026-10-17 REST API 實測） |
| open PR | 量測時 0（本收尾同步 PR 開立前）；現況以 GitHub 為準 |
| active work | **無 —— 安全停點**。本對話已收尾（客戶 2026-10-17T01:31Z「準備結束本對話並切換到新的 Claude Code 對話」「不開始下一個 Batch」）；下一批須客戶指示 |
| ⚠️ 過期值 | `70416a6a` 是 #852／Z65（2026-10-15）的舊 commit，**不是目前 main**；`f91dfb56`（#865）亦已不是最後合併 |

## 2. 最近完成（皆已合併、main CI success）

| PR | merge sha | 內容 |
|---|---|---|
| #866 | `2647a0fd` | DEC-055：`CV1-FU-01` 結案，S1-6 合規指南與 `AI_QA_DISCLOSURE` 對齊 DEC-054（治理／規格文件、`wf_page_why.js` 線框、`AI_QA_DISCLOSURE` 字串）；新增 `CV1-FU-05`、`CV1-FU-06`；main CI run 38980399324 success（2026-10-17 實測） |
| #865 | `f91dfb56` | DEC-054：裁示 `CV1-DR-01`，方向性 Action 有條件允許、部分取代 DEC-022（治理文件）；main CI run 38939311066 success（2026-10-17 REST API 實測） |
| #864 | `66fee4e8` | Project AI Constitution v1.0 治理文件（`PROJECT_RULES.md`、`docs/DECISIONS.md`、`docs/BACKLOG.md`、本檔）；main CI run 38921405387 success |
| #863 | `f0a6c474` | BACKLOG：AUD-C21／PQ-C6-3 結案登記（docs-only） |
| #862 | `fa26914b` | 新 UI 獨立 Risk Cap 快照檔＋卡面揭露資料完整性（DR-2026-10-16-4／5；DEC-051、DEC-052） |
| #861 | `3dfad58d` | BACKLOG：AUD-C6／C7 結案登記（docs-only） |
| #860 | `ef7cf41c` | 停用 M1B−M2 腿＋Required Core 閘門（DR-2026-10-16-1／2；DEC-048、DEC-049） |
| #859 | `8b8f9e1e` | `revenue_yoy` 改單季對去年同季單季（DR-2026-10-16-3；DEC-050） |

各 PR 的 main CI run 編號見 `docs/BACKLOG.md`「3. 已結案」（#864、#865、#866 非 Backlog「3. 已結案」項，run 編號寫在上表）。

## 3. Blocker／Decision Required（只列指標，細節見 BACKLOG）

- **PQ-C4-2**：prescreen「三率三升」累計 vs 單季（`docs/BACKLOG.md` §1.1、`AUD-C4-3UP`）—— 待客戶裁示。
- **PQ-C3-1**：舊／新 UI 加碼措辭與計數說明（`docs/BACKLOG.md` §1.1、`AUD-C3-FU`）—— 待客戶裁示。
- ~~**CV1-DR-01**（高）~~：**已裁示**（2026-10-16，DEC-054；`docs/BACKLOG.md` DR-2026-10-16-6）—— 不再是 blocker。後續一致性項（只列指標）：~~`CV1-FU-01`（S1-6 合規指南未同步）~~（2026-10-16 改版結案，DEC-055／DR-2026-10-16-7；#866）、`CV1-FU-02`（再平衡射程，待裁示）、`CV1-FU-03`（待確認題）、`CV1-FU-04`（Thesis 等無正式規格）、`CV1-FU-05`（AI 轉述正式 Action／通用免責，Action Layer 設計批）、`CV1-FU-06`（`persona.py`「請給出明確的動作」，既有產品 code 衝突，本批未改）—— 見 `docs/BACKLOG.md` 第 4.1 節。
- 其餘 Constitution 遷移時未升格的項目：`docs/BACKLOG.md` 第 4 節（`CV1-DR-*`、`CV1-RC-*`）。
- **舊待辦與「等你答」**：handoff 分支 `HANDOFF.md@1510f3f0` §3（1）、§4（91）、§5（42）、§6 等你答（25 題）及不佔列註，尚未遷入、仍以該檔為權威 —— 見 `docs/BACKLOG.md` `BL-MIGRATE-1` 補註。
- 2026-10-17 收尾同步補登：`CV1-RC-07`（客戶 MSG 1 §18 推播三類警報方向、§26 最終產品原則；原只在聊天）—— Research Candidate，不構成動工授權。
- 供客戶知悉：`AUD-C28`（「必要與選用訊號皆已評估」與薩姆從未評估並存）。

## 4. 下一安全接手點

1. ~~DEC-054 治理 PR：evidence audit → PR → CI → merge → main verification（客戶 2026-10-16T16:26Z 指示）。~~（#865 已合併）~~`CV1-FU-01` 批（DEC-055）：evidence audit → PR → CI → merge → main verification（客戶 2026-10-16T22:15Z 指示）。~~（#866 已合併，2026-10-17 更新）**目前無進行中工作**；新對話先依第 5 節重查 GitHub，再**等待客戶指示下一批**。
2. **停在安全點**（2026-10-17 收尾；客戶原文「不開始下一個 Batch」）。⛔ 客戶原文「不要自行開始 CV1-DR-02 或產品功能 Batch。」（2026-10-16T22:15Z 重申：不開始 CV1-DR-02、不開始產品 Action Layer）；⛔ **DEC-054 不是 Action Layer 實作授權**（DEC-015、DEC-002、DEC-009）。
3. BACKLOG 各列的 next action **不構成動工授權**；有客戶指派或實際 bug 觸發才動（`CLAUDE.md` §-1）。

## 5. 新對話 takeover

1. `git fetch origin`；`git log -1 --format='%H %P' origin/main` 與本檔第 1 節比對；不一致 → 以 GitHub 為準，先更新本檔。
2. 查 open PR 與 main 最新非 cron commit 的 check-run `conclusion`。
3. 依序讀：`CLAUDE.md` → `PROJECT_RULES.md` → 本檔 → `docs/BACKLOG.md` → `docs/DECISIONS.md`；舊脈絡查 handoff 分支 `HANDOFF.md`（只讀）。
4. 確認 working tree 乾淨；⛔ 不還原舊 UI 壓測 `stash@{0}`（DEC-019）。
5. 不要求客戶重講已落盤資訊（`PROJECT_RULES.md` 第 11 節）。

## 6. 本檔沒查證的部分

- open PR＝0、CI conclusion 為 2026-10-17 量測當下快照；本收尾同步 PR 開立後 open PR 至少為 1。
- ~~「cron commit 只動 `data_cache/**`」只對 `f0a6c474..82e19dbd` 實測（`git diff --name-only`），不宣稱未來 cron 亦然。~~（2026-10-16 更新：該量測屬上一版快照；本版未重測 cron 改動範圍）
- `CV1-FU-*` 的衝突掃描為單組 `git grep`，「其他地方無衝突」未經第二組驗證（`CV1-FU-01` 批的全 repo 掃描同為單組）。
- ~~#865 的 main CI run 38939311066 success 為總管轉述，撰寫組未重查。~~（2026-10-17：收尾同步撰寫組以 REST API 重查，head `f91dfb56`、conclusion `success`）
- 「客戶訊息中未入檔的長效指示只有 `CV1-RC-07` 兩段」為收尾同步撰寫組單組掃描（本 session 客戶訊息逐則與四檔比對；MSG 4、8 為 AI 摘要，不作來源），未經第二組驗證。
- 本檔由單一撰寫組撰寫，待第二組獨立 audit（`CLAUDE.md` §-2 規則 6）。
