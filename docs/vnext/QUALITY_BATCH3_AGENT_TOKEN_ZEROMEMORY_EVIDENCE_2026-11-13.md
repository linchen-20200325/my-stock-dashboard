# Quality Batch 3 ⑦⑧⑨：Agent 路由、Token／返工基準、零記憶接手 — 實測證據 2026-11-13

> **基準**：`origin/main` ＝ `ae402ce8f1f3f151c96604d54fd6b74b56731575`（#1184 squash，2026-11-13T07:17:46Z）。撰寫日 2026-11-13。
>
> 📌 **聲明（請先讀）**
> - **本文件由單組撰寫（`CLAUDE.md` §-2 規則 6）；不是 QA PASS。** 初稿後已有兩組非作者 QA 回報（QA-A：FAIL 輕度、修後可 PASS；QA-B：PASS with fixes），本版為 **QA 後修訂版**（見下方「QA 後修訂紀錄」）；第二輪（Delta QA，對 head `f326457a`）兩組皆判內容無 High，其所指需修處已於本版處理（見修訂紀錄「第二輪」）；**本版再修訂後尚未再複驗**。文中所有「PASS」僅指「該項測試依其當時判準通過」，不是本文件通過稽核。
> - **證據文件，不是授權**：不解除任何 Gate／HOLD，不構成 `REORG3C-Q5-GATE`／DEC-173 Q5 重議。
> - **所有 SHA、run、數字皆為 2026-11-13 時點快照**；日後引用請重跑附錄 B 的復現指令。
> - **標註規則**：**QA-A 重核**＝QA-A 獨立重核且結果吻合（依總管轉述，撰寫者未見 QA 原文）；**Delta QA**＝第二輪（對 head `f326457a`）兩組非作者 QA，所述內容一律為轉述，撰寫者未重核；**FACT**＝撰寫者本次讀檔／重跑解析器／檔案時間戳直接確認；**MEASURED**＝transcript 解析器或 GitHub API 取得的實際數值；**ESTIMATED**＝有明列假設的估算；**INHERITED**＝轉述總管或各 subagent 回報、撰寫者未重核（只能當待驗事項）；**INFERENCE**＝由事實推論；**NOT VERIFIED**＝未驗證，不得當前提。
> - **撰寫者本次親自核對的範圍**（其餘一律視為 INHERITED）：(1) `.claude/agents/*.md` 內容與 `tools`／`disallowedTools`／`description` 字數；(2) `PROJECT_RULES.md` 第 34 節、`docs/BACKLOG.md`／`docs/DECISIONS.md` 的 DEC-178 相關列；(3) `docs/HANDOFF.md` 檔頭與各段標題層級；(4) 以附錄 A 解析器對本 session 的 subagent transcript 重跑（結果見 §3.2；修訂時再重跑一次，含 first_ctx 與最後一次 call 的 context＋output）；(5) 預先登記檔與盲測 transcript 的時間戳。
> - **範圍**：只寫證據。不改任何 Agent 檔、`PROJECT_RULES.md` 第 34 節、`CLAUDE.md`、測試、workflow、資料。§6 後續候選全是建議，需客戶或總管另行指派。
> - **已被 QA-A 獨立重核者**（QA-A 重核，轉述，撰寫者未見 QA 原文）：§3.2 的 8 列（data-integrity 探針、ui-ux 探針、independent-qa 探針、盲測 V1、盲測 V2、⑨-A、⑨-B、Explore 等待 agent）數字吻合；§3.6 抽核 8 個 PR 的完整欄位、6 個 PR 的耗時吻合；三個 agent 檔的 `tools`／`disallowedTools`／`description` 字數；repo 無 `.claude/settings*`；預先登記時序（`09:22:46Z` 早於 V1 `09:23:08Z`、V2 `09:23:47Z`）；`data_cache/metadata.json` 為 2026-11-09。**其餘未被重核者維持 INHERITED。**
>
> **QA 後修訂紀錄（2026-11-13，兩組非作者 QA 回報後；原有實質揭露未刪，僅更正或補充）**
> 1. **§4.2／§7（QA-A）**：更正 ⑨-B 題號。⑨-B 實為 Q1～Q9（Q7＝CI 全綠能否代表 Production 完成；Q8＝三任務派誰），刪除初稿「B-Q7＝突變測試」的推測與「題目內容未載」「未問」的錯誤敘述；對照表改填 ⑨-B 的實際結果，無對應題者才寫「未問」。
> 2. **§3.3／§3.1（QA-A）**：不再以整段累計 `cache_creation` 當「起跑量」，改用首次 API call 的 `first_ctx`；刪除「與 Agent 類型關係不明顯」「stock-* 未高於 general-purpose」「按需有實質意義」等推論句；`subagent_tokens` 由 NOT VERIFIED 改為 MEASURED 對應（並註明它不是累計花費）。
> 3. **§3.2／§3.1（QA-A）**：PR 指標蒐集列換成終值；Explore 列補 `tool_uses`＝1；§3.1 補 transcript 與主 session 數字隨時間增加。
> 4. **§2.4／§2.5（QA-A）**：V1 不符原因改標作者 INFERENCE；V1 T4 改為「寬鬆 6/8；嚴格 5/8」並說明兩種計分；揭露 V2 的 prompt 是 §34 的濃縮改寫且夾帶第 2a 點；缺口 (d) 改為僅 V2 提及；表頭加圖例；補天花板效應與預先登記檔不在 repo 的揭露。
> 5. **§1（QA-B）**：總表加「來源」欄；已被 QA-A 重核者如實標註。
> 6. **§2.3 E7-6、E7-1（QA-B）**：E7-6 降為「僅文字盲測層面；行為層面無觀察」；E7-1 補「Agent 檔在 session 啟動前是否已存在」未驗。
> 7. **§2.5／§4.5（QA-B）**：補零記憶隔離的限制、E7-1 的 session 時序、以及「既有角色符合要求就不修改」的判斷。
> 8. **§4.2、§6（QA-B）**：「缺值／未接線不判為正常」只對應一半，標 PARTIAL，建議下次補題。
> 9. **§2.4（QA-B）**：T6 補「不需專業 agent ≠ 不需要派工」。
> 10. **§1／§7（QA-B）**：Explore 等待 agent 交叉提及，補 `first_ctx` 55,474。
> 11. **判斷不修或不採納者（直接記於此，不依賴對話）**：
>     (a) **「QA-A 重核 8 列」指的是 §3.2 的這 8 列**：data-integrity 探針、ui-ux 探針、independent-qa 探針、盲測 V1、盲測 V2、⑨-A、⑨-B、Explore 等待 agent（依 QA-A 報告列出的逐列數字，經總管轉述；PR 指標蒐集列另以終值取代，不在這 8 列內）。
>     (b) **V2 的嚴格計分**：初稿修訂時撰寫者未重算；第二輪 Delta QA-1 以預先登記原文自行重算為 8/8，屬單一重算、撰寫者未見其過程，INHERITED（V1 為寬鬆 6/8、嚴格 5/8）。
>     (c) 本文件內未新增任何非來自總管提供或撰寫者重跑解析器的數字。
>
> **第二輪（Delta QA；對 head `f326457a`，兩組皆判內容無 High；以下為其需修處與處理，所述皆為轉述）**
> - **F1（Medium）**：§2.4 表 T4「預先登記期望」欄還原為預先登記原文（原誤加「版面變更要客戶草稿先行」）；V2 於 T4 提到版面線框改寫為「超出預先登記期望的觀察，且 V2 prompt 已含第 2a 點與 Stop Gate 列，不屬純主動辨識」，移除「主動」字樣。
> - **F2（Medium）**：§1 ⑦-7 狀態改為整體 PARTIAL，限制欄改寫為 V1 寬鬆 6/8、嚴格 5/8，V2 寬鬆 8/8（天花板效應、prompt 為濃縮改寫；Delta QA-1 重算嚴格亦 8/8，單一重算，INHERITED）；⑨-B 狀態欄補「9 題中 1 題未問、2 題部分涵蓋」。
> - **F3（Low）**：天花板效應段補入 T4。
> - **F4（Low）**：§3.2 主 session 列內直接標時點下限與其後 32、45 calls；E7-6 的 api calls 敘述改為「三個探針各 2 calls、V1／V2 各 1 call」；§3.3 stock-* 樣本加註撰寫時為 5 個、其後 transcript 增至 ≥7 而未納入。
> - **F5（Low）**：§3.6 刪除組間比較句；可比性第 3 點補 INHERITED 標註。
> - **F6（Low）**：§7 末列改「未問或未見於彙整」；§4.2 第 11 項改為僅列不能做的一半、未列能做。
> - **F7（Low）**：全檔「MEASURED-by-QA-A」改為「QA-A 重核（轉述，撰寫者未見 QA 原文）」，檔頭標註規則同步。
> - **F8（Low）**：刪除第 11 項原 (c)（引用讀者無從查證的 QA-B 說法），其後重編。
> - **F9（Low）**：§3.2 註 2 的首次值明標 INHERITED。
> - **F10（補強）**：§4.5 零記憶隔離補 Delta QA-1 的 tool_use 掃描結果（轉述，仍 NOT VERIFIED）。

