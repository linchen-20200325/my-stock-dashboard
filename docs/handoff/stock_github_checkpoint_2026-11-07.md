# my-stock-dashboard｜GitHub 實查與可恢復接手快照（2026-11-07）

> **定位**：使用者明確要求「請幫我存檔至GITHUB 目前進度 代辦事項 未完成項目」。本檔為當次 GitHub 查核的**補充證據與交接快照**，不是第二份 BACKLOG/DECISIONS/HANDOFF/PROJECT_STATE SSOT，也不授權開工。請在 #1047 文件 PR 核銷後將最新有效部分歸入既有正式文件；本檔保留歷史取證，避免併行寫入三個已有 PR 占用的治理檔造成衝突。
>
> **取證基準**：2026-11-07 查 GitHub（PR/CI/branch API；單組稽核，未執行本機程式測試）；當次 main 完整 SHA **`08bf2b68e5cbd63005c75f5900530a9a37598769`**（#1046）。GitHub 最新狀況可被 cron/merge 改寫；下個工作 session **必須重新實查**，不得直接沿用表格中 SHA／PR 結論。已讀 `PROJECT_RULES.md`、`CLAUDE.md`、`PROCESS.md`、`docs/{BACKLOG,HANDOFF,PROJECT_STATE,DECISIONS}.md` 入口，並實查 7 個 open PR 的 head、draft、mergeable、workflow conclusion；尚**未**獨立完成全量 diff/非作者 QA、完整 required check job 判定、全 repo 待辦清點或即時資料 row PIT 的第二組複驗。

## 一、目前真正已完成（以 main 與 PR 證據分開）

| 內容 | 已確認的 GitHub 事實 | 不能推論 |
|---|---|---|
| main | `08bf2b68e5cbd63005c75f5900530a9a37598769`，#1046：舊四頁／抽屜規格適用性註記 | 不代表新五頁程式已完成 |
| DEC-141～145 | #1045 squash 合併至 main `848fd977ea79179c9f2e6f3fcd5395b8901824a7` | 不包含後續客戶 DEC-146 |
| PIT scalar 守衛 | #1049 merged `63d55badad8dea1b4de767afbd20d31314d46be8`，修正 pandas 純量精度問題 | 不代表 #1038 的歷史觀測 PIT 資格通過 |
| cron 資料發布路徑 | #1035（`8d95847f`，資料分支＋PR 發布）、#1036（`44b6f34e`，macro-history）、#1037（`1029078e`，sector-flow）、#1042（`27f42d18`，原子寫入修正）經 GitHub PR API 查證均已 merged | **真實發布端到端結果：NOT VERIFIED（本快照未驗證）**；不能用「PR 已合併」當作 cron 已實際成功發布。發布 PR 仍須正確觸發原生檢查、保留權限／人工合併 Gate，#1038 PIT 獨立阻塞不變 |
| New UI2 現行 runtime | 依前次獨立讀碼與 Claude #1048 2026-11-07 唯讀前置評論：📊市場、🎯標的、💼持股、👤我的 四頁 Preview，可切 FAKE 場景；Real Preview 目前僅兩類有限資料；手機 Drawer／桌機 rail | 「五頁方向已裁示」≠正式五頁路由/View、完整資料/正式 Auth、完整 OneBrain 已接線；現輪未執行瀏覽器重測 |
| 遠端分支清理 | GitHub 此輪掃描為 11 個分支（含 main），上一輪列出的七個無 open PR 舊工作分支已不在遠端 | 不能憑分支名稱保證剩餘分支可安全刪除 |

## 二、Open PR / 正在等待的證據（此表是量測時點，不是永遠的 current）

