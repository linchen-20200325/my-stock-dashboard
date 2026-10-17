# HANDOFF — 現行交接（my-stock-dashboard）

> **用途**：只寫「現在在哪、最近完成、blocker／Decision Required、下一安全接手點」，並指向其他三檔。**不是完成證明**（`PROJECT_RULES.md` 第 1.3 節）；接手時先依第 5 節重查 GitHub。
> 本檔由 Constitution v1.0 治理 PR #864 建立（DEC-016）；~~本版隨 DEC-054（`CV1-DR-01` 裁示）治理 PR 一起合併（分支 `claude/stock-cv1-dr01`）。~~ ~~本版隨 `CV1-FU-01`（S1-6 合規指南對齊 DEC-054）PR 一起合併（分支 `claude/stock-cv1-fu01`；2026-10-16 更新）。~~ ~~**本版由對話收尾同步 PR 更新**（分支 `claude/stock-close-sync`；2026-10-17，客戶 2026-10-17T01:31Z「對話結束完整性檢查」；純文件同步）。最後一個功能／治理合併為 #866；本同步 PR 合併後 main 會前進，cron 亦會推進 tip —— **main tip 以 GitHub 為準**。~~ ~~**本版隨 #868（VN-00 Blueprint 批）合併**（分支 `claude/investment-inbox-product-design-m1lu7v`；2026-10-17，DEC-057；文件批，無產品 code）；合併後 main SHA 以 GitHub 為準，cron 亦會推進 tip。~~ **本版隨 `BP-ERR-01` 第 4 輪文件修正 PR 合併**（同分支名，已重置到 main `f7c60cae` 後重做；2026-10-17，客戶授權，DEC-058；文件批，無產品 code）；合併後 main SHA 以 GitHub 為準，cron 亦會推進 tip。
> **完整歷史**：分支 `claude/stock-dashboard-handoff-g9dtm0` 的 `HANDOFF.md`（`1510f3f0`，約 5150 行；**未刪除**；其 current-state 行寫 main＝`fa26914b`，已過期、不含 #863）。本檔不搬歷史。

## 1. 現況（量測：2026-10-17，`origin/main`＝`f7c60cae`；main CI 由 GitHub check-runs API 實測）

> 本節為現況快照，每版整表替換（不逐格加刪除線；沿用 #867 作法），歷史見第 2 節與 git history。

| 項目 | 現況 |
|---|---|
| 最後一個功能／治理合併（非 cron、不含本版所隨的 `BP-ERR-01` PR） | `f7c60cae`（#868 squash merge，`docs(vNext)：投資決策 OS／Investment Inbox 產品藍圖＋新 UI 實機 Audit（VN-00、DEC-057）`）；parent `312c7fee`（#867） |
| main tip | 量測時 tip＝`f7c60cae`。本版 PR 合併後 tip 會前進（合併後 main SHA 以 GitHub 為準）；cron 亦會持續推進 tip，引用前重查 |
| main CI | `f7c60cae`：run 39000890158（Fast checks、Slow tests 皆 `success`；2026-10-17 GitHub check-runs API 實測） |
| open PR | 量測時本版 PR 尚未開立；開立後 open PR 至少為 1，合併後現況以 GitHub 為準 |
| active work | **`BP-ERR-01` 第 4 輪最小必要文件修正**（客戶 2026-10-17 授權，DEC-058）：只改 Blueprint §8.9 各桶數字、§29.3 自查敘述、新增 §29.4，與治理檔同步；合併即完成本批，之後無進行中工作。⛔ 不改產品 code、公式、資料語意，不擴大產品方向，不開始 vNext 1.0 實作 |
| ⚠️ 過期值 | `70416a6a` 是 #852／Z65（2026-10-15）的舊 commit，**不是目前 main**；`312c7fee`（#867）亦已不是最後合併 |

## 2. 最近完成（皆已合併、main CI success）

