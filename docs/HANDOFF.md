# HANDOFF — 現行交接（my-stock-dashboard）

> **用途**：只寫「現在在哪、最近完成、blocker／Decision Required、下一安全接手點」，並指向其他三檔。**不是完成證明**（`PROJECT_RULES.md` 第 1.3 節）；接手時先依第 5 節重查 GitHub。
> 本檔由 Constitution v1.0 治理 PR #864 建立（DEC-016）；~~本版隨 DEC-054（`CV1-DR-01` 裁示）治理 PR 一起合併（分支 `claude/stock-cv1-dr01`）。~~ ~~本版隨 `CV1-FU-01`（S1-6 合規指南對齊 DEC-054）PR 一起合併（分支 `claude/stock-cv1-fu01`；2026-10-16 更新）。~~ ~~**本版由對話收尾同步 PR 更新**（分支 `claude/stock-close-sync`；2026-10-17，客戶 2026-10-17T01:31Z「對話結束完整性檢查」；純文件同步）。最後一個功能／治理合併為 #866；本同步 PR 合併後 main 會前進，cron 亦會推進 tip —— **main tip 以 GitHub 為準**。~~ ~~**本版隨 #868（VN-00 Blueprint 批）合併**（分支 `claude/investment-inbox-product-design-m1lu7v`；2026-10-17，DEC-057；文件批，無產品 code）；合併後 main SHA 以 GitHub 為準，cron 亦會推進 tip。~~ ~~**本版隨 `BP-ERR-01` 第 4 輪文件修正 PR 合併**（同分支名，已重置到 main `f7c60cae` 後重做；2026-10-17，客戶授權，DEC-058；文件批，無產品 code）；合併後 main SHA 以 GitHub 為準，cron 亦會推進 tip。~~ ~~**本版隨 vNext 0.9 第一安全修復批（`SEC-1`）＋治理同步（DEC-060、`BP-ERR-01` 結案）PR 合併**（同分支名，已重置到 main `15bc173e` 後重做；2026-10-17，客戶授權）；合併後 main SHA 以 GitHub 為準，cron 亦會推進 tip。~~ ~~**本版隨 #870 後的收尾同步 PR 合併**（同分支名，基於 main `7b803b4f`；2026-10-18；docs-only：`SEC-1` 結案登記、DEC-059／DEC-060 狀態補證據）；合併後 main SHA 以 GitHub 為準，cron 亦會推進 tip。~~（#871 已合併，`d3425a91`；2026-10-18 更新）~~**本版隨 vNext 0.9 第二批地基修復 PR 合併**（同分支名 `claude/investment-inbox-product-design-m1lu7v`，基於 main `d3425a91`；2026-10-18，客戶指派；產品 code commit `98118b3f`、`a6e500b2` ＋本文件同步）；合併後 main SHA 以 GitHub 為準，cron 亦會推進 tip。~~（#872 已合併，`c41ee3fb`；2026-10-18 更新）~~**本版隨 #872 後的收尾同步 PR 合併**（同分支名，基於 main `c41ee3fb`；2026-10-18；docs-only：`UIA-01`／`UIA-02`／`UIA-07` 結案登記）；合併後 main SHA 以 GitHub 為準，cron 亦會推進 tip。~~（#873 已合併，`6e71ec60`；其後 #874 `5cec364e` 合併 DEC-061）**本版隨 vNext 1.0 Decision Gate 收斂批 PR 合併**（同分支名，基於 main `5cec364e`；2026-10-18，客戶指派；docs-only，研究整理、不施工）；合併後 main SHA 以 GitHub 為準，cron 亦會推進 tip。
> **完整歷史**：分支 `claude/stock-dashboard-handoff-g9dtm0` 的 `HANDOFF.md`（`1510f3f0`，約 5150 行；**未刪除**；其 current-state 行寫 main＝`fa26914b`，已過期、不含 #863）。本檔不搬歷史。

## 1. 現況（量測：2026-10-18，`origin/main`＝`87afe5ae`；main CI 由撰寫組 `gh run list` 實查）

> 本節為現況快照，每版整表替換（不逐格加刪除線；沿用 #867 作法），歷史見第 2 節與 git history。