| PR | 類型、Head 8 碼 | 當輪狀態 | 下一個必要行動／阻塞 |
|---|---|---|---|
| [#1050](https://github.com/linchen-20200325/my-stock-dashboard/pull/1050) | 文件：DEC-146 與正式五頁頂部兩列 Safety Gate；`b4ec40dd` | Open、non-Draft、mergeable；PR workflow **completed/success** | **缺獨立非作者 QA 與每一 required job/review 細項證據**；驗收後依 latest head 合併，方能正式施工 |
| [#1047](https://github.com/linchen-20200325/my-stock-dashboard/pull/1047) | 治理 BACKLOG/HANDOFF/PROJECT_STATE；`1c8e1e68` | Open、non-Draft；當輪 connector mergeable=true，第二組 QA 指出其 GitHub `mergeable_state=behind`（需更新 main）；workflow completed/success | 修正 #1045/#1046 已合併及 #1044/#1049 已修等過期進度，核實 #1050 與本文，再獨立 QA/required CI 後合併 |
| [#1048](https://github.com/linchen-20200325/my-stock-dashboard/pull/1048) | 舊五頁視覺提案；`8fcf2a1f` | **Draft**；workflow success | 2026-11-07 客戶已裁示**流程方案 B＝直接正式頂部五頁，不做臨時五頁 Drawer**；#1048 原視覺 A1 兩列對應 #1050。比對 unique design 成分後決定保留/關閉，不直接合併過期提案 |
| [#1038](https://github.com/linchen-20200325/my-stock-dashboard/pull/1038) | macro-forward-test 資料發布；`9e7014c7` | **Draft**；workflow success | **PIT FAIL 未解除**：2026-11-05 observation_date 的 captured_at/source as_of 時間落後；需確認逐列原始來源與發佈資格，禁止以 CI 綠取代 PIT 證據，**NO MERGE** |
| [#1034](https://github.com/linchen-20200325/my-stock-dashboard/pull/1034) | 舊治理同步 Draft；`fea34845` | Draft、mergeable=false，workflow success | DEC-143～145 已從其內容收斂至 #1045 main；餘下獨有文件逐項核銷，禁止直接 merge/刪 branch |
| [#1030](https://github.com/linchen-20200325/my-stock-dashboard/pull/1030) | 新 UI2 資料頁／OneBrain／PDF 藍圖；`1e5afee1` | Draft、mergeable=false，workflow success | DEC-142 已進 main，仍可能有獨有研究規格；保留研究證據，逐檔核銷再決定關閉 |
| [#1027](https://github.com/linchen-20200325/my-stock-dashboard/pull/1027) | 持股 W-11 剩餘草稿；`d3556ada` | Draft、mergeable=false，workflow success | DEC-141 已進 main；持股 W-11 線框與未完能力仍待資料/視覺 Gate，逐檔核銷 |

**精度說明**：表中 `workflow completed/success` 是 workflow 粒度的回傳值；**不構成**已確認五個 required job 均 success、無未解 review threads、非作者 QA 或 main CI 成功。

## 三、正式方向與未完成工作（不創建重複 Backlog ID）

| 優先 | 工作／現有依據 | Owner | 狀態與結案 Gate |
|---|---|---|---|
| P0 | DEC-146／#1050 方向入 main | ChatGPT 治理／獨立 QA | 使用者已核准五頁頂部兩列方向；PR 還沒合併。不得把「方向核准」當正式施工已完成 |
| P0 | New UI2 五頁殼／🗂資料 Preview／頂部導航 | **Claude Code**，Sonnet＋Medium | **未施工**；#1050 入 main 且 Gate 後才啟動。最小交付三塊：UI2 自有第五頁登錄/VM、頂部 Sheet/Account＋五頁導覽、原測試與 viewport evidence 更新；不得留下中間態五項 Drawer。下一 code PR 需真 Chromium 390×844、1440×900 × Streamlit 1.56/1.59.2；首屏 `p2_nav_margin_160≥160px`、CTA、JS_V4/focus/keyboard/inert/ESC 等價守衛，獨立 QA，head CI，mergeability |
| P0 | #1038 macro forward-test PIT 資料資格 | Claude Code 唯讀根因／GPT 風險 Gate | 不能發佈為合格歷史訊號；查 observation_date/source as_of/captured_at 逐列証據、修法與 fail-closed，未核實前不合併 |
| P1 | #1047 交接治理文件入 main | ChatGPT | 清除 active 欄位過期敘述、保留歷史快照，與 #1050 合併順序協調；不可把此檔當新 SSOT |
| P1 | #1048/#1034/#1030/#1027 Draft 完整核銷 | ChatGPT + 必要時 Claude 唯讀 | 按 unique file/DEC/未完成能力與現行合併證據做對照，再決定 close/branch deletion；未核銷前不刪 |
| P1 | 🗂資料頁真實來源健康度／欄位、分母 | 待獨立契約 Gate | 目前只有 Preview 空殼可規劃；不得偽造 retrieved_at/source health/proxy、最近成功、最近嘗試或 coverage |
| P1 | 既有四頁正式連接：Active Sheet、持續登入、持股 W-11 | Claude Code 待 Auth/Data Gate | Preview signed-in 不是登入證據；資料不完整顯示未備，不可把空槽視為已完成 |
| P1 | 第一版 UI 可用資料清查與 New UI2 Evidence Coverage | GPT 稽核＋Claude 研究/施工 | DEC-143：逐項查 producer→canonical→計算→UI2→Digest；shortage screener 只能稱疑似、fin_trend_score 缺腿 0 中性化、cashflow 單季/累計等待正式核實。未驗來源不推論為真 |
| P2 | OneBrain 六領域／全域覆核、PDF 市場 EPS×PE/籌碼/國際研究 | 研究與決策 Gate | 設計方向已記 DEC-142；正式 Canonical/Evidence/完整 Digest/風險與 Token coverage Gate 前不得啟用 runtime 或宣稱已有正式 AI 決策 |
| 維護 | 遠端剩餘 11 branches | GPT 治理 | `data` 無 main 共同祖先，`v2`、`claude/stock-dashboard-handoff-g9dtm0` 承載歷史；其餘有 open PR，**目前無已驗證可直接刪除**。PR 核銷/合併後再逐條評估 |

## 四、使用者已確認決策（不是新增產品需求）

- **客戶 2026-11-07 最新原話**：「我核准方案 B 作為五頁頂部導覽的視覺方向，不做臨時 B0 五頁抽屜。請將裁示寫入 GitHub，收斂正式線框與安全驗收條件，再安排 Claude Sonnet＋Medium 最小施工；未通過安全 Gate 不得合併。」
- **避免命名混淆**：「方案 B」是 GPT 施工路線 B（直接最終頂部五頁），畫面採 #1048 舊視覺草案 A1 **頂部兩列**；並**不是** #1048 舊「手機全部一列」B。此裁示在 #1050 DEC-146，待 CI/QA/merge。
- 施工不改 `shared/ia_nav4` 舊 UI 合約、不降級首屏 ≥160px/CTA/安全焦點、不把資料缺值當 0/neutral/safe、不從 FAKE 帳號宣稱真登入。

## 五、下一次接手的唯一安全執行順序

1. **GitHub fresh Gate**：重新確認 main SHA、所有 Open/Draft PR/head/diff、五個 required CI jobs、review threads、non-author QA、cron/main、branches，讀 `CLAUDE.md`、`PROCESS.md`、`PROJECT_RULES.md`、正式五檔與當前 visual contract；不以本文當即時事實。
2. **先核 #1050**：驗 DEC-146 客戶原文、A1/B 對映、三檔 docs diff、最新 head required CI 與獨立 QA；條件齊才合併，禁止直接改 protected main。
3. **再核 #1047**：修已過期的 current 欄位/交接資訊，把本快照的有效現況歸入正式 BACKLOG/HANDOFF/PROJECT_STATE（不另建待辦 ID），完成 QA/CI 後合併。
4. **安排 Claude Code**：核證 #1050 在 main 且沒有重複在途程式 PR 才提供 Sonnet＋Medium（Code）的五頁外殼最小施工提示語；此批只動 UI2 第五頁、頂部兩列與必要測試/量測。Claude 未被使用者轉貼前不可聲稱已派工或正在施工。
5. **平行安全稽核**：#1038 PIT fail-closed；#1027/#1030/#1034/#1048 unique diff/決策/來源核銷。不可直接合併或刪 branch。
6. **只有**全套測試、瀏覽器、獨立 QA、CI/mergeability、文件同步完成，才能聲稱 Stage 完成。正規工作繼續靜默，真正需裁示/Claude 新提示語/交接時才通知。

**此快照由本次 GPT 單組整理，沒有第二組全文獨立複驗；取證範圍與未驗項目已明示。**