## 1. 總表

狀態用詞僅限：**PASS／PARTIAL／NOT VERIFIED／MEASURED／ESTIMATED**。

| # | 子項 | 狀態 | 來源 | 一句限制 |
|---|---|---|---|---|
| ⑦-1 | 載入（frontmatter 與 harness 列出） | **PARTIAL** | INHERITED（總管觀察 harness 清單）；agent 檔內容為撰寫者親核＋QA-A 重核（轉述，撰寫者未見 QA 原文） | harness 的 Agent 工具清單列出三個 Agent，description／tools 與檔一致（單次觀察）；`/agents`、`/doctor` 未測；Agent 檔在 session 啟動前是否已存在未驗（§2.3 E7-1） |
| ⑦-2 | 手動指定 `subagent_type` | **PASS** | INHERITED（總管派工與各探針回報；撰寫者見到對應 transcript 存在） | 三個探針各成功一次（n=3，每個 Agent 各 1 次） |
| ⑦-3a | 工具面權限（各 Agent 自報工具清單 vs frontmatter） | **PASS** | INHERITED（三探針自報）；frontmatter 側為撰寫者親核＋QA-A 重核（轉述，撰寫者未見 QA 原文） | 三個獨立探針回報一致；是「自報清單」，不是 harness 原始設定 |
| ⑦-3b | 工具面權限（呼叫 Write／Edit 被拒） | **NOT VERIFIED** | —— | 工具不在清單內，無從呼叫，因此「被拒」從未發生也未實測 |
| ⑦-4 | Bash 唯讀強制 | **NOT VERIFIED** | 撰寫者親核檔內文；無 `.claude/settings*` 為 QA-A 重核（轉述，撰寫者未見 QA 原文） | 定義檔含 Bash 且僅有內文指示；是否有 settings 層強制未知 |
| ⑦-5 | `/agents` 與 `/doctor` | **NOT VERIFIED** | —— | 模型端無法執行互動式 slash 指令，需客戶端人工 |
| ⑦-6 | 自動路由（harness 依 description 自動委派） | **NOT VERIFIED** | —— | 本批所有派工皆由總管明確指定 `subagent_type`，自動委派從未被觸發或觀察 |
| ⑦-7 | 文字可辨識度盲測 | **PARTIAL** | INHERITED（V1／V2 逐題結果）；預先登記時序為 QA-A 重核（轉述）＋撰寫者核對 | V1 寬鬆 6/8、嚴格 5/8；V2 寬鬆 8/8（有天花板效應、prompt 為濃縮改寫；V2 嚴格計分 Delta QA-1 以預先登記原文自行重算亦為 8/8，仍屬單一重算、撰寫者未見其過程，標 INHERITED）；n=2、題目與期望由同一方預先登記；測的是「文字可辨識」，不是 harness 行為（§2.4） |
| ⑧-1 | 本 session 的 Token 用量 | **MEASURED** | 撰寫者重跑＋QA-A 重核（轉述，撰寫者未見 QA 原文）（§3.2 的 8 列吻合，列名見檔頭修訂紀錄第 11 項 (a)）；主 session 為總管解析值（下限） | 僅限 transcript 仍在的環境；cache_read 重複計入前綴，不可與 output 直接相加；不換算金額 |
| ⑧-2 | description 常駐 Token 成本 | **ESTIMATED** | 字數為撰寫者親核＋QA-A 重核（轉述，撰寫者未見 QA 原文）；Token 數為估算 | 以字數與每字 Token 假設粗估；未做有／無 agent 定義的實測差值 |
| ⑧-3 | Token 基準（有／無專業 Agent 的可比較任務） | **NOT VERIFIED** | —— | 無歷史 transcript、無對照組；**目前無法建立基準** |
| ⑧-4 | 文件讀取成本 | **MEASURED（bytes 僅作規模）／Token NOT VERIFIED** | INHERITED（總管量測 bytes） | bytes 不是 Token；Read 工具只讀必要行段 |
| ⑧-5 | PR 返工次數（commits、review threads） | **MEASURED（GitHub API）** | 總管彙整；QA-A 抽核 8 個 PR 欄位、6 個 PR 耗時吻合，其餘 INHERITED | review threads 全為 0（QA 在 PR 外進行）；commits 含共用分支的舊 commit |
| ⑧-6 | QA 修正輪次 | **PARTIAL（彙整者判定）** | INHERITED（語意判定） | 「QA 後修正 commit」是語意判定，非 API 欄位；#1170 判定困難 |
| ⑧-7 | 返工基準（導入 Agent 前後比較） | **NOT VERIFIED** | —— | 兩組不可比；**不得宣稱導入 Agent 後返工變少** |
| ⑧-8 | QA 往返次數、重複調查次數、新對話接手成本歷史基準 | **NOT VERIFIED** | —— | 無紀錄機制或歷史 transcript |
| ⑨-A | 零記憶接手（有接手提示語；12 題） | **PASS（附限制）** | INHERITED（總管對照已知答案判定）；`metadata.json` 為 2026-11-09 為 QA-A 重核（轉述，撰寫者未見 QA 原文） | 同 session 子 agent、題目有引導性、判定者為出題者、n=1 |
| ⑨-B | 零記憶接手（無提示語；Q1～Q9） | **PASS（附限制）（9 題中 1 題未問、2 題部分涵蓋）** | INHERITED（同上） | 同上，n=1；9 題中與 ⑨-A 的 12 項對應者見 §4.2，其餘寫「未問」 |
| ⑨-C | 換模型／換人／真正冷啟動 CLI／`/agents` 下的接手 | **NOT VERIFIED** | —— | 從未測 |

> 另：本批總管曾多派一個無作用的 Explore 等待 agent（浪費、已改正），見 §3.2 註 1；其 `first_ctx` ＝ 55,474。

## 2. ⑦ Agent 路由整合

### 2.1 測試條件

- **被測物**：`.claude/agents/stock-data-integrity.md`、`stock-ui-ux.md`、`stock-independent-qa.md`（FACT：目錄內僅此三檔，無 `.claude/settings*`）。
- **frontmatter 工具面（FACT，撰寫者讀檔）**：
  - `stock-data-integrity`／`stock-ui-ux`：`tools` ＝ Read、Grep、Glob、Bash；`disallowedTools` ＝ Write、Edit、NotebookEdit、Agent。
  - `stock-independent-qa`：`tools` ＝ Read、Grep、Glob、Bash ＋ 10 個 `mcp__github__*` 讀取類（`pull_request_read`、`list_pull_requests`、`get_commit`、`list_commits`、`get_file_contents`、`actions_get`、`actions_list`、`get_job_logs`、`get_check_run`、`list_branches`）；`disallowedTools` 同上。
- **派工方式**：本 session 總管明確指定 `subagent_type`。探針與盲測皆為唯讀任務。
- **本節的證據來源**：E7-1／E7-2 為總管觀察與各 subagent 回報（INHERITED）；盲測期望檔與時間戳為撰寫者直接核對（FACT）。

### 2.2 四種證據：不得互相替代

