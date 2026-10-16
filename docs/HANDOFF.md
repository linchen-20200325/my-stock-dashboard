# HANDOFF — 現行交接（my-stock-dashboard）

> **用途**：只寫「現在在哪、最近完成、blocker／Decision Required、下一安全接手點」，並指向其他三檔。**不是完成證明**（`PROJECT_RULES.md` 第 1.3 節）；接手時先依第 5 節重查 GitHub。
> **本檔隨 Constitution v1.0 治理 PR 一起合併**（客戶 2026-10-16 裁示，`docs/DECISIONS.md` DEC-016）。下表為寫作當下快照；合併本 PR 後 main 會前進，**以 GitHub 為準**。
> **完整歷史**：分支 `claude/stock-dashboard-handoff-g9dtm0` 的 `HANDOFF.md`（`1510f3f0`，約 5150 行；**未刪除**；其 current-state 行寫 main＝`fa26914b`，已過期、不含 #863）。本檔不搬歷史。

## 1. 現況（量測：2026-10-16 14:09 UTC，`git fetch` ＋ GitHub REST API）

| 項目 | 現況 |
|---|---|
| 最後一個非 cron 的 main commit | `f0a6c474`（#863 merge，`docs(BACKLOG)：AUD-C21／PQ-C6-3 結案（#862）`）；parent `fa26914b`（#862） |
| main tip | 其後只有每日 cron 資料 commit（只動 `data_cache/**`）：`8bb52427`「🤖 每日總經歷史增量：2026-10-16」→ 量測時 tip `82e19dbd`「🤖 板塊資金泡泡圖每日增量：2026-10-16」。cron 會持續推進 tip，引用前重查 |
| main CI | `f0a6c474`：Fast checks、Slow tests（informational）`success`（`8bb52427` 的 update-sector-flow `success`；`82e19dbd` 量測時尚無 check-run） |
| open PR | 0（量測時；**本 Constitution v1.0 治理 PR 於量測後才開**，進行中） |
| active work | Constitution v1.0 治理批：`PROJECT_RULES.md`、`docs/DECISIONS.md`、`docs/BACKLOG.md`（append-only）、本檔；只做治理文件 |
| ⚠️ 過期值 | `70416a6a` 是 #852／Z65（2026-10-15）的舊 commit，**不是目前 main** |

## 2. 最近完成（皆已合併、main CI success）

| PR | merge sha | 內容 |
|---|---|---|
| #863 | `f0a6c474` | BACKLOG：AUD-C21／PQ-C6-3 結案登記（docs-only） |
| #862 | `fa26914b` | 新 UI 獨立 Risk Cap 快照檔＋卡面揭露資料完整性（DR-2026-10-16-4／5；DEC-051、DEC-052） |
| #861 | `3dfad58d` | BACKLOG：AUD-C6／C7 結案登記（docs-only） |
| #860 | `ef7cf41c` | 停用 M1B−M2 腿＋Required Core 閘門（DR-2026-10-16-1／2；DEC-048、DEC-049） |
| #859 | `8b8f9e1e` | `revenue_yoy` 改單季對去年同季單季（DR-2026-10-16-3；DEC-050） |

各 PR 的 main CI run 編號見 `docs/BACKLOG.md`「3. 已結案」。

## 3. Blocker／Decision Required（只列指標，細節見 BACKLOG）

- **PQ-C4-2**：prescreen「三率三升」累計 vs 單季（`docs/BACKLOG.md` §1.1、`AUD-C4-3UP`）—— 待客戶裁示。
- **PQ-C3-1**：舊／新 UI 加碼措辭與計數說明（`docs/BACKLOG.md` §1.1、`AUD-C3-FU`）—— 待客戶裁示。
- **CV1-DR-01**（高）：合規母法「全站不產生任何直接買賣建議」vs Action Layer 長期目標的未調和張力（`docs/BACKLOG.md` 第 4 節）—— 待客戶裁示。
- 其餘 Constitution 遷移時未升格的項目：`docs/BACKLOG.md` 第 4 節（`CV1-DR-*`、`CV1-RC-*`）。
- **舊待辦與「等你答」**：handoff 分支 `HANDOFF.md@1510f3f0` §3（1）、§4（91）、§5（42）、§6 等你答（25 題）及不佔列註，尚未遷入、仍以該檔為權威 —— 見 `docs/BACKLOG.md` `BL-MIGRATE-1` 補註。
- 供客戶知悉：`AUD-C28`（「必要與選用訊號皆已評估」與薩姆從未評估並存）。

## 4. 下一安全接手點

1. Constitution v1.0 治理 PR：獨立第二組 evidence audit → PASS 後 PR → CI → merge → main verification（DEC-016）。
2. 完成後 **停手**。⛔ **不得開始 Batch 1 或任何下一功能 Batch**，須等客戶核准（DEC-015、DEC-002）。
3. BACKLOG 各列的 next action **不構成動工授權**；有客戶指派或實際 bug 觸發才動（`CLAUDE.md` §-1）。

## 5. 新對話 takeover

1. `git fetch origin`；`git log -1 --format='%H %P' origin/main` 與本檔第 1 節比對；不一致 → 以 GitHub 為準，先更新本檔。
2. 查 open PR 與 main 最新非 cron commit 的 check-run `conclusion`。
3. 依序讀：`CLAUDE.md` → `PROJECT_RULES.md` → 本檔 → `docs/BACKLOG.md` → `docs/DECISIONS.md`；舊脈絡查 handoff 分支 `HANDOFF.md`（只讀）。
4. 確認 working tree 乾淨；⛔ 不還原舊 UI 壓測 `stash@{0}`（DEC-019）。
5. 不要求客戶重講已落盤資訊（`PROJECT_RULES.md` 第 11 節）。

## 6. 本檔沒查證的部分

- open PR＝0、CI conclusion 為量測當下快照；本 PR 開立後 open PR 至少為 1。
- 「cron commit 只動 `data_cache/**`」只對 `f0a6c474..82e19dbd` 實測（`git diff --name-only`），不宣稱未來 cron 亦然。
- 本檔由單一撰寫組撰寫，待第二組獨立 audit（`CLAUDE.md` §-2 規則 6）。
