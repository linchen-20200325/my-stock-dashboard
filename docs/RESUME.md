# RESUME｜衍生接續索引（DERIVED INDEX ONLY，無獨立決策效力）

> 唯一 SSOT：https://github.com/linchen-20200325/my-stock-dashboard/issues/1199
> 本檔與 #1199、有效 DEC、Contract、`PROJECT_RULES.md` 衝突時，**一律以後者為準**。本檔不是第二 SSOT，不授權任何施工、Ready、merge、部署。
> 快照：2026-11-25（台北）；main `2fd0773e120d27f2093078dae67404eded333fc5`。**快照，過期即不可信；每輪須 LIVE Gate 重查。**
> 出處記法：`c<數字>`＝#1199 留言 ID（網址 `…/issues/1199#issuecomment-<數字>`）；其餘為 repo 路徑。

## 1. 版本

- 最新核准產品基準 **v1.0**（2026-11-23 共識；DEC-224，APPROVED PRODUCT TARGET，**非施工／merge／部署授權**）。出處：`docs/DECISIONS.md` DEC-224、`docs/vnext/UI2_ONEBRAIN_FULL_PRODUCT_SPEC_V1_0_2026-11-23.md`。
- **V1.1**＝僅調整「新對話如何接續讀取」的索引版本，不改產品範圍、規則或授權。本輪客戶明示接續方式已回存 c7165164441；早期派工卡逐字全文仍 NOT VERIFIED。
- ⚠️ 與規格第十章「MF-AC2 A 整合口徑、B Y 守衛及接入裁示、#1274 Merge Gate、#1281 文件/新 head 驗收及 Merge 授權、#1268/#1278 原 Draft 限制；v1.1（Catalyst Radar／Signal Log／Canonical Evidence Store，全部 HOLD）」**不是同一件事，勿混淆**。

## 2. 讀取順序（本檔只是定位入口；V1.1 輕量接續與正式驗收分開）

**日常輕量接續（V1.1）**：
1. 從 GitHub 即時狀態開始：#1199 最新正式交接摘要（最新客戶正式裁示、各線最新回存）與 main SHA、Open／Draft PR 的 head／base。
2. 按需讀本檔（衍生索引）與必要差額；不因本檔省略第 1 步。

**正式 QA／施工／合併：不得以本檔取代，一律回到 D2 原讀序與完整原 LIVE Gate**：
3. GitHub：main SHA、Draft head／base、必要 diff、既有獨立 QA、五項 CI＋Slow AppTest 實際 step（Run AppTest）、reviews／threads。
4. 高位階治理與正式契約：`CLAUDE.md`、`PROCESS.md`、`PROJECT_RULES.md`、`docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`。
5. 五檔相關有效部分（`PROJECT_RULES.md` 第 15 節）→ 最新 handoff（`docs/HANDOFF.md`，只當索引）→ 必要時歷史。
6. 有效 DEC／Contract 為準：DEC-224、DEC-225（`docs/DECISIONS.md`）；ADR-OB-001（`docs/vnext/ONEBRAIN_ARCHITECTURE_DECISION_2026-10-31.md`）；`docs/vnext/READ_FIRST_UI2_ONEBRAIN_VERSION_AND_DEC_DRAFT_2026-11-23.md`（檔首已更正：舊「DRAFT／未核准」文字勿再用來派工）。

**效力與衝突**：`PROJECT_RULES.md` 第 25 節只定效力順位，不是接續程序，本檔不重述。本節若與 READ FIRST 第四節第 3 點、第 25 節或第 15 節讀序有衝突，**以有效正式規則為準，並提請裁示（#1199）**；本檔不改寫、不覆蓋正式規則，不新增 Gate、不降低原 Gate。
**證據入口**：c7164122838、Work c7164471316（MF-RESUME-1）、本輪客戶明示接續方式回存 c7165164441。早期派工卡逐字全文仍 NOT VERIFIED；正式規則及原 Gate 不變。

## 3. 三行硬約束（每張派工卡固定保留；出處 c7110402272，與規格第十一章比對）

- 【範圍鎖定】只改本卡授權檔案／指定差額；不順手重構、不跨線共編、不解鎖 HOLD、不自行新增 Gate。
- 【誠實降級】缺值、NaN、STALE、不可比較等依有效契約顯示或標 NOT VERIFIED；不得補 0、冒充 fresh／安全／續抱，Real 不以 FAKE 補畫。
- 【退回門檻】遇最新 DEC/Contract 衝突、授權缺失、指定 Must-Fix 未清、有效 QA FAIL／CI FAIL、head/base 改變而證據失效，停在現有 Gate，明列阻塞及最小解除證據；不得硬上 Ready/merge/deploy。

（差異註記：留言原文每行為粗體標題加冒號，條文本體與 repo 規格第十一章逐字一致；若有出入以 repo 文件為準。）

## 4. 四張最小派工卡（依 #1199 留言歸納，非客戶逐字派工；模型、Effort、日期依當輪卡片，本檔不寫）