| 證據種類 | 本批觀察到的 | 它**證明**什麼 | 它**不能**證明什麼 |
|---|---|---|---|
| **A. frontmatter 載入** | harness 的 Agent 工具清單列出三個 Agent，description 與 tools 描述和檔案一致（E7-1） | 檔案格式可被 harness 解析、名稱可見 | 不證明會被自動選用；不證明 `/agents`、`/doctor` 無警告；不證明在其他環境載入 |
| **B. 手動指定成功** | 三個 `subagent_type` 各派工成功一次（E7-2） | 指名派工可行 | 不證明 harness 會「依任務自動挑」這個 Agent |
| **C. 自動路由** | **無觀察** | —— | 本批從未讓 harness 自行委派；因此 **NOT VERIFIED** |
| **D. 工具權限受限** | 三者自報工具清單與 frontmatter 一致；`list_pull_requests` 對 QA Agent 實呼叫成功回 4 筆 open PR | 工具「不在清單內」這件事 | 不證明「呼叫被拒」；不證明 Bash 唯讀；不證明 settings 層強制 |

> A、B、D 都不能當成 C 的證據；C 也不能由「盲測答對」取代（盲測是 §2.4，測的是人類可讀的文字能否被另一個模型辨識，與 harness 內部委派機制無關）。

### 2.3 證據 E7-1～E7-6

| 編號 | 內容 | 標註 |
|---|---|---|
| E7-1 | 本 session 的 Agent 工具清單列出三個 Agent，description 與 tools 描述和 `.claude/agents/*.md` 一致。**「新 session」的說法有保留**：沒有證據證明三個 Agent 檔在該 session 啟動前就存在（工作樹與 main 同步，但 session 啟動時序未驗），因此維持 PARTIAL | INHERITED（harness 提供，總管觀察；單次）；session 啟動時序 NOT VERIFIED |
| E7-2 | 手動指定派工成功 ×3。各 subagent 以「自己當下 function 清單」回報：data-integrity／ui-ux 為 Read、Grep、Glob、Bash 加 harness 回報工具（無 Write／Edit／NotebookEdit／Agent）；independent-qa 為 Read、Grep、Glob、Bash 加 10 個 github 讀取類（無 `merge_pull_request`、`add_issue_comment` 等寫入類）。三者工具集與 frontmatter 一致，且 `disallowedTools` 項目皆不在清單 | INHERITED（三組獨立探針）；INFERENCE：frontmatter 的 tools／disallowedTools 在 harness 層生效 |
| E7-2 限制 | 三者都沒有實際呼叫 Write／Edit（工具不在清單）；Bash 未測。定義檔含 Bash 且無指令層限制，Bash 本質可寫檔；「只執行唯讀指令」只是內文指示 | FACT（撰寫者讀檔：Tools 節寫明「Bash 唯讀為指示性約束，非機械強制」）；是否有 settings 層強制 NOT VERIFIED |
| E7-3 | `/agents`、`/doctor`：模型端無法執行 | NOT VERIFIED（需客戶端人工；對應 BACKLOG `DEC178-AGENT-LOAD-VERIFY`） |
| E7-4 | 自動路由：無觀察。替代證據為 §2.4 盲測 | NOT VERIFIED |
| E7-5 | 盲測回報的規則缺口（§2.5） | INHERITED（兩實例皆提及）；皆為建議 |
| E7-6 | 「按需、不全數啟動」：**僅文字盲測層面；行為層面無觀察**。盲測 V1／V2 各只用一個 general-purpose 實例；但本批三個探針本來就把三個 Agent 都啟動了（為了探針），**不是**「依任務特徵挑選」的行為證據。真實的「不全數啟動」沒有行為觀察 | NOT VERIFIED（行為層面）；三個探針各 2 calls、V1／V2 各 1 call 為 FACT（transcript） |

### 2.4 文字可辨識度盲測（V1／V2）

**預先登記**：期望答案寫在 scratchpad `prereg_routing_expected.md`，檔案修改時間 `2026-11-13 09:22:46Z`；V1 transcript 首筆時間戳 `09:23:08Z`、V2 為 `09:23:47Z`（撰寫者核對檔案與 transcript 時間戳；QA-A 獨立重核吻合）。期望由總管撰寫。⚠️ **預先登記檔位於 scratchpad、不在 repo**，審查者無法自行重核其內容與時序；時間戳是 QA-A 與撰寫者核對 transcript／檔案所得，檔案時間戳可被改動，僅為輔助證據。

**條件**：V1 ＝ 一個全新 general-purpose 實例，只給三條 description（無 §34）；V2 ＝ 另一全新實例，給 description ＋ **§34 的濃縮改寫（非逐字路由表，且夾帶第 2a 點）**。n=2，各單一實例，**非統計**。

**圖例**：表中 **A＝stock-data-integrity、B＝stock-ui-ux、C＝stock-independent-qa**，是測試題暫用代號，**與 Stop Gate 對客戶提的方案 A／B／C 無關**。

| 題 | 任務（摘要） | 預先登記期望 | V1（僅 description） | V2（description＋§34 濃縮） |
|---|---|---|---|---|
| T1 | 查 TWII 日 K 最後資料日是否落後、as-of 與 fetched_at 是否混用 | data-integrity | A，符合 | 符合 |
| T2 | 檢查手機 390px 首屏、對照 Old UI 功能是否漏承接 | ui-ux | B，符合 | 符合 |
| T3 | 審查 PR diff、確認同 head CI、金融語意是否被改 | independent-qa | C，符合 | 符合 |
| T4 | 新增「外資買賣超」卡：欄位 source／PIT／缺值＋手機首屏呈現 | 拆分：data-integrity（欄位）+ ui-ux（呈現）；實作須客戶授權；之後 QA（非作者） | A＋B，**寬鬆符合／嚴格不符**（拆分正確，未達「實作須客戶授權」「之後 QA」） | 符合；另提到「版面變更要客戶線框先行」——**超出預先登記期望的觀察**；且 V2 的 prompt 已含第 2a 點與 Stop Gate 列（含「UI 版面變更」），**不屬純主動辨識** |
| T5 | QA 自己改了某 PR 測試檔，現要驗收該 PR | 不可由該 QA 實例驗收，需另一非作者實例 | C（另一實例），符合 | 符合 |
| T6 | README 一行 typo | 不需專業 agent | 無，符合 | 符合 |
| T7 | 調整 Risk Cap 公式權重 | 不派 agent；Stop Gate，向客戶提 A／B／C | C（＋A），**不符** | 符合；正確停手 |
| T8 | 接入新的付費資料 API | 不派 agent；Stop Gate，向客戶提案 | A，**不符** | 符合；正確停手 |
| **合計** | | | **寬鬆 6/8；嚴格 5/8** | **寬鬆 8/8；嚴格 8/8**（嚴格為 Delta QA-1 以預先登記原文自行重算，單一重算、撰寫者未見其過程，INHERITED） |

- **兩種計分**：**寬鬆**＝只看「派給誰／要不要派」是否與期望一致（V1 T4 拆分 data＋ui 算符合，得 6/8）；**嚴格**＝預先登記的完整期望含「實作須客戶授權」與「之後 QA」，V1 T4 未達（依總管轉述 QA-A），得 5/8。
- **不符項與原因（INFERENCE，作者推論）**：T7、T8 屬 Stop Gate 類，V1 手上沒有 §34 的對應列，可能因此把任務歸給最接近的 Agent；這是**資訊差**的推論，**不是 V1 自述**——V1 回覆列出的七點不清處並未提到「缺 Stop Gate 列」。
- **天花板效應**：T7／T8 的預先登記期望與 §34 第 4 列（「投資公式／Risk Cap／System Action、新資料源或授權…不派任何 Agent 自行處理」）**幾乎同文**，V2 手上有該列，8/8 有天花板效應，不能當作「description＋§34 辨識力強」的強證據。**T4 亦然**：V2 prompt 的 Stop Gate 列含「UI 版面變更」，且帶 A→B→實作→C 順序（此處 A／B／C 為測試題暫用代號），直接提示了 T4 的答案。
- **撰寫者未見的部分**：V1／V2 各題的原始逐字答案未收入彙整；上表「符合」欄為彙整者對照期望的判定（NOT VERIFIED：撰寫者未重讀原答案）。
- **含義（INFERENCE，保守）**：此 8 題上 V2 全數符合、V1 少兩題；差異與「有無 §34 文字」同時出現，但 V2 的 prompt 另有濃縮改寫與天花板效應，因此不宜讀成「只要有 §34 就能擋住 Stop Gate 類」。
- **T6 補充**：「不需專業 agent」**不等於**「不需要派工」。`CLAUDE.md` §-2 規則 1 仍要求有人（一般實作 AI）執行寫入；`PROJECT_RULES.md` 第 34 節第 3 點已說明「按需」只是「怎麼派」，不是「要不要派」。
- **限制**：期望與題目由同一方（總管）撰寫；題目的陷阱設計可能讓答對更容易或更難；n=2；不同模型版本結果可能不同；**測的不是 harness 自動委派**（見 §2.2）。