| PR | merge sha | 內容 |
|---|---|---|
| #868 | `f7c60cae` | VN-00：vNext Product Blueprint＋新 UI 實機 Audit＋治理四檔同步（DEC-057；docs-only）；main CI run 39000890158 success（2026-10-17 check-runs API 實測） |
| #867 | `312c7fee` | 對話收尾同步（HANDOFF 現況至 #866、結案證據、`CV1-RC-07`）＋DEC-056 產品方向登記、BACKLOG 第 5 節 `VN-00`～`VN-36`（docs-only）；main CI run 38995150529 success（2026-10-17 實測） |
| #866 | `2647a0fd` | DEC-055：`CV1-FU-01` 結案，S1-6 合規指南與 `AI_QA_DISCLOSURE` 對齊 DEC-054（治理／規格文件、`wf_page_why.js` 線框、`AI_QA_DISCLOSURE` 字串）；新增 `CV1-FU-05`、`CV1-FU-06`；main CI run 38980399324 success（2026-10-17 實測） |
| #865 | `f91dfb56` | DEC-054：裁示 `CV1-DR-01`，方向性 Action 有條件允許、部分取代 DEC-022（治理文件）；main CI run 38939311066 success（2026-10-17 REST API 實測） |
| #864 | `66fee4e8` | Project AI Constitution v1.0 治理文件（`PROJECT_RULES.md`、`docs/DECISIONS.md`、`docs/BACKLOG.md`、本檔）；main CI run 38921405387 success |
| #863 | `f0a6c474` | BACKLOG：AUD-C21／PQ-C6-3 結案登記（docs-only） |
| #862 | `fa26914b` | 新 UI 獨立 Risk Cap 快照檔＋卡面揭露資料完整性（DR-2026-10-16-4／5；DEC-051、DEC-052） |
| #861 | `3dfad58d` | BACKLOG：AUD-C6／C7 結案登記（docs-only） |
| #860 | `ef7cf41c` | 停用 M1B−M2 腿＋Required Core 閘門（DR-2026-10-16-1／2；DEC-048、DEC-049） |
| #859 | `8b8f9e1e` | `revenue_yoy` 改單季對去年同季單季（DR-2026-10-16-3；DEC-050） |

各 PR 的 main CI run 編號見 `docs/BACKLOG.md`「3. 已結案」（#864～#868 非 Backlog「3. 已結案」項，run 編號寫在上表）。

## 3. Blocker／Decision Required（只列指標，細節見 BACKLOG）

