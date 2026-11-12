# 股票 UI2／資料層：Open Issues × Open PR × SSOT 對帳（2026-11-12；唯讀觀察）

> **定位：單組對帳底稿／Draft PR，非正式 DEC、非完成證明、非新施工授權。** 本文為當時 GitHub 快照；後續必須重新查核 main、PR head／CI、Issue 留言及變更。全稱性結論 **NOT VERIFIED**，須非作者獨立 QA 另行抽查。僅在本文件記錄事實與待核項，不修改既有治理、資料或 UI 檔。

## 0. GitHub-first 範圍與限制

- 當時 main：`6241ad3b6c64ca7f64140cd111a9038dd8c1dea5`（#1167）；Open **Issues 5**：#1138、#1119、#1116、#1110、#1107。核對時 Open **PR 6**（不是使用者較早截圖的 5）：#1169、#1168、#1164、#1124、#1125、#1126。第六筆為調查 Draft #1169。
- 主要對帳依據：`docs/DECISIONS.md`、`docs/BACKLOG.md`、`docs/PROJECT_STATE.md`、`docs/HANDOFF.md`、`PROJECT_RULES.md` 的 main 內容；Issue 與 PR 主文、PR metadata。**未窮盡**所有留言、已關閉 Issue／PR、所有歷史 branch、Secret／Cloud 真機結果；本文不是全歷史「零遺漏」證明。
- 關鍵防誤讀：**GitHub Issue 的「已授權」標題不等於所有內文方案或 G 表皆獲核准**；有效裁示需按 newer DEC 的取代鏈與 Gate 判讀。HOLD 不能靠開發方便而解除。

## 1. 5 個 Open Issues 與正式 SSOT