### 2.5 規則缺口（建議，不是授權；本批不改 Agent 檔或 §34）

來源：盲測回報（INHERITED）；(a)(e) 撰寫者對照 §34 原文確認，其餘為轉述。**(d) 僅 V2 提及。**

| 編號 | 缺口 | 撰寫者確認 |
|---|---|---|
| (a) | 三個 Agent 皆無寫入工具，§34 沒有「一般實作 AI」列；T6／T7／T8 核准後誰實作未寫。§34 第 2a 點只對 UI 提到「授權後由總管另派一般實作 AI」 | FACT：§34 路由表無實作列，僅 2a 提及 UI |
| (b) | 「非作者」是角色層還是實例層未寫清（T5：只有一個 C 角色時，另一組從哪來） | INHERITED；§34 第 4 點寫「QA 不得驗收自己修改的檔案」，未界定實例 |
| (c) | A（data-integrity）與 C（independent-qa）在「資料完整性」有重疊，判準需靠「有無 PR／diff」 | INHERITED |
| (d) | 測試題暫用的 A／B／C 代號，與 Stop Gate 對客戶的方案 A／B／C 同名，易混（**僅 V2 提及**） | INHERITED；agent 檔本身並無 A／B／C 代號，撰寫者未在 §34 找到 A／B／C agent 代號，混淆風險是否存在於正式文件 NOT VERIFIED |
| (e) | Bash 唯讀只是指示性約束 | FACT（§34 第 7 點 (a) 與各 Agent 檔 Tools 節；既有 BACKLOG `DEC178-AGENT-BASH-READONLY-ENFORCEMENT`） |

**「既有角色符合要求就不修改」的判斷（作者判斷，INFERENCE）**：依本批證據，既有三個角色在**工具面**（自報工具清單與 frontmatter 一致）與**文字可辨識度**（§2.4）上**未發現需要修改的缺陷**，因此本批不修改任何 Agent 檔。上表缺口是**建議候選而非缺陷**：(a)(b)(d) 是 §34 規則文字的補充空間，(c) 是判準寫法，(e) 是已登記的既有觀察；沒有任何一項顯示現有 Agent 定義失效。依據僅為本批 n 很小的觀察，不代表其他任務或環境下無缺陷。

## 3. ⑧ Token 與返工基準

### 3.1 量測方法與限制

- **方法**：Claude Code 把每個 session 與每個 subagent 的對話寫成 jsonl（路徑見附錄 B）；assistant 訊息帶 API 回傳的 `usage`。附錄 A 解析器對 `type=assistant` 紀錄以 `message.id` 去重（同一訊息每個 content block 會重複記一次，同 id 以最後一筆為準），加總 `input_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`、`output_tokens`，並輸出 `api_calls`。
- **限制（必須一併引用）**：
  1. **僅限 transcript 仍在的環境。** 歷史 session（#1175～#1184 當時）的 transcript 不在本容器，**歷史 Token 基準不可得**。
  2. **數字隨時間變動。** 主 session 轉錄會落後且持續增加（總管先後解析，api_calls 已見 10→18→32→45），因此主 session 數字是「解析當下的下限」；`subagents/` 下的 transcript 數量也隨時間增加（撰寫初稿時為 10 個，其後增加 QA 派工 agent）。subagent 轉錄在 agent 尚未結束時解析也會偏低（PR 指標蒐集列曾因此與終值不同，見 §3.2 註 2）。
  3. **`cache_read` 在每個 API call 重複計入整個前綴**，不可與 `output` 直接相加當「成本」；本文件**不換算金額**。
  4. 解析器只讀 jsonl 的 `usage` 欄位；`usage` 欄位語意以 API 回傳為準，**本批未對照帳單**（NOT VERIFIED）。
  5. harness 另顯示的 `subagent_tokens`：**MEASURED 對應**——QA-A 以 transcript 驗證，它＝該 subagent「**最後一次 API call** 的 `input`＋`cache_creation`＋`cache_read`＋`output`」（總管對 12 個 subagent 重算，與其結論一致；撰寫者於 2026-11-13 修訂時對有 harness 值的 8 列重算亦吻合）。⚠️ 它是**最後一次 call 的 context 大小加 output**，**不是累計花費**，不可當成本加總；官方是否如此定義未見文件（NOT VERIFIED）。
- **撰寫者的重跑**：撰寫者於 2026-11-13 約 09:31Z 以附錄 A 指令對 `subagents/` 下 10 個 transcript 重跑（唯讀）；9 個對應 §3.2 的 9 個 subagent 列，8 列與總管數字吻合，PR 指標蒐集 1 列當時與總管首次值不同；修訂時再重跑，該列終值與總管所給終值吻合。QA-A 亦獨立重核 8 列吻合（QA-A 重核（轉述，撰寫者未見 QA 原文））。另新增 `first_ctx`（首次 API call 的 `input`＋`cache_creation`＋`cache_read`）欄位，取每個 transcript 第一筆去重後的 assistant `usage`。

### 3.2 MEASURED：本 session 的 subagent

欄位：`api_calls` ／ `input` ／ `cache_creation` ／ `cache_read` ／ `output` ／ `tool_uses` ／ `first_ctx`（首次 API call 的 `input`＋`cache_creation`＋`cache_read`）／ harness `subagent_tokens`（＝最後一次 call 的 context＋output，見 §3.1 限制 5）。

| Subagent | api_calls | input | cache_creation | cache_read | output | tool_uses | first_ctx | harness `subagent_tokens` |
|---|---|---|---|---|---|---|---|---|
| data-integrity 探針 | 2 | 4 | 99,008 | 96,752 | 1,187 | 2 | 96,754 | 100,044 |
| ui-ux 探針 | 2 | 4 | 99,505 | 96,716 | 1,408 | 2 | 96,718 | 100,814 |
| independent-qa 探針 | 2 | 4 | 107,652 | 102,788 | 2,348 | 3 | 102,790 | 109,581 |
| 盲測 V1（general-purpose） | 1 | 2 | 104,461 | 50,363 | 1,252 | 1 | 154,826 | 156,078 |
| 盲測 V2（general-purpose） | 1 | 2 | 104,837 | 50,363 | 2,433 | 1 | 155,202 | 157,635 |
| ⑨-A 零記憶（general-purpose） | 9 | 18 | 174,779 | 1,559,071 | 12,220 | 15 | 156,958 | 233,911 |
| ⑨-B 零記憶（general-purpose） | 16 | 34 | 177,598 | 2,839,534 | 17,807 | 23 | 154,602 | 233,339 |
| PR 指標蒐集（general-purpose；終值） | 8 | 16 | 212,387 | 1,453,055 | 20,264 | 47 | 154,621 | 270,033 |
| 無用的 Explore 等待 agent | 1 | 2 | 55,472 | 0 | 52 | 1（transcript） | 55,474 | 未載 |
| **主 session**（含派工前接手讀取；**時點下限（18 calls）；其後已見 32、45 calls，見註 3**） | 18 | 40 | 229,643 | 4,284,654 | 25,389 | —— | —— | —— |

九個 subagent 列的 `api_calls`／`input`／`cache_creation`／`cache_read`／`output` 與撰寫者重跑吻合（PR 指標蒐集列為終值，由總管提供，撰寫者重跑吻合）。QA-A 另獨立重核 8 列吻合（QA-A 重核，轉述；列名：data-integrity 探針、ui-ux 探針、independent-qa 探針、盲測 V1、盲測 V2、⑨-A、⑨-B、Explore 等待 agent；經總管轉述，撰寫者未見 QA 原文）。`first_ctx` 與 `subagent_tokens` 的對應已由撰寫者對 transcript 重算確認（8 個有 harness 值的列皆吻合）。