- **PQ-C4-2**：prescreen「三率三升」累計 vs 單季（`docs/BACKLOG.md` §1.1、`AUD-C4-3UP`）—— 待客戶裁示。
- **PQ-C3-1**：舊／新 UI 加碼措辭與計數說明（`docs/BACKLOG.md` §1.1、`AUD-C3-FU`）—— 待客戶裁示。
- ~~**CV1-DR-01**（高）~~：**已裁示**（2026-10-16，DEC-054；`docs/BACKLOG.md` DR-2026-10-16-6）—— 不再是 blocker。後續一致性項（只列指標）：~~`CV1-FU-01`（S1-6 合規指南未同步）~~（2026-10-16 改版結案，DEC-055／DR-2026-10-16-7；#866）、`CV1-FU-02`（再平衡射程，待裁示）、`CV1-FU-03`（待確認題）、`CV1-FU-04`（Thesis 等無正式規格）、`CV1-FU-05`（AI 轉述正式 Action／通用免責，Action Layer 設計批）、`CV1-FU-06`（`persona.py`「請給出明確的動作」，既有產品 code 衝突，本批未改）—— 見 `docs/BACKLOG.md` 第 4.1 節。
- 其餘 Constitution 遷移時未升格的項目：`docs/BACKLOG.md` 第 4 節（`CV1-DR-*`、`CV1-RC-*`）。
- **舊待辦與「等你答」**：handoff 分支 `HANDOFF.md@1510f3f0` §3（1）、§4（91）、§5（42）、§6 等你答（25 題）及不佔列註，尚未遷入、仍以該檔為權威 —— 見 `docs/BACKLOG.md` `BL-MIGRATE-1` 補註。
- 2026-10-17 收尾同步補登：`CV1-RC-07`（客戶 MSG 1 §18 推播三類警報方向、§26 最終產品原則；原只在聊天）—— Research Candidate，不構成動工授權。
- 2026-10-17 產品方向登記（客戶 MSG 14，2026-10-17T01:52Z）：新 UI 方向「投資決策 OS／Investment Inbox」→ `docs/DECISIONS.md` DEC-056；方向項目 `docs/BACKLOG.md` 第 5 節（`VN-00`～`VN-36`）。**只核准方向、不是實作授權**；本登記隨收尾同步 PR #867 一起合併（同分支 `claude/stock-close-sync`）。最後合併仍為 #866（`2647a0fd`）。
- 2026-10-17 VN-00 Blueprint 批（DEC-057）：**待客戶裁示 `BP-DR-01`～`BP-DR-21`**（見 `docs/BACKLOG.md` 第 5.1.2 節；推薦方案見 Blueprint 第 23 節）。
- ⚠️ **`SEC-1`（高，隱私）**：持股讀取快取不分使用者 —— 見 `docs/BACKLOG.md` 第 5.1.1 節；修法單一、不需裁示，但須客戶指派批次（本批禁止施工）。另 `SEC-2`（`BP-DR-18`）、P0 bug `UIA-01`／`UIA-02`／`UIA-07`／`UIA-14` 同節。
- ~~⚠️ **`BP-ERR-01`**：Blueprint §8.9 Desktop 線框各桶分母錯誤、§29.3 自查宣稱不成立；依 DEC-010 回修上限未修，待客戶決定是否允許第 4 輪修正 —— 見 `docs/BACKLOG.md` 第 5.1.1 節（另 `BP-ERR-02` 已知限制）。施工時以 `shared/macro_buckets.py::BUCKET_DANGER_SPECS` 為準。~~（2026-10-17 更新）**`BP-ERR-01`**：客戶 2026-10-17 授權第 4 輪最小必要文件修正（DEC-058／DR-2026-10-17-3），**本批處理**（本版所隨 PR）；不再是 blocker。`BP-ERR-02` 第 2、4 項仍 open —— 見 `docs/BACKLOG.md` 第 5.1.1 節。施工時仍以 `shared/macro_buckets.py::BUCKET_DANGER_SPECS` 為準。
- 供客戶知悉：`AUD-C28`（「必要與選用訊號皆已評估」與薩姆從未評估並存）。

## 4. 下一安全接手點

1. ~~DEC-054 治理 PR：evidence audit → PR → CI → merge → main verification（客戶 2026-10-16T16:26Z 指示）。~~（#865 已合併）~~`CV1-FU-01` 批（DEC-055）：evidence audit → PR → CI → merge → main verification（客戶 2026-10-16T22:15Z 指示）。~~（#866 已合併，2026-10-17 更新）~~**目前無進行中工作**；新對話先依第 5 節重查 GitHub，再**等待客戶指示下一批**。~~（2026-10-17 更新）~~**VN-00 Blueprint 批**：#868 → CI → merge → main verification；合併後**停在安全點**（本版隨 #868 合併；讀到本檔時若 #868 已合併，即處於此安全點）。⛔ 客戶原文「不要開始 vNext 1.0 implementation。」「完成後停止，不開始施工。」（DEC-057）~~（#868 已合併，2026-10-17 更新）**`BP-ERR-01` 第 4 輪文件修正批**（DEC-058）：PR → CI → merge → main verification → 收尾同步補登 BACKLOG（PR 號／merge sha／main CI，`BP-ERR-01` 移入「3. 已結案」）；之後**停在安全點**（讀到本檔時若本版 PR 已合併，即處於此安全點）。⛔ 客戶原文「不開始 vNext 1.0 implementation。」（DEC-058）、「不要開始 vNext 1.0 implementation。」（DEC-057）
2. ~~**停在安全點**（2026-10-17 收尾；客戶原文「不開始下一個 Batch」）。~~ 下一批須客戶指派。Blueprint 建議第一批（**只是建議**，DEC-015）：`BP-B0a`（`SEC-1` 安全修復）、`BP-B0b`（`UIA-01` (a)／`UIA-02`／`UIA-14` 假綠燈類 bug）—— 見 Blueprint 第 26 節。⛔ 客戶原文「不要自行開始 CV1-DR-02 或產品功能 Batch。」（2026-10-16T22:15Z 重申：不開始 CV1-DR-02、不開始產品 Action Layer）；⛔ **DEC-054、DEC-056、DEC-057 都不是實作授權**（DEC-015、DEC-002、DEC-009）。
3. BACKLOG 各列的 next action **不構成動工授權**；有客戶指派或實際 bug 觸發才動（`CLAUDE.md` §-1）。