| Issue | 主題／來源 | 已有正式依據（main 中觀察） | 仍需核查與 UI 影響 | 狀態 |
|---|---|---|---|---|
| [#1138](https://github.com/linchen-20200325/my-stock-dashboard/issues/1138) | UI2 簡化＋OneBrain Evidence Coverage；不重建架構、UI 簡化≠Evidence 減少 | BACKLOG 有「Issue #1138 雙線結果」：tests-only 31／27 測試、production 疑似缺口 a～i；HANDOFF 有其歷史接手點。DECISIONS 全文對 **字面 #1138** 未找到命中，但有 DEC-160～165 OneBrain／市場頁／G 表相關裁示，故**不能據零命中斷定客戶裁示遺失**。 | 依 newer DEC-164（G-1～G-10 裁示）及 DEC-165 等取代鏈核對 #1138 的早期「G 表待決」是否已過期；檢查 tests-only 結果與缺口 a～i 在 BACKLOG 的對應、是否有獨立 QA／CI 實證、未來施工 Gate。不要重問已裁示方向，也不要把 G 表／Schema Candidate 當 production 核准。 | **部分追溯，待獨立差異稽核** |
| [#1119](https://github.com/linchen-20200325/my-stock-dashboard/issues/1119) | Actions 19 workflow 瘦身唯讀盤點 | DECISIONS 及 BACKLOG 已記錄客戶「Action 等儀表板好了，刪死碼時候再一起刪除」及 `WORKFLOW-SLIM-AUDIT-1` HOLD。 | 與後續 DEC-175 Draft #1168 同方向；暫停所有清理，不能把先前候選當刪除授權。 | **有記錄，延後** |
| [#1116](https://github.com/linchen-20200325/my-stock-dashboard/issues/1116) | ETF Managers GH006，改為資料 PR 發布 | DECISIONS 記 #1117 已合併至 main `aa69d99e`、BACKLOG 有 `ETF-MGR-DATA-PR-1` 等。 | 真正首次排程產生可驗證 PR 仍 **NOT VERIFIED**（文件列 2026-11-16 20:00 UTC）；不得把 CI 綠當 production cron 已通過，亦不得重做已合併修復。 | **實作已記、運行證據待驗** |
| [#1110](https://github.com/linchen-20200325/my-stock-dashboard/issues/1110) | Secrets／舊 UI API 可用性與 New UI2 差距 | DECISIONS 有 Issue #1110 研究完成指標，研究見 `docs/vnext/ISSUE1110_DATA_AVAILABILITY_MATRIX_2026-11-10.md`；BACKLOG 記錄相關問題及後續 Gate。 | User 曾設定 Secrets ≠ 金鑰可用 ≠ API 認證可用 ≠ PIT／授權合格 ≠ UI2 已接線。Cloud smoke test 尚需非敏感證據；不得要求貼 Key／token／代理憑證，也不得自動接入。 | **研究已有，Cloud 結果未證** |
| [#1107](https://github.com/linchen-20200325/my-stock-dashboard/issues/1107) | UI2 Cloud 真 K、手機首屏、Real Preview | DECISIONS DEC-157 註 #1107 驗收 PARTIAL；Issue 記 Cloud 部署路徑、390×844／1440×900、20 根日 K 與 fail-closed 驗收 Gate。 | headless／本機瀏覽器 ≠ Cloud／真機；部署 branch／entrypoint、Real 軸截圖與缺值降級尚待可回查證據；未授權切換正式 `app.py`。 | **PARTIAL／NOT VERIFIED** |

### #1138 的判讀提醒

- `docs/DECISIONS.md` 字面未見 #1138，而 BACKLOG／HANDOFF 有明確段落；這是**索引可追溯性待補強**，不是目前已證實漏掉「正式客戶裁示」。
- 尤其 Issue 主文「G-1～G-10 仍待拍板」是當時快照；後續 DEC-164 已給部分正式裁示。其「UI 摘要簡化」是方向，不等於新 layout／聚合定義／排名／接線授權。
- 新 Agent 必須查 newer DEC、來源逐字可靠度及 Gate（`I1144-WIRING-GATE`、G-F2～G-F6 等），不得把這兩者混為一談。

## 2. 6 個 Open PR 的邊界

| PR | 內容 | 與 UI／資料主線關係 | 本輪處置 |
|---|---|---|---|
| [#1169](https://github.com/linchen-20200325/my-stock-dashboard/pull/1169) | Draft，三個**新** docs：#1165 第二組複驗＋勘誤、接線前決策單、#1124～#1126 PIT／cron 調查 | 與本對帳互補：該 PR 處理資料契約的獨立複驗；**避免重複**或在本 PR 聲稱其結論已核准 | 不改其 head／文件；待非作者 QA、同 head CI 與正式 Gate |
| [#1168](https://github.com/linchen-20200325/my-stock-dashboard/pull/1168) | Draft DEC-175：UI＋既有資料層優先、Actions 延後、跨對話落盤 | 與本對帳直接相關；尚未在 main 生效，不能以未合併文當既有 main SSOT | 不重覆增 DEC；先 QA／CI 再照既有 Gate 合併 |
| [#1164](https://github.com/linchen-20200325/my-stock-dashboard/pull/1164) | REORG3C 歷史結案段歸檔 Draft | 有可能影響歷史文獻定位，不應把搬移當成決策解除 | 本輪不改、不合併、不與其 BACKLOG 衝突 |
| [#1124](https://github.com/linchen-20200325/my-stock-dashboard/pull/1124) | auto macro-history | 可見 TWII／機構／融資更新；來源 published_at 未提供，PIT 尚非通過 | **HOLD**，不合併／關閉／rebase |
| [#1125](https://github.com/linchen-20200325/my-stock-dashboard/pull/1125) | auto sector-flow | 影響板塊資料與口徑；與 FinMind 外資不可直接等同 | **HOLD**，不合併／關閉／rebase |
| [#1126](https://github.com/linchen-20200325/my-stock-dashboard/pull/1126) | auto macro-forward-test | published_at／fetched_at 不明；前瞻測試 PIT 更需留意 | **HOLD**，不合併／關閉／rebase |

## 3. 優先對帳／必要人工作業（非新施工清單）

1. **優先 P0 — #1138 需求與證據的雙向追蹤**：比對 Issue 及其留言中真正由客戶拍板的選項 vs DEC-160～165、DEC-174；核對 BACKLOG「tests-only」、「production 缺口 a～i」與實際 PR／tests／CI。對已由 newer DEC 解決者標 SUPERSEDED；尚未通過 Gate 者留 HOLD。若證實「新裁示沒入 DEC」，另開最小 append-only 修正、附逐字來源，不能由本底稿自行升格。
2. **優先 P1 — #1110 × #1107 的資料／驗收交界**：把 Key presence、API 可用、資料語意/PIT、UI2 caller、Cloud/Real 瀏覽器證據分層；任何不具證據者 NOT VERIFIED。與 #1169 的 Gate 決策單互引，不重寫研究。
3. **優先 P1 — #1116／#1119 既有完成／延後狀態**：追蹤 ETF Managers 真實 cron PR（新證據到時再查），Actions 清理延後到正式 UI cutover／Old UI removal Gate 後；不把尚開 Issue 誤讀成待重做已完成工作。

## 4. 使用者可安全依賴的結論與限制

- **FACT（本次從 main 文件／Issue／PR 主文查核）**：5 Issues 與 6 PR 的類型、#1138 BACKLOG 有段而 DECISIONS 無字面編號、#1116 實作已記錄、#1119 清理 HOLD、#1110／#1107 有研究／驗收追蹤，#1168／#1169 尚為 Draft。
- **INFERENCE**：#1138 可能是「Decision 來源交叉索引不足」，但尚未證明有未登記的客戶逐字裁示；對該主題不可只 grep #1138 就下零覆蓋結論。
- **NOT VERIFIED**：Issue 全部留言與已關閉項是否有新裁示、#1169 文件勘誤是否全面成立、完整 production 行為、Cloud Secrets／真機／Real Preview、所有 PR 同 head CI／獨立 QA、資料 PIT 與來源授權。
- **行動界線**：本文件不是 UI layout、OneBrain runtime、資料接線、資料 PR 合併、任何檔案刪除或新採集來源授權。新 UI 五頁與資料契約沿 DEC-174；#1168 DEC-175 完成 Gate 後才正式生效。資料事實與 AI 分析分離、unknown ≠ neutral、unavailable ≠ safe、missing 不補 0。
- **跨對話讀法**：新 Agent 先 Live GitHub-first，再讀較新 DEC 與 HANDOFF，對照本底稿 Issue／PR link；本底稿是稽核證據，不取代 DECISIONS／BACKLOG／PROJECT_STATE／HANDOFF。

## 5. Draft PR 驗收要求

- 非作者獨立 QA 至少重核：5 Issues 原文／留言、6 PR 最新 head/base/status、DEC-164 對 G 表的後續裁示、DEC-175 是否真正 merge、#1110 API Matrix／#1107 Cloud Gate、#1138 相關實作與 tests-only 是否仍成立。
- 最新 head 的原生 CI 依正式 required checks 規則核實；任何不足保持 Draft。不自我宣稱 QA PASS，不 Auto-merge。
- 若逐項核對證實上述對帳已足夠且零新差異，**不應為湊 PR 另改其他正式文件**。若發現新客戶裁示確實漏登，單獨依來源進行最小追加與第二組 QA。