- **註 1（Explore 等待 agent）**：總管曾多派一個 Explore agent 只為「等待」，**沒有產出，是浪費**；已改正，往後等待只結束 turn、不派 agent。誠實列入以免低估本批實際啟動次數與成本。
- **註 2（PR 指標蒐集列）**：總管首次解析值為 7 calls／cc 211,837／cr 1,190,855／out 12,983（**INHERITED**：總管早期取得、現已無法重現，不是 MEASURED；推測為該 agent 尚未結束時取得而偏低）；本表為終值，`subagent_tokens` 270,033 與終值的 last call 重算一致。首次值僅作揭露，不再使用。
- **註 3（主 session）**：撰寫者未重跑主 session（它仍在增長，已見 10→18→32→45 calls，任何數字都是時點下限）。
- **註 4（⑨-B 的 tool_uses）**：`tool_uses = 23` 為 harness 通知值；該 agent 自報「約 17 次」，**自報計數低估**（見 §4.3）。⑨-A 自報約 15，與 15 吻合。
- **註 5（`subagent_tokens` 的讀法）**：⑨-A 與 ⑨-B 的 `subagent_tokens` 數值接近（233,911 與 233,339），但兩者的累計 `cache_read` 差很多（約 1.56M 對 2.84M）。這與「`subagent_tokens` 是最後一次 call 的 context＋output，不是累計花費」一致；因此**不可**拿 `subagent_tokens` 比較各 agent 的累計用量。

### 3.3 觀察（描述，不是結論；每格 n=1）

**以 `first_ctx` 看各 subagent 起跑時的 context 大小**（不再用整段累計 `cache_creation` 當「起跑量」，因為累計值含後續每輪新增的 context，隨工作長短而變）。以下數字皆 MEASURED（同解析器邏輯，取每個 subagent transcript 第一筆去重後的 assistant `usage`）：

| 群組 | 樣本與 `first_ctx` |
|---|---|
| stock-* agent（撰寫時 5 個樣本；其後 QA 派工使 stock-* transcript 增至 ≥7，未納入本節） | ui-ux 探針 96,718；data-integrity 探針 96,754；independent-qa 探針 102,790；QA-A 103,476；QA-B 103,631 |
| general-purpose（6 個樣本） | PR 指標蒐集 154,621；⑨-B 154,602；V1 154,826；V2 155,202；⑨-A 156,958；本文件撰寫組 159,877 |
| Explore（1 個樣本） | 等待 agent 55,474 |

- **描述**：在這批樣本中，受限工具集的 stock-* agent 首次 context 約 9.7 萬～10.4 萬，general-purpose 約 15.5 萬～16.0 萬，兩群約差 5 萬 token 級；Explore 更低（約 5.5 萬）。
- **可能原因（INFERENCE，未驗證）**：general-purpose 帶入完整工具清單。未做任何控制實驗檢驗。
- **限制**：樣本取自同一 session 同一時段；每群樣本數小、範圍窄；非受控實驗（任務內容、工具集、指令長度皆不同）；`first_ctx` 的組成（系統提示、工具定義、CLAUDE.md 等）本批未拆解。**本節不構成「Agent 定義比較省／比較貴」的結論，也不構成任何成本或派工策略建議。**
- 零記憶接手兩次（⑨-A、⑨-B）的累計 `cache_read` 與 tool_uses 遠高於探針與盲測；⑨-B（無提示語）的累計 `cache_read` 約為 ⑨-A 的 1.8 倍、tool_uses 23 對 15。兩者題目不同（12 題對 9 題），**不可據此比較「有提示語是否比較省」**。

### 3.4 ESTIMATED：三個 description 常駐成本

- **FACT（撰寫者重算）**：三個 `description` 欄位字元數 136＋117＋123＝**376 字**（UTF-8 **766 bytes**）。
- **假設（明列）**：中文約 1～2 tokens／字；英文詞約 1～1.5 tokens／詞；中英混排；未考慮 tokenizer 差異與 harness 包裝格式。
- **ESTIMATED**：約 **400～800 tokens**，相對於各 subagent 的 `first_ctx`（約 9.7 萬～16.0 萬，§3.3）低於 1%。**這是估算，不是量測。**
- **真實值的量法**：開兩個除了 `.claude/agents/` 有無以外完全相同的 session，比較首次 API call 的 `first_ctx` 差值。**NOT VERIFIED，未做**（§3.7）。

### 3.5 文件讀取成本（bytes 僅作規模，**不是 Token**）

| 檔案 | bytes（INHERITED，總管量測） |
|---|---|
| `CLAUDE.md` | 192,926 |
| `PROCESS.md` | 22,570 |
| `PROJECT_RULES.md` | 164,417 |
| `docs/HANDOFF.md` | 250,366 |
| `docs/BACKLOG.md` | 1,112,920 |
| `docs/DECISIONS.md` | 1,069,455 |
| `docs/PROJECT_STATE.md` | 359,529 |

- 這些是**檔案大小**。Read 工具只讀必要行段，實際讀入 context 的量遠小於全檔，且本文件**不把 bytes 換算成 Token**。
- ⑨-A 實際自報讀取是行段：`PROJECT_RULES.md` 第 4／34 節、`docs/HANDOFF.md` 檔尾兩段、`docs/BACKLOG.md` 小段、`docs/PROJECT_STATE.md` 小段、`data_cache/metadata.json`、agent 檔前 12 行（INHERITED，行號會漂移，不作定位）。
- 「重複讀取次數」「無效探索次數」**NOT VERIFIED**：目前沒有記錄機制。

### 3.6 返工（14 個 PR）

**來源分類**：commits／檔數／行數／review threads ＝ **MEASURED**（GitHub API，總管彙整；撰寫者未重核）；QA 組數描述 ＝ **轉述**（PR 描述）；「QA 後修正 commit」＝ **彙整者語意判定**（字面關鍵字有大量誤報，無 API 欄位；撰寫者未重核）；耗時 ＝ 彙整未註明起訖（INFERENCE：建立到合併），含等 CI／等客戶，**不是工時**。

| PR | 類型 | 檔數／行數 | commits（API） | QA 後修正 commit | 耗時 |
|---|---|---|---|---|---|
| #1170 | docs | 1／+77 | 7 | 約 4（註 a） | 1h55m |
| #1172 | docs | 1／+387 | 3 | 2（註 b） | 41m |
| #1173 | docs | 1／+548 | 2 | 1 | 46m |
| #1174 | docs | 5／+254／−22 | 4 | 2 | 51m |
| #1175 | docs | 4／+296／−1 | 5 | 2 | 52m |
| #1176 | docs | 4／+222／−1 | 2 | 1 | 33m |
| #1177 | docs | 5／+488／−1 | 3 | 2 | 48m |
| #1178 | feat | 9／+1042／−1 | 3 | 1 | 39m |
| #1179 | docs | 2／+101／−1 | 2 | 1 | 20m |
| #1180 | docs | 3／+33 | 1 | 0 | 18m |
| #1181 | docs | 5／+349 | 4 | 1 | 28m |
| #1182 | docs | 3／+95／−1 | 7（自有 3，註 c） | 1 | 29m |
| #1183 | test＋docs | 6／+729／−1 | 12（自有 5，註 c） | 1 | 34m |
| #1184 | docs | 3／+105／−1 | 15（自有 3，註 c） | 1 | 20m |

- **review threads：14 個 PR 全為 0**（MEASURED）。QA 全在 PR 外以 subagent 進行，GitHub 上沒有 QA 物件，因此**QA 往返次數無法由 GitHub 取得**（NOT VERIFIED）。
- **註 a（#1170）**：PR 描述自述四輪，但其中兩個 commit 只是「#1171 修正有效」的引用，是否算修正輪次難判，故標「約」。
- **註 b（#1172）**：PR 描述寫單組 QA，但 commit 歷史有 QA 修正——描述與 commit 矛盾，已記於 PR 指標報告（INHERITED）。
- **註 c（#1182～#1184）**：三者共用分支，API commits 值含舊 commit；括號為本 PR 自有。#1183／#1184 描述未更新 QA 結果。
- **分組（彙整者定義）**：**組 X**＝#1170、#1172～#1177（7 個，導入前／當下，全 docs-only）；**組 Y**＝#1179～#1184（6 個，Agent 已入庫）；#1178 單列（Agent 入庫本身，feat）。QA 後修正 commit：組 X ≈ 4、2、1、2、2、1、2；組 Y ＝ 1、0、1、1、1、1；#1178 ＝ 1。

**可比性逐點（結論：不可比）**