| 項目 | 現況 |
|---|---|
| 最後一個功能／治理合併（非 cron、不含本版所隨的 PR） | `87afe5ae`（#876；DEC-062 裁示登記）；其前為 `3192ef11`（#875，Decision Gate 收斂）、`5cec364e`（#874） |
| main tip | 量測時 tip＝`87afe5ae`。本版 PR 合併後 tip 會前進（合併後 main SHA 以 GitHub 為準）；cron 亦會持續推進 tip，引用前重查 |
| main CI | `87afe5ae`：run 39121214945（main push）`success`（2026-10-18 撰寫組 `gh run list` 實查） |
| open PR | 本批 PR 開立後至少為 1，合併後現況以 GitHub 為準 |
| active work | **`1.0-B1` 安全地基進行中**（DEC-062 Q2／Q3；分支 `claude/investment-inbox-product-design-m1lu7v`，commits `abb44a90`、`5be0e9dd`；總管轉述）：`SEC-2`（OAuth state 綁瀏覽器的一次性 nonce）＋`SEC-3`（關閉匿名經 SA 讀 Sheet）→ `in-progress`，**PR 待開／未合併**；`SEC-1-FU` 刻意未併入。後續 `B1-FU-1`～`3` 已登記 —— 見 `docs/BACKLOG.md` 5.1.1 |
| ⚠️ 過期值 | `70416a6a` 是 #852／Z65（2026-10-15）的舊 commit，**不是目前 main**；`5cec364e`（#874）亦已不是最後合併 |

## 2. 最近完成（皆已合併、main CI success）

| PR | merge sha | 內容 |
|---|---|---|
| #876 | `87afe5ae` | DEC-062：登記 `VN1-Q1`～`Q5` 裁示＋production SA 檢查（unknown）＋`VN1-STORE` 研究項＋建議小批次（docs-only）；main CI run 39121214945 success（2026-10-18 撰寫組 `gh run list` 實查） |
| #875 | `3192ef11` | vNext 1.0 Decision Gate 收斂（`BP-DR-01`～`21` → `VN1-Q1`～`Q5`；DR-2026-10-18-2；docs-only）；main CI run 39114405647 success（2026-10-18 撰寫組 `gh run list` 實查） |
| #874 | `5cec364e` | DEC-061：每個階段邊界強制內部 Effort Check、High → Medium／Low 主動降級提醒（`PROJECT_RULES.md` 9.2；docs-only）；main CI run 39107408166 success（2026-10-18 總管 GitHub 實查） |
| #873 | `6e71ec60` | #872 收尾同步（`UIA-01`／`02`／`07` 結案登記、HANDOFF 現況至 `c41ee3fb`；docs-only）；main CI 撰寫組未查 |
| #872 | `c41ee3fb` | vNext 0.9 第二批地基修復：`UIA-01`（部分資料不再顯示五桶全綠／運作中，燈色未改）、`UIA-02`（回 0 列不再顯示運作中）、`UIA-07`（更新失敗不再顯示尚未載入）＋治理同步；三列已移入 `docs/BACKLOG.md`「3. 已結案」；main CI run 39098902005 success（Fast＋Slow；2026-10-18 總管 GitHub 實查） |
| #871 | `d3425a91` | #870 收尾同步（`SEC-1` 結案登記、HANDOFF 現況至 `7b803b4f`、DEC-059／DEC-060 狀態補證據；docs-only）；main CI run 39086819330 success（2026-10-18 撰寫組 `gh run list` 實查） |
| #870 | `7b803b4f` | vNext 0.9 第一安全修復批：`SEC-1` 持股 Google Sheet 讀取快取依使用者身分隔離（已結案）＋DEC-060 回報格式治理同步＋`BP-ERR-01` 結案登記；main CI run 39042558728 success（2026-10-18 總管 GitHub 實查） |
| #869 | `15bc173e` | `BP-ERR-01` 第 4 輪文件修正（DEC-058，已結案）＋永久治理：Minimum Sufficient Effort、Effort 雙向提醒、靜默自主巡航（DEC-059）（docs-only）；main CI run 39019586971 success（2026-10-17 Actions API 實測） |
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

各 PR 的 main CI run 編號見 `docs/BACKLOG.md`「3. 已結案」（#869 所含 `BP-ERR-01`、#870 所含 `SEC-1`、#872 所含 `UIA-01`／`UIA-02`／`UIA-07` 已列入「3. 已結案」；其餘 #864～#869 非 Backlog「3. 已結案」項，run 編號寫在上表）。