## 5. 新對話 takeover

1. `git fetch origin`；`git log -1 --format='%H %P' origin/main` 與本檔第 1 節比對；不一致 → 以 GitHub 為準，先更新本檔。
2. 查 open PR 與 main 最新非 cron commit 的 check-run `conclusion`。
3. 依序讀：`CLAUDE.md` → `PROJECT_RULES.md` → 本檔 → `docs/BACKLOG.md` → `docs/DECISIONS.md`；做新 UI／產品方向相關工作時另讀 `docs/vnext/VNEXT_PRODUCT_BLUEPRINT.md`（DEC-056 第 4 點、DEC-057）；舊脈絡查 handoff 分支 `HANDOFF.md`（只讀）。
4. 確認 working tree 乾淨；⛔ 不還原舊 UI 壓測 `stash@{0}`（DEC-019）。
5. 不要求客戶重講已落盤資訊（`PROJECT_RULES.md` 第 11 節）。
6. 推理強度（Minimum Sufficient Effort、雙向提醒）與靜默自主巡航為永久規則：見 `PROJECT_RULES.md` 第 9 節、第 3 節（DEC-059）；本檔不複製規則。

## 6. 本檔沒查證的部分

- ~~open PR＝0、CI conclusion 為 2026-10-17 量測當下快照；本收尾同步 PR 開立後 open PR 至少為 1。~~~~（2026-10-17 更新）main CI（run 38995150529）為 VN-00 批撰寫組量測當下快照；#868 開立後、合併前 open PR 至少為 1。~~（2026-10-17 更新）main CI（run 39000890158）為 `BP-ERR-01` 文件修正組量測當下快照；本版 PR 開立後、合併前 open PR 至少為 1。
- `BP-ERR-01` 第 4 輪修正（各桶分母讀碼、其他寫死分母處的核對）為文件修正組單組結論，未再派複驗，未經第二組驗證。
- VN-00 批：`SEC-*`／`UIA-*` 的重現**未在真實部署**（Streamlit Cloud＋真 Google 登入）實測；`UIA-14` 根因未查；Blueprint 的 BP-DR 推薦方案為總管推薦、未經客戶確認。
- ~~「cron commit 只動 `data_cache/**`」只對 `f0a6c474..82e19dbd` 實測（`git diff --name-only`），不宣稱未來 cron 亦然。~~（2026-10-16 更新：該量測屬上一版快照；本版未重測 cron 改動範圍）
- `CV1-FU-*` 的衝突掃描為單組 `git grep`，「其他地方無衝突」未經第二組驗證（`CV1-FU-01` 批的全 repo 掃描同為單組）。
- ~~#865 的 main CI run 38939311066 success 為總管轉述，撰寫組未重查。~~（2026-10-17：收尾同步撰寫組以 REST API 重查，head `f91dfb56`、conclusion `success`）
- 「客戶訊息中未入檔的長效指示只有 `CV1-RC-07` 兩段」為收尾同步撰寫組單組掃描（本 session 客戶訊息逐則與四檔比對；MSG 4、8 為 AI 摘要，不作來源），未經第二組驗證。
- 本檔由單一撰寫組撰寫，待第二組獨立 audit（`CLAUDE.md` §-2 規則 6）。