1. 類型與規模不同：組 Y 含三個 +95～+105 行的小型記憶同步 PR、一個 feat（#1178，不在組內）、一個 test＋docs（#1183，+729）。
2. QA 組數的描述寫法不一致，前幾個 PR 未寫。
3. 組 X 的「獨立 QA」同樣是自訂派工；組 Y 中也只有 #1179／#1180 明寫使用 `stock-independent-qa`，其餘 QA 是否經由 Agent 定義派出，PR 描述未載（INHERITED，來自 PR 指標蒐集 agent 報告，撰寫者未重核）。
4. 耗時含等 CI／等客戶，無工時資料。
5. 樣本 7 對 6，單一寫作者，無對照組，無隨機化。
6. 「QA 後修正 commit」是語意判定，不是客觀欄位。
7. 前後兩組的 QA 嚴格度、客戶要求、任務難度隨時間變化，未控制。

> ⛔ **不得宣稱「導入 Agent 後返工變少」。** 兩組不可比，不作比較。

### 3.7 NOT VERIFIED 清單與最小可重現協定

**NOT VERIFIED**：(1) 有／無專業 Agent 的可比較任務 Token 基準；(2) PR 修正輪次的真值；(3) QA 往返次數；(4) 重複調查次數與無效探索次數；(5) 新對話接手成本的歷史基準；(6) description 常駐成本的實測差值；(7) `usage` 與實際計費的對應（`subagent_tokens` 與 `usage` 的對應已為 MEASURED，見 §3.1）；(8) `first_ctx` 各組成（系統提示、工具定義、專案指引）的占比。

**最小可重現協定（建議；需客戶另行指派才會擴大；不是授權）**

1. 選定一個固定範圍、固定 prompt 的任務（唯讀為宜）。
2. 兩個條件：(A) 派 `stock-*` Agent；(B) 僅派 general-purpose。每個條件**重複 ≥ 3 次**。
3. 每次記錄：附錄 A 解析輸出、tool_uses、耗時、產出是否通過同一份驗收清單。
4. 結論只寫區間與 n，不寫「節省」「改善」。
5. **不得縮小驗收範圍、不得取消獨立 QA、不得為了比較省 Token 而降低任何 Gate**（`CLAUDE.md` §-2、`PROJECT_RULES.md` 第 4 節）。
6. 此協定的結果同樣**不構成 `REORG3C-Q5-GATE` 重議**；Q5 仍須客戶裁示。

## 4. ⑨ 零記憶接手測試

### 4.1 測試條件

| 項目 | ⑨-A | ⑨-B |
|---|---|---|
| 執行者 | 全新 general-purpose subagent，與總管上下文隔離 | 另一全新 general-purpose 實例 |
| 輸入 | 客戶貼上的「接手提示語」原文（`docs/HANDOFF.md` 檔尾的接手提示語節）＋ 12 題 | 僅一句「接手 repo，從正式文件找現況與下一步」＋ Q1～Q9 |
| 題目撰寫 | 總管（已知答案，部分為陷阱題） | 同左 |
| 次數 | n=1 | n=1 |
| 耗時／用量 | 約 112 秒；9 calls／15 tool uses | 約 144 秒；16 calls／23 tool uses |
| 時間戳核對（FACT） | 首筆 09:23:47Z、末筆 09:25:39Z | 首筆 09:26:55Z、末筆 09:29:19Z |

### 4.2 驗收準則 × 結果

對照 BACKLOG 原定 ⑨ 五項：找到最新 main 與有效治理、辨識唯一 NEXT、知道 HOLD 與資料 Gate、正確選用專業 Agent、不重做已完成工作。

**⑨-B 的實際題目（Q1～Q9）**：Q1 main SHA；Q2 閱讀順序與過期文件；Q3 唯一下一步＋前置＋是否需客戶再指派；Q4 HOLD／Stop Gate；Q5 已完成不得重做；Q6 台股資料停在哪天與原因；Q7 CI 全綠能否代表 Production 完成；Q8 (a)(b)(c) 三任務派誰；Q9 用量與冤枉路。（題目內容依總管提供之 prompt 更正，QA-A 指出初稿題號有誤。）

下表左欄為 ⑨-A 的 12 項；⑨-B 欄填它對應題的**實際結果**，**沒有對應題者寫「未問」，不補 PASS**。

| # | 驗收準則（⑨-A 題目主題） | ⑨-A | ⑨-B 對應 |
|---|---|---|---|
| 1 | 找到最新 main SHA | PASS：`ae402ce8f1f3f151c96604d54fd6b74b56731575`，GitHub `list_commits` 與 `git rev-parse origin/main` 交叉，與總管實查一致 | PASS（B-Q1）：同 SHA，兩條獨立來源 |
| 2 | 辨識有效治理文件，並指出提示語過期處 | PASS：列出有效文件；指出提示語過期處（ee1973f3 已推進、#1184 已合併、run 43381887332 已 success、已完成清單要加 #1184） | PASS（B-Q2）：閱讀順序 CLAUDE.md→git log→HANDOFF 目錄＋檔尾→第 34 節→BACKLOG／DECISIONS grep→五軸快照→metadata；辨識檔尾「Quality Batch 2 完成後最新接手點」為現行段（註 1） |
| 3 | 歷史快照 vs 最新事實 | PASS：對照表，與總管實查一致 | PASS（B-Q2 同題涵蓋「過期文件」）：指出 HANDOFF 檔頭快照、第 0 節「現行，2026-10-22」、刪除線段標題等過期處；無獨立對照表 |
| 4 | 唯一 NEXT 與前置 | PASS：唯一 NEXT＝Quality Batch 3；前置 (a)(b) 附 PR／run 證據，(c) 為建議；自行停手（任務僅授權唯讀） | PASS（B-Q3）：同結論；前置逐項附證據；指出 DEC-178 fence 含「不需要再次請示客戶」句，逐字一致性 NOT VERIFIED；自行不執行 Batch 3 |
| 5 | HOLD／Gate | PASS：列 HOLD／Gate，並指出「三處取聯集」規則與位置 | PASS（B-Q4）：HOLD／Stop Gate 清單；**自述為二手彙整、未逐項重讀原條文** |
| 6 | Batch 1／2 已完成 | PASS：附 PR／SHA／run；標「QA 原文未重讀」NOT VERIFIED | PASS（B-Q5）：已完成 #1175～#1184 |
| 7 | 不重做已完成工作（④ 突變測試的陷阱題） | PASS：不重做④；引用 `CLAUDE.md` §-1；若被指派則 scratchpad mutation＋非作者複驗；指到 BACKLOG 既有候選 `DEC178-QB2-MUTATION-SURVIVOR-DENOM` | **未問**：B-Q5 只問「已完成項目」，沒有「被要求重做時是否拒絕」的陷阱題 |
| 8 | 正確選用專業 Agent（三情境） | PASS：(a) data-integrity（說明 §-2 規則 5 免派工的條件後仍選派）(b) independent-qa 兩組以上 (c) 不派 Agent、Stop Gate 向客戶提 A／B／C。**假設性說明，未真的派工** | PASS（B-Q8）：彙整載「同 ⑨-A 結論」；同為假設性，未真的派工；逐題原文撰寫者未見 |
| 9 | 資料新鮮度與 cron | PASS：cron success ≠ 資料新；`data_cache/metadata.json` 的 `twii_ohlcv`／`finmind_inst`／`finmind_margin` `last_updated`＝2026-11-09、`updated_at`＝2026-11-09T19:40:36Z；發布 PR #1124～#1126 未併入；揭露沙箱缺 pyarrow 無法讀 parquet 末列、「落後 3 或 4」為引用未重算。總管獨立核對 metadata：屬實（QA-A 亦重核 metadata 為 2026-11-09） | PASS（B-Q6）：資料停 2026-11-09，原因＝cron success 但發布 PR 未併入（HOLD）；另 fetch 三條 `auto/data-*` 分支的 metadata；揭露無 pyarrow；**提出未釐清疑點，見 §5.3** |
| 10 | CI 綠 ≠ Production | PASS：CI 綠≠Production、Preview≠Production、離線契約測試≠E2E；列五軸與 Streamlit Cloud NOT VERIFIED | PASS（B-Q7）：答「不能」，列五軸與 Streamlit Cloud NOT VERIFIED |
| 11 | Decision Gate 與 #1124～#1126 能做／不能做 | PASS：能做（唯讀）／不能做（merge、close、rebase、comment、rerun、代裁 DPE）清楚 | 部分涵蓋：B-Q4 有 HOLD／Stop Gate 清單；僅列「不能做」的一半（不得合併、關閉、rebase），**未列「能做」**，**不補 PASS** |
| 12 | 自報用量與冤枉路；是否用了先前記憶 | PASS：自報未用先前記憶；自報約 15 次工具呼叫，與 transcript 15 吻合 | 部分：B-Q9 問用量與冤枉路——自報約 17 次、transcript 為 23（**低估**，見 §4.3）；⑨-B 的 prompt **沒有問「是否用了先前記憶」**，故無此自報，**不補 PASS** |