## 3. Blocker／Decision Required（只列指標，細節見 BACKLOG）

- **PQ-C4-2**：prescreen「三率三升」累計 vs 單季（`docs/BACKLOG.md` §1.1、`AUD-C4-3UP`）—— 待客戶裁示。
- **PQ-C3-1**：舊／新 UI 加碼措辭與計數說明（`docs/BACKLOG.md` §1.1、`AUD-C3-FU`）—— 待客戶裁示。
- ~~**CV1-DR-01**（高）~~：**已裁示**（2026-10-16，DEC-054；`docs/BACKLOG.md` DR-2026-10-16-6）—— 不再是 blocker。後續一致性項（只列指標）：~~`CV1-FU-01`（S1-6 合規指南未同步）~~（2026-10-16 改版結案，DEC-055／DR-2026-10-16-7；#866）、`CV1-FU-02`（再平衡射程，待裁示）、`CV1-FU-03`（待確認題）、`CV1-FU-04`（Thesis 等無正式規格）、`CV1-FU-05`（AI 轉述正式 Action／通用免責，Action Layer 設計批）、`CV1-FU-06`（`persona.py`「請給出明確的動作」，既有產品 code 衝突，本批未改）—— 見 `docs/BACKLOG.md` 第 4.1 節。
- 其餘 Constitution 遷移時未升格的項目：`docs/BACKLOG.md` 第 4 節（`CV1-DR-*`、`CV1-RC-*`）。
- **舊待辦與「等你答」**：handoff 分支 `HANDOFF.md@1510f3f0` §3（1）、§4（91）、§5（42）、§6 等你答（25 題）及不佔列註，尚未遷入、仍以該檔為權威 —— 見 `docs/BACKLOG.md` `BL-MIGRATE-1` 補註。
- 2026-10-17 收尾同步補登：`CV1-RC-07`（客戶 MSG 1 §18 推播三類警報方向、§26 最終產品原則；原只在聊天）—— Research Candidate，不構成動工授權。
- 2026-10-17 產品方向登記（客戶 MSG 14，2026-10-17T01:52Z）：新 UI 方向「投資決策 OS／Investment Inbox」→ `docs/DECISIONS.md` DEC-056；方向項目 `docs/BACKLOG.md` 第 5 節（`VN-00`～`VN-36`）。**只核准方向、不是實作授權**；本登記隨收尾同步 PR #867 一起合併（同分支 `claude/stock-close-sync`）。最後合併仍為 #866（`2647a0fd`）。
- 2026-10-17 `CV1-DR-10` 已裁示（DEC-060：完整證據留 PR、一般完成回報 ≤5 行、裁示題只留裁示所需資訊）—— 不再是 blocker。
- 2026-10-17 VN-00 Blueprint 批（DEC-057）：**待客戶裁示 `BP-DR-01`～`BP-DR-21`**（見 `docs/BACKLOG.md` 第 5.1.2 節；推薦方案見 Blueprint 第 23 節）。
- **（2026-10-18）vNext 1.0 Decision Gate 收斂**：`BP-DR-01`～`21` 等收斂為 **5 題 `VN1-Q1`～`VN1-Q5`，待客戶裁示** —— 見 `docs/vnext/VNEXT_1_0_DECISION_GATES.md`、`docs/BACKLOG.md` 5.1.2、DR-2026-10-18-2。BP-DR 各列狀態不變（延後 2.0 等為建議）。
- ~~⚠️ **`SEC-1`（高，隱私）**：持股讀取快取不分使用者 —— 見 `docs/BACKLOG.md` 第 5.1.1 節；修法單一、不需裁示，但須客戶指派批次（本批禁止施工）。另 `SEC-2`（`BP-DR-18`）、P0 bug `UIA-01`／`UIA-02`／`UIA-07`／`UIA-14` 同節。~~（2026-10-17 更新）⚠️ **`SEC-1`**：客戶已授權 vNext 0.9 第一安全修復批，**本版 PR 修復**，合併且 main CI 綠後結案 —— 見 `docs/BACKLOG.md` 第 5.1.1 節。`SEC-2`（`BP-DR-18`）、P0 bug `UIA-01`／`UIA-02`／`UIA-07`／`UIA-14` 仍 open（另批）。修復批安全稽核殘留：`SEC-3`（SA 模式匿名讀分享 Sheet，待 `BP-DR-06`）、`SEC-1-FU`（撤銷授權後自身快取 TTL 內仍命中、`clear_read_cache` 清全體；已知限制）—— 見同節。（2026-10-18 更新：`SEC-1` **已結案** —— #870、`7b803b4f`、main CI run 39042558728，移入 `docs/BACKLOG.md`「3. 已結案」，不再是 blocker。仍 open 的指標：`SEC-2`（待 `BP-DR-18`）、`SEC-3`（待 `BP-DR-06`）、`SEC-1-FU`（已知限制）、P0 bug `UIA-01`／`UIA-02`／`UIA-07`／`UIA-14`（須客戶指派批次）、`BP-DR-01`～`BP-DR-21` 待裁示。）
- ~~⚠️ **`BP-ERR-01`**：Blueprint §8.9 Desktop 線框各桶分母錯誤、§29.3 自查宣稱不成立；依 DEC-010 回修上限未修，待客戶決定是否允許第 4 輪修正 —— 見 `docs/BACKLOG.md` 第 5.1.1 節（另 `BP-ERR-02` 已知限制）。施工時以 `shared/macro_buckets.py::BUCKET_DANGER_SPECS` 為準。~~（2026-10-17 更新）**`BP-ERR-01`**：客戶 2026-10-17 授權第 4 輪最小必要文件修正（DEC-058／DR-2026-10-17-3），**本批處理**（本版所隨 PR）；~~不再是 blocker。~~ 本 PR 修正，合併後生效（2026-10-17 更正，V4 SF-1）。`BP-ERR-02` 第 2、4 項仍 open —— 見 `docs/BACKLOG.md` 第 5.1.1 節。施工時仍以 `shared/macro_buckets.py::BUCKET_DANGER_SPECS` 為準。（2026-10-17 更新：已結案 —— #869、`15bc173e`、main CI run 39019586971，移入 `docs/BACKLOG.md`「3. 已結案」）
- ~~（2026-10-18 新增）**vNext 0.9 第二批地基修復進行中**：`UIA-01`／`UIA-02`／`UIA-07` → `in-progress`（本批 PR，未合併）；`UIA-14` 仍 open（不在本批）。本批後續：`UIA-FU-1`（失敗被說成未載入，另批）、`UIA-FU-2`（待 `BP-DR-16`，新增徽章屬視覺規格）、`UIA-FU-3`（取數監控殘留；「哪些來源回空＝失敗」屬資料語意，待裁示）、`UIA-FU-4`（待 `BP-DR-19`）—— 見 `docs/BACKLOG.md` 第 5.1.1 節。`UIA-01` (b) 燈色語意仍待 `BP-DR-19`，本批未改燈色。~~（2026-10-18 更新：#872 已合併，`UIA-01`／`02`／`07` 已結案；有意識的變更，不是漏刪）**仍 open／待裁示的指標**：`SEC-2`（待 `BP-DR-18`）、`SEC-3`（待 `BP-DR-06`）、`SEC-1-FU`（已知限制）、`UIA-14` 及其他 UIA 項（`UIA-P1P2`）、`UIA-FU-1`（另批）、`UIA-FU-2`（待 `BP-DR-16`）、`UIA-FU-3`（資料語意部分待裁示）、`UIA-FU-4`（待 `BP-DR-19`）、`BP-DR-01`～`BP-DR-21` —— 見 `docs/BACKLOG.md` 第 5.1.1～5.1.3 節。
- （2026-10-18）**`1.0-B1` 進行中**（`SEC-2`／`SEC-3` → `in-progress`，本批 PR 未合併）。後續（只列指標，見 `docs/BACKLOG.md` 5.1.1）：`B1-FU-1`（未登入時舊 UI 誤導文案；舊 UI 凍結 DEC-019）、`B1-FU-2`（`SEC-2` Streamlit Cloud 實測：需客戶登入一次、查 log reason codes；屬 `1.0-B2`）、`B1-FU-3`（cookie 綁定殘留風險；建議客戶自 Streamlit secrets 移除 `[gcp_service_account]`）；`SEC-1-FU` 仍 open。
- 供客戶知悉：`AUD-C28`（「必要與選用訊號皆已評估」與薩姆從未評估並存）。