- **A**（歸納，非客戶逐字派工）｜治理文件與永久交接（#1274）；設計裁示統整，依 A 回存歸納（c7158239712、c7161029065）；依客戶裁示擔任指定 PR 合併 owner｜邊界：#1274 本身不含產品碼｜驗收：exact head、同 head 五項 CI＋Slow step、非作者 QA（c7131915767、c7147969987、c7157145655）
- **B**（歸納，非客戶逐字派工）｜唯一共用 UI／Contract writer（New UI2）；C 不共編｜需線框／Copy／Contract Gate 者先出草稿、客戶拍板才施工；109.0／160 守衛與 Delta BELOW 不放寬｜驗收：390／1280／1440 真畫面、非作者 QA、五項 CI（c7131915767、c7162031909）
- **C**（歸納，非客戶逐字派工）｜OneBrain 資料承載與 Digest v2 設計／驗收矩陣；隔離 FAKE 預覽（#1268，tests-only）、K2 原型（#1278，tests-only）｜不改共用 UI／Contract、不改正式 Digest v1；不得開正式 Provider／caller、真資料或快取寫入（客戶原文 c7131915767）；另「本輪設計規劃不取數」為 C 自身回存（c7156469742、c7162202145），非客戶原文｜驗收：合成證據、正負控、Work 獨立驗收（c7131915767、c7162202145）
- **Work**（歸納，非客戶逐字派工）｜獨立唯讀驗收：只核新增差額、原 Merge Gate、main push CI 五項＋Slow 實際 step；不重跑已 PASS 矩陣、不施工、不合併。無法執行時由備援角色 O 承接未驗差額（條件式，非第四條施工線）｜驗收：PASS／HOLD／NOT VERIFIED 附可回查證據（c7147969987、c7148133320）

## 5. 現況快照（2026-11-25；過期即不可信）

- **最新接續存檔：c7165164441**（FACT／APPROVED／PROPOSED／HOLD／NOT VERIFIED；先讀此留言及其後有效裁示）。
- APPROVED：A/B/C 並列、最多三活躍施工線、單一寫者與檔案隔離；D 唯讀不占施工槽位、O 原條件式備援；Work 功能→畫面→正式 Gate，不降低原 Gate。
- 永久靜默：禁止過程回報及碎碎念，證據寫 GitHub；必要裁示／重大 FAIL／整批完成才回報，最多五行。

| 項目 | 快照 | 出處 |
|---|---|---|
| main HEAD | `2fd0773e`（#1280 P-1 合併，05:40Z） | GitHub API |
| #1274 | docs 治理收口（DEC-226／第 35 節）；head `9f016862`；Draft；四輪非作者 QA PASS；待明示 Ready／merge 授權 | c7162261882 |
| #1278 | K2 decision_digest.v2 tests-only 原型；head `a863b747`；Draft；base 落後 | PR 頁 |
| #1268 | OneBrain 持股 FAKE 示範 Stage2 A1 tests-only；head `826cc9e6`；Draft；base 落後 | PR 頁 |
| #1237 | NAS 安全補丁候選；head `c406fb5f`；Draft；HOLD merge／部署 | PR 頁 |
| 最新客戶正式裁示 | c7151544405（#1273 Cloud Gate A、#1280 P-1 A；已依序入庫） | c7151544405 |
| 近期客戶指示 | 一鍵複製精簡派工格式 c7148182082；備援 O c7148133320；Work 備援 c7148028894；V1.2 唯讀盤點放行 c7164122838（不授權實作或刪除） | 各留言 |
| #1281（本檔） | FACT：同步前 head `0a553ad7`、68 行，MF-RESUME-1 修正已呈現；同步後 exact head、CI／獨立 QA NOT VERIFIED；Draft，不 Ready／merge | c7164471316、c7165164441 |
| 各線最新回存 | A c7164463719｜B c7164432247｜C c7163715572｜Work c7164471316（同步前快照 549 則；本輪存檔 c7165164441） | 各留言 |
| 未完成（只列指標） | Digest v2 裁示包 A c7161029065＋補註 c7161067915；MF-AC2 更正 C c7162202145；B 接入狀態裁示包 c7160953590／c7162031909（待客戶回覆）；B Y 守衛採 Work 兩條測試定位、仍 HOLD（c7164432247）；#1274 待授權。Work c7162964168 判定：B 兩項設計差額 PASS、Y 守衛定稿仍 HOLD；C 歸因更正與負控 PASS、A 整合口徑仍 HOLD（A c7161029065 §2.4 仍待採用 C 更正 c7162202145）；#1274 治理 QA PASS 沿用、Merge Gate HOLD。其後 A c7164463719 回存標題為採用 C 更正（Work 尚未複驗） | 各留言 |

- PROPOSED：Work 先驗 #1281 同步後新差額，再驗 A MF-AC2 整合口徑，後驗 #1268 尚未通過的實際功能與畫面；B 等 Y 守衛裁示，C 回原授權內功能差額，D/O 暫不啟動。
- NOT VERIFIED：上述歷史 PASS 指標未於本輪逐則重讀；完整 LIVE Gate、最新 CI 與 reviews/threads 待驗，不將歷史或作者證據冒充即時 PASS。

## 6. HOLD（非窮舉；來源：規格第十一章與 c7162261882；**本檔不解除任何 HOLD**）

v1.1（Catalyst Radar／Signal Log／Canonical Evidence Store）、#1237 NAS、Cloud cutover、真持股／Sheet／OAuth、Secrets、正式 LINE、正式 Provider／caller／付費 AI、未核准來源／公式、比較 producer／歷史快照寫入、AI 快取寫入／排程、DG-PIT／LIC／SCOPE／COV、I1144-WIRING-GATE、DEC-185 三支停用 workflows。

## 7. 禁止事項

- 不得把本檔當第二 SSOT，不得據以施工或宣稱 PASS。
- 不得新增 Gate、不得跨線共編、不得自行解除 HOLD。
- 本檔快照與 #1199 或 GitHub 即時狀態不符時，以後者為準並回報差額。
- 未驗證的狀態一律標 NOT VERIFIED；無即時證據不得沿用本檔數字。