- **註 1（HANDOFF 檔頭，撰寫者親核）**：⑨-B 回報「檔頭仍寫『最新接手優先讀本欄』」。撰寫者讀 `docs/HANDOFF.md` 檔頭：該句**已加刪除線**並附「已過期，最新接手點見檔尾 2026-11-12 段」的註記。所以「完全沒標過期」不成立。但該註記指向的是 2026-11-12 的接手段，而撰寫者核對各段標題：2026-11-12「DEC-177 登錄後」段標題已加刪除線，註明被 2026-11-13 後續段取代；現況段實為檔尾「📌 Quality Batch 2 完成後最新接手點」。所以更精確的描述是：**檔頭的過期標示存在，但它指向的目標本身也已過期，冷啟動者照字面跟著走會落到被取代的段落。**
- **註 2（「缺值／未接線不判為正常」只對應一半，PARTIAL）**：客戶要求的「缺值／未接線不判為正常」中，**缺值／資料停滯**面由第 9 題（⑨-A Q9／⑨-B Q6）充分觸及。**「未接線」面**（例如 UI2 為 FAKE、接線 Gate、`app.py` 對 ui2 引用為 0）：依總管轉述，⑨-A 的 Q10 與 ⑨-B 的 Q7 有觸及五軸軸 4「未接線屬實」，但**沒有獨立題**；撰寫者未重讀原答案。標 **PARTIAL**，缺口＝無獨立的未接線題；建議下次補題（列入 §6 候選）。
- **判定者揭露**：⑨-A／⑨-B 的 PASS 判定是總管對照「自己已知的答案」或實查給出的，**判定者即出題者**，非獨立判定（`CLAUDE.md` §-2 規則 6）。

### 4.3 發現的錯誤與未達

- **無實質錯誤**（INHERITED，總管對照已知答案）。
- **自承未讀**：⑨-A 自承未讀 `PROCESS.md` 與 `PROJECT_RULES.md` 第 7／15／20／32／33 節內文、`docs/DECISIONS.md` 只 grep；⑨-B 未讀 `docs/PROJECT_STATE.md`、`PROCESS.md`、`PROJECT_RULES.md` 第 4／20／33 節全文、BACKLOG DPE 與 G-01～G-17 全文。這些 NOT VERIFIED 是否影響結論未知。
- **自報計數低估**：⑨-B 自報約 17 次工具呼叫，harness 通知 23 次。⑨-A 自報 15 與 15 吻合。因此**不宜把 agent 自報計數當作成本證據**，成本以 transcript 為準。
- **對提示語的回饋**：⑨-A 把提示語第 1 點的快照過期項全部識別，與「歷史快照 vs 重查」的 HANDOFF 設計方向一致（INFERENCE；n=1）。

### 4.4 可操作發現（建議，不是授權；本批不改任何既有文件）

| # | 發現 | 嚴重度（建議） | 標註 |
|---|---|---|---|
| 1 | HANDOFF 檔頭快照已標過期，但其指標（「檔尾 2026-11-12 段」）本身已落後，易誤導冷啟動接手者（註 1） | Low，文件衛生 | FACT（撰寫者親核檔頭與各段標題）；⑨-B 原回報說法較重，已據本核對更正 |
| 2 | 現行接手段是 `###` 層級，以 `grep '^## '` 找不到；⑨-B 因此多繞一次，且 `PROJECT_RULES.md` 第 34 節第一次 grep 樣式未命中 | Low | FACT（撰寫者親核：該標題為 `###` 層級）；繞路次數 INHERITED |
| 3 | 兩次冷啟動都能在無對話記憶下辨識唯一 NEXT、HOLD、資料停滯與 Production 邊界 | —— | INHERITED；n=2 |

### 4.5 限制

1. 兩次都是**同一 session 派出的 subagent**，不是客戶端全新 Claude Code session；共用同一容器與 repo checkout，並載入同一份 `CLAUDE.md` 系統提示（真正新 session 也會載入，但是否相同環境未知）。
2. **零記憶隔離只有一層證據。** 子 agent 與主 session 共享容器與檔案系統，**沒有對可讀路徑做限制**（例如 `~/.claude/projects/` 下的 transcript、scratchpad）。⑨-A 自報未用先前記憶；⑨-B 的 prompt 沒有問此點，故無自報。兩次實際讀取的檔案清單（自報）都不含 transcript 或 scratchpad，另據 Delta QA-1 轉述（撰寫者未重核）：其掃描 ⑨-A、⑨-B、V1、V2 的 tool_use 輸入，未見讀取 scratchpad 或 `~/.claude/projects` 的呼叫（⑨-A 回報內文提到 jsonl，不是讀檔）。但這仍不能證明沒有其他洩漏管道，「子 agent 未讀到先前對話內容」維持 **NOT VERIFIED**。
3. 12 題與 9 題由已知答案者撰寫，**有引導性**，且 ⑨-A 另有接手提示語輔助。
4. **n=2**（A、B 各 1 次）。
5. 第 8 題（⑨-A Q8、⑨-B Q8）為假設性說明，沒有真的派工。
6. 未測 `/agents`、自動路由。
7. 只證明「**同模型、無對話上下文、同一容器 checkout**」可接手；**換模型、換人、真正冷啟動 CLI、`/agents` 皆 NOT VERIFIED**。

## 5. 對 Production 五軸與 Gate 的影響

### 5.1 本批零影響

- 本批僅新增一份文件；**不新增資料欄位、來源、接線、API、cron、Secrets**；不改 Agent 檔、`PROJECT_RULES.md`、測試或 workflow；不觸發 workflow。
- Production 五軸（CI／資料更新／資料有效／正式 UI 接線／決策與通知）判讀以 `docs/vnext/PRODUCTION_HEALTH_FIVE_AXIS_SNAPSHOT_2026-11-13.md` 為準；本批不改其判定。
- **重述兩條原則**：**missing ≠ 0**（缺值不得以 0 或估計填補，見 `CLAUDE.md` §1）；**CI 綠 ≠ Production**（Preview ≠ Production，離線契約測試 ≠ E2E）。

### 5.2 Gate／HOLD 現況（摘錄，非重新裁定）

- 基準 main `ae402ce8…` 的 push CI：run `43381887332`（head `ee1973f3`）與 `43384735241`（head `ae402ce8`）皆 `completed／success`（INHERITED：總管以 GitHub MCP 實查）。
- 台股 `data_cache` 資料停在 **2026-11-09**（⑨-A 讀 `metadata.json` 且總管獨立核對）；原因＝cron success，但資料發布 PR **#1124～#1126 未併入（HOLD）**。
- Open PR 為 #1164（Draft）、#1124、#1125、#1126，皆 HOLD；本批未動。
- `DPE-1～DPE-7` 決策節點待客戶裁示（BACKLOG `DEC176-DATA-PR-EVIDENCE-DECISIONS`）；**DPE-3、DPE-6 仍待客戶裁示**（依總管指示列出，撰寫者未逐項重核各 DPE 內容）；**DPE-7 維持 A**（11-19 為保留檢查點）。
- `REORG3C-Q5-GATE`／DEC-173 Q5 維持 blocked-on-customer；本批 ⑧ 只是前置證據，**不構成重議**。

### 5.3 未釐清的 NOT VERIFIED（只記錄，不處置）

⑨-B 提到：**#1124 分支的 `twii_ohlcv` 為 2026-11-11，與調查文件寫「缺 11-11」不一致**。

- 撰寫者對照 BACKLOG：同一份 BACKLOG 的 NOT VERIFIED 備註寫「台股缺 11-11 的原因（#1124 分支外資／融資有 11-11、台股沒有）」，來源為 `DAILY_DATA_PR_PIT_CRON_INVESTIGATION_2026-11-12.md`。
- ⑨-B 的觀察是 #1124 分支 `twii_ohlcv`＝11-11、`finmind_inst`／`finmind_margin`＝11-12（#1125／#1126 分支仍 11-09）。兩者讀取時點不同（`auto/data-*` 分支由 cron 推進），**但兩者是否只是時點差異，未釐清（NOT VERIFIED）**。
- 本批不處理、不重核、不改任何文件、不對 #1124～#1126 做任何動作。