## 4. 下一安全接手點

1. ~~DEC-054 治理 PR：evidence audit → PR → CI → merge → main verification（客戶 2026-10-16T16:26Z 指示）。~~（#865 已合併）~~`CV1-FU-01` 批（DEC-055）：evidence audit → PR → CI → merge → main verification（客戶 2026-10-16T22:15Z 指示）。~~（#866 已合併，2026-10-17 更新）~~**目前無進行中工作**；新對話先依第 5 節重查 GitHub，再**等待客戶指示下一批**。~~（2026-10-17 更新）~~**VN-00 Blueprint 批**：#868 → CI → merge → main verification；合併後**停在安全點**（本版隨 #868 合併；讀到本檔時若 #868 已合併，即處於此安全點）。⛔ 客戶原文「不要開始 vNext 1.0 implementation。」「完成後停止，不開始施工。」（DEC-057）~~（#868 已合併，2026-10-17 更新）**`BP-ERR-01` 第 4 輪文件修正批**（DEC-058）：PR → CI → merge → main verification → 收尾同步補登 BACKLOG（PR 號／merge sha／main CI，`BP-ERR-01` 移入「3. 已結案」）；之後**停在安全點**（讀到本檔時若本版 PR 已合併，即處於此安全點）。⛔ 客戶原文「不開始 vNext 1.0 implementation。」（DEC-058）、「不要開始 vNext 1.0 implementation。」（DEC-057）
2. ~~**停在安全點**（2026-10-17 收尾；客戶原文「不開始下一個 Batch」）。~~ ~~下一批須客戶指派。Blueprint 建議第一批（**只是建議**，DEC-015）：`BP-B0a`（`SEC-1` 安全修復）、`BP-B0b`（`UIA-01` (a)／`UIA-02`／`UIA-14` 假綠燈類 bug）—— 見 Blueprint 第 26 節。⛔ 客戶原文「不要自行開始 CV1-DR-02 或產品功能 Batch。」（2026-10-16T22:15Z 重申：不開始 CV1-DR-02、不開始產品 Action Layer）；⛔ **DEC-054、DEC-056、DEC-057 都不是實作授權**（DEC-015、DEC-002、DEC-009）。~~（2026-10-17 更新）本版 PR（`SEC-1` 安全修復＋治理同步）合併並完成 main verification 後**停在安全點**；客戶原文「完成後依 Silent Autonomous Cruise 規則精簡回報，不開始下一個 Batch。」下一批（例：`BP-B0b` 假綠燈）須客戶指派。（2026-10-18 更新：#870 已合併、main CI run 39042558728 success，**現處於此安全點**。）
~~3. （2026-10-18 新增）**下一安全接手點**：vNext 0.9 其餘項目（`UIA-01`／`UIA-02`／`UIA-07`／`UIA-14` 等 P0 bug、`SEC-2` 待 `BP-DR-18`、`SEC-3` 待 `BP-DR-06`）**須客戶指派**；⛔ 不自行開始（DEC-057「不要開始 vNext 1.0 implementation。」）。~~（2026-10-18 更新：客戶已指派第二批地基修復，`UIA-01`／`02`／`07` 本批施工；有意識的變更，不是漏刪）
3a. ~~（2026-10-18）**本批**：開立本批 PR → CI → merge → main verification → **收尾同步**（`UIA-01`／`02`／`07` 移入 `docs/BACKLOG.md`「3. 已結案」並附 PR 號＋merge sha＋main CI run；本檔現況改至新 main）→ **停在安全點**。其餘 vNext 0.9 項目（`UIA-14`、`UIA-FU-1`～`4`、`SEC-2` 待 `BP-DR-18`、`SEC-3` 待 `BP-DR-06`）**須客戶指派**；⛔ 不開始 vNext 1.0（DEC-057「不要開始 vNext 1.0 implementation。」）。~~（2026-10-18 更新：#872 已合併、main CI run 39098902005 success；有意識的變更，不是漏刪）
3b. ~~（2026-10-18）**現處於安全點**：本版收尾同步 PR 合併後即停。下一批（例：`UIA-14`、`UIA-FU-1`）**須客戶指派**；需裁示者（`UIA-FU-2`／`UIA-FU-4`／`SEC-2`／`SEC-3`、`BP-DR-*`）待客戶裁示；⛔ 不開始 vNext 1.0（DEC-057「不要開始 vNext 1.0 implementation。」）。~~（2026-10-18 更新：客戶已指派 vNext 1.0 Decision Gate 收斂批，現況見 3c；有意識的變更，不是漏刪）
3c. （2026-10-18）**現處於安全點，等待客戶裁示 `VN1-Q1`～`VN1-Q5`**（`docs/vnext/VNEXT_1_0_DECISION_GATES.md`）。裁示後施工仍須客戶指派批次；`VN1-Q1` 未裁示前不得寫任何 1.0 UI code（DEC-003）；⛔ 不開始 vNext 1.0（DEC-057）。
3d. （2026-10-18）裁示已登記（DEC-062）；**下一安全接手點＝`1.0-B1`**（安全地基 SEC-2／SEC-3；先依最新 repo／依賴／風險確認最小安全批次），開工前依 `PROJECT_RULES.md` 9.2 Effort Check，需 High 則先停下提醒客戶切換。建議批次見 `docs/vnext/VNEXT_1_0_DECISION_GATES.md` 第 6 節（建議，不是授權）。3c 由本項接續。（2026-10-18：3d 由 3e 接續 —— `1.0-B1` 已開工）
3e. （2026-10-18）**本批 `1.0-B1`**：開立 PR → CI → merge → main verification → **收尾同步**（`SEC-2`／`SEC-3` 移入 `docs/BACKLOG.md`「3. 已結案」並附 PR 號＋merge sha＋main CI run；本檔現況改至新 main）→ 下一批 **`1.0-B2`**（登入持續性 PoC，含 `B1-FU-2` 實測），開工前依 `PROJECT_RULES.md` 9.2 Effort Check（預期 High → 先提醒客戶切換）。
4. BACKLOG 各列的 next action **不構成動工授權**；有客戶指派或實際 bug 觸發才動（`CLAUDE.md` §-1）。

## 5. 新對話 takeover

1. `git fetch origin`；`git log -1 --format='%H %P' origin/main` 與本檔第 1 節比對；不一致 → 以 GitHub 為準，先更新本檔。
2. 查 open PR 與 main 最新非 cron commit 的 check-run `conclusion`。
3. 依序讀：`CLAUDE.md` → `PROJECT_RULES.md` → 本檔 → `docs/BACKLOG.md` → `docs/DECISIONS.md`；做新 UI／產品方向相關工作時另讀 `docs/vnext/VNEXT_PRODUCT_BLUEPRINT.md`（DEC-056 第 4 點、DEC-057）；舊脈絡查 handoff 分支 `HANDOFF.md`（只讀）。
4. 確認 working tree 乾淨；⛔ 不還原舊 UI 壓測 `stash@{0}`（DEC-019）。
5. 不要求客戶重講已落盤資訊（`PROJECT_RULES.md` 第 11 節）。
6. 推理強度（Minimum Sufficient Effort、雙向提醒）與靜默自主巡航為永久規則：見 `PROJECT_RULES.md` 第 9 節、第 3 節（DEC-059；回報格式 DEC-060）；本檔不複製規則。
7. 每個階段邊界（含「merge＋main verification → 收尾同步」）強制內部 Effort Check、雙向提醒：見 `PROJECT_RULES.md` 9.2（DEC-061）；本檔不複製規則。