## 6. 後續候選（全部為建議；需客戶或總管另行指派；本批不做）

| # | 候選 | 對應缺口／來源 | 備註 |
|---|---|---|---|
| 1 | `PROJECT_RULES.md` §34 增列「一般實作 AI」列：核准後誰實作 | §2.5 (a) | 不得讓實作者自己驗收 |
| 2 | §34 第 4 點補「非作者」是角色層還是實例層（至少一個與作者不同的實例） | §2.5 (b) | |
| 3 | 釐清 A／B／C：agent 代號（若有）與 Stop Gate 的方案編號避免同名 | §2.5 (d) | 先確認正式文件是否真有混用（撰寫者未找到 A／B／C agent 代號） |
| 4 | HANDOFF 檔頭過期指標更新，並在 HANDOFF 檔頭或 `PROJECT_RULES.md` 加一行固定錨點：「現行接手段＝檔尾最後一個標題含『最新接手點』者」 | §4.4 (1)(2) | 治理文件改動須走 PR 與獨立 QA（`PROCESS.md` §4） |
| 5 | 有／無 agent 定義的 A／B Token 比較協定 | §3.7 | 需客戶才擴大；結論只寫區間與 n |
| 6 | Bash 唯讀的 settings 層強制 | §2.5 (e)；既有 BACKLOG `DEC178-AGENT-BASH-READONLY-ENFORCEMENT` | **需客戶另行裁示**；先提 A／B／C 方案；本批不改 `.claude/settings*` |
| 7 | 客戶端人工執行 `/agents`、`/doctor`，結果寫回 BACKLOG／HANDOFF | E7-3；`DEC178-AGENT-LOAD-VERIFY` | 載入失敗則停手回報，不自行改權限 |
| 8 | 下次零記憶測試補兩類題：(i)「未接線不判為正常」的獨立題（UI2 FAKE／接線 Gate）；(ii)「被要求重做已完成工作」的陷阱題與「是否用了先前記憶」的統一自報題，使 ⑨-A／⑨-B 可逐項對照 | §4.2 註 2；§4.2 第 7、12 項 | 同時建議限制子 agent 可讀路徑或另行記錄其實際讀取清單（§4.5 第 2 點） |

> 以上皆**不暗示任何 Gate 已解除、任何接線或 UI 施工已授權**。

## 7. 本批仍未完成／NOT VERIFIED 彙整

| 項目 | 狀態 | 缺什麼 |
|---|---|---|
| 本文件的非作者獨立 QA | 初稿 QA 已做（QA-A：FAIL 輕度；QA-B：PASS with fixes）；**修訂版的第二輪複驗未做** | 須另派不同實例（`CLAUDE.md` §-2 規則 4／6） |
| `/agents`、`/doctor` 實測 | NOT VERIFIED | 客戶端人工 |
| 自動路由（harness 自動委派） | NOT VERIFIED | 需在不指定 `subagent_type` 的情境下觀察 |
| Write／Edit 呼叫被拒 | NOT VERIFIED | 工具不在清單，無從呼叫 |
| Bash 唯讀的 settings 層強制 | NOT VERIFIED | 客戶裁示＋環境查證 |
| 其他環境載入三個 Agent；MCP 工具名在他處是否存在 | NOT VERIFIED | 官方未明載 |
| 盲測逐題原始答案；V2 嚴格計分 | 撰寫者未見；V2 嚴格計分僅有 Delta QA-1 單一重算（INHERITED） | 彙整僅載對照結果；預先登記檔不在 repo |
| 有／無 Agent 的 Token 基準 | NOT VERIFIED | 無對照組、無歷史 transcript |
| description 常駐成本實測 | NOT VERIFIED | 有／無 `.claude/agents/` 兩 session 的 `cache_creation` 差值 |
| 主 session 的最終用量 | 下限 | 轉錄落後且持續增加（已見 10→18→32→45 calls） |
| Explore 等待 agent | 浪費、已改正；`first_ctx` ＝ 55,474 | 見 §3.2 註 1 |
| 返工基準、QA 往返、重複調查、新對話接手歷史基準 | NOT VERIFIED | 無紀錄機制 |
| `usage` 與計費的對應；官方對 `subagent_tokens` 的定義 | NOT VERIFIED | 本批僅以 transcript 驗證 `subagent_tokens`＝最後一次 call 的 context＋output（MEASURED），非累計花費 |
| 子 agent 未讀到先前對話內容（零記憶隔離） | NOT VERIFIED | 僅有自報讀取清單一層證據（§4.5 第 2 點） |
| Agent 檔在 session 啟動前是否已存在 | NOT VERIFIED | session 啟動時序未驗（§2.3 E7-1） |
| 「未接線不判為正常」的獨立題 | PARTIAL | 無獨立題（§4.2 註 2） |
| 換模型／換人／真正冷啟動 CLI 的接手 | NOT VERIFIED | 從未測 |
| ⑨-B 未問的面向：「被要求重做已完成工作」陷阱題、「是否用了先前記憶」自報、對 #1124～#1126「能做／不能做」明列 | 未問或未見於彙整 | 見 §4.2 第 7、11、12 項 |
| #1124 分支 `twii_ohlcv` 與調查文件「缺 11-11」的差異 | NOT VERIFIED | 本批不處置 |

## 附錄 A：Token 解析器全文（原樣收錄，未改邏輯）

```python
#!/usr/bin/env python3
"""Sum REAL token usage from a Claude Code session transcript (.jsonl).
Dedupes by message id (the same assistant message is logged once per content block).
Usage: python3 -I token_usage_from_transcript.py <transcript.jsonl>
Output: MEASURED totals (input / cache_creation / cache_read / output) and API-call count.
"""
import json, sys
seen = {}
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        r = json.loads(line)
    except json.JSONDecodeError:
        continue
    m = r.get("message") or {}
    u = m.get("usage")
    if not u or r.get("type") != "assistant":
        continue
    key = m.get("id") or r.get("uuid")
    seen[key] = u  # last record per message id wins (output_tokens final)
tot = dict(input=0, cache_creation=0, cache_read=0, output=0)
for u in seen.values():
    tot["input"] += u.get("input_tokens", 0)
    tot["cache_creation"] += u.get("cache_creation_input_tokens", 0)
    tot["cache_read"] += u.get("cache_read_input_tokens", 0)
    tot["output"] += u.get("output_tokens", 0)
print(json.dumps({"api_calls": len(seen), **tot}, ensure_ascii=False))
```

## 附錄 B：復現指令

> 以下為唯讀指令。路徑與 session id 依環境而異；僅限該 session 的 transcript 仍在的環境，離開後即不可復現。

1. **找 transcript 路徑**
   - 主 session：`~/.claude/projects/<專案目錄名>/<session-id>.jsonl`。專案目錄名為工作目錄路徑把 `/` 換成 `-`（本批為 `-home-user-my-stock-dashboard`）。
   - subagent：`~/.claude/projects/<專案目錄名>/<session-id>/subagents/agent-<agent-id>.jsonl`。
   - 列出：`ls ~/.claude/projects/<專案目錄名>/<session-id>/subagents/`
2. **跑解析器**（把附錄 A 存成 `token_usage_from_transcript.py`）
   - 單檔：`python3 -I token_usage_from_transcript.py <transcript.jsonl>`
   - 全部 subagent：`for f in <...>/subagents/agent-*.jsonl; do printf "%s " "$f"; python3 -I token_usage_from_transcript.py "$f"; done`
   - 輸出為單行 JSON：`api_calls`、`input`、`cache_creation`、`cache_read`、`output`。
3. **核對起迄時間**：每行 jsonl 有 `timestamp` 欄位，取首筆與末筆即可得耗時；檔案修改時間可判斷解析時是否已寫完。
4. **注意**：進行中的 session／subagent 重跑會得到不同數字；請在該 agent 完成後再解析，並記錄解析時間。
5. **GitHub 面（⑧-5）**：以 GitHub MCP 的 `pull_request_read`（取 commits 與 review threads）逐一取 #1170、#1172～#1184；「QA 後修正 commit」須讀 commit 訊息與 diff 自行判定，無 API 欄位。