## 6. 本檔沒查證的部分

- ~~open PR＝0、CI conclusion 為 2026-10-17 量測當下快照；本收尾同步 PR 開立後 open PR 至少為 1。~~~~（2026-10-17 更新）main CI（run 38995150529）為 VN-00 批撰寫組量測當下快照；#868 開立後、合併前 open PR 至少為 1。~~~~（2026-10-17 更新）main CI（run 39000890158）為 `BP-ERR-01` 文件修正組量測當下快照；本版 PR 開立後、合併前 open PR 至少為 1。~~~~（2026-10-18 更新）main＝`7b803b4f`、main CI run 39042558728 success、open PR＝0 為總管 GitHub 實查之 2026-10-18 快照（收尾撰寫組未重查）；本版 PR 開立後、合併前 open PR 至少為 1。~~~~（2026-10-18 第二批更新）main＝`d3425a91`、main CI run 39086819330 success、open PR＝0 為本版撰寫組 2026-10-18T04:09Z 實查快照（單組）；本批 PR 開立後、合併前 open PR 至少為 1。~~（2026-10-18 收尾更新）main＝`c41ee3fb`、main CI run 39098902005 success 為總管 GitHub 實查（撰寫組未重查）；本版 PR 開立後、合併前 open PR 至少為 1。
- ~~`BP-ERR-01` 第 4 輪修正（各桶分母讀碼、其他寫死分母處的核對）為文件修正組單組結論，未再派複驗，未經第二組驗證。~~（2026-10-17 更新）`BP-ERR-01` 第 4 輪修正經 V4 獨立複驗（2026-10-17，PASS-WITH-FIXES，0 MUST-FIX），驗證組數 2；「其他寫死分母處已核對」仍非窮舉宣稱。
- VN-00 批：`SEC-*`／`UIA-*` 的重現**未在真實部署**（Streamlit Cloud＋真 Google 登入）實測；`UIA-14` 根因未查；Blueprint 的 BP-DR 推薦方案為總管推薦、未經客戶確認。
- ~~「cron commit 只動 `data_cache/**`」只對 `f0a6c474..82e19dbd` 實測（`git diff --name-only`），不宣稱未來 cron 亦然。~~（2026-10-16 更新：該量測屬上一版快照；本版未重測 cron 改動範圍）
- `CV1-FU-*` 的衝突掃描為單組 `git grep`，「其他地方無衝突」未經第二組驗證（`CV1-FU-01` 批的全 repo 掃描同為單組）。
- ~~#865 的 main CI run 38939311066 success 為總管轉述，撰寫組未重查。~~（2026-10-17：收尾同步撰寫組以 REST API 重查，head `f91dfb56`、conclusion `success`）
- 「客戶訊息中未入檔的長效指示只有 `CV1-RC-07` 兩段」為收尾同步撰寫組單組掃描（本 session 客戶訊息逐則與四檔比對；MSG 4、8 為 AI 摘要，不作來源），未經第二組驗證。
- `SEC-1` 修復批（#870 已合併）：重現與 regression tests 以 mock／單元測試進行，**未在真實部署**（Streamlit Cloud＋真 Google 登入、多使用者）實測。
- ~~第二批地基修復（本批，未合併）：修復驗證（實作組＋獨立語意稽核 PASS-WITH-FIXES 0 MUST＋Desktop／Mobile QA）為總管轉述，撰寫組未重查；`UIA-FU-1`～`4` 為單組發現、未經第二組驗；重現與測試以單元測試進行，**未在真實部署**（Streamlit Cloud）實測。~~（2026-10-18 更新：#872 已合併）第二批地基修復（#872）：修復驗證（實作組＋獨立語意稽核 PASS-WITH-FIXES 0 MUST＋Desktop／Mobile QA 兩輪 PASS）、merge sha 與 main CI run 39098902005 皆為總管轉述，撰寫組未重查；`UIA-FU-1`～`4` 為單組發現、未經第二組驗；`UIA-02`／`UIA-07` 等**未在 Streamlit Cloud＋真實資料**實測。
- vNext 1.0 Decision Gate 收斂（本版）：兩組分析分群一致為總管轉述，撰寫組未重查；VN1-Q2 B 案可行性、Streamlit cookie 限制、`AUD-C12` 保存方式、production 是否設定系統帳號、DEC-037／049／051／044 是否適用彙總燈皆**未驗證**；未在 Streamlit Cloud 實測。#874 merge sha 與 main CI run 39107408166 為總管轉述，撰寫組未重查。
- `1.0-B1`（本批，未合併）：修法內容、commits、驗證結果（實作組＋SA1 PASS-WITH-FIXES → 修正 → 複驗 PASS；SA2 PASS-WITH-FIXES 0 MUST；fast lane 28568 passed／0 failed）皆為總管轉述，撰寫組未重查 code 與測試。**未驗證**：Streamlit Cloud cookie 轉送／單一程序／重啟（若不成立，登入會被拒 → `oauth_csrf_enforce` 閥門）；production 是否設定 `[google_oauth]`（未設則 web 持股只顯示登入狀態，符合 Q3＝A）；production SA 是否存在仍 unknown。`B1-FU-1`～`3` 為總管轉述、1 組。
- 本檔由單一撰寫組撰寫，待第二組獨立 audit（`CLAUDE.md` §-2 規則 6）。
