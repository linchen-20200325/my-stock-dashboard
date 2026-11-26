# RESUME｜衍生接續索引（DERIVED INDEX ONLY，無獨立決策效力）

> 唯一 SSOT：https://github.com/linchen-20200325/my-stock-dashboard/issues/1199
> 本檔不是第二 SSOT；與 #1199、有效 DEC、Contract、PROJECT_RULES 衝突時，以後者為準。不得據本檔施工、Ready、merge、部署或解除 HOLD。
> 快照：2026-11-26（台北），main `0ceeb971a5aa3206171e88603b29dd44ff257dfd`；最新讀到 #1199 留言 c7192864454（V1.3 制度錨點 c7192149293）；每輪重查 LIVE，過期即不可信。
> 出處：c<數字>＝#1199 留言 ID（`https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-<數字>`）。

## 1. HOT｜最新版入口（先讀本檔；權威仍是 #1199，再取差額）

- **V1.3 接續制度 c7192149293**（APPROVED；非產品 v1.3）：新對話只輸入「接續」，本檔為唯一首讀導航索引（≤80 行）；正式 QA／施工／合併仍完整原 LIVE Gate。**R22 增量僅限接續制度與 D 線**，不取代 R21 的 A/B/C/Work/O 派工。
- **LATEST_HANDOFF：c7191455542**，R21 完整交接與全量 HOLD；最新增量 R22.1 c7192459223、R22.2 c7192570719（總管狀態，非新施工授權）、Work QA c7192593347（承 c7191602881）。另讀其後有效裁示。
- **CURRENT_TARGET R2：c7182728412**；產品 v1.0／DEC-224（`UI2-ONEBRAIN-PRODUCT-V1.0-APPROVED-2026-11-23`），Real Data First；五頁：📊市場／🎯標的／💼持股／👤我的／🗂資料；確定性權威不變。
- **目標補充 c7192864454**（總管，2026-11-26；補充 R2，不取代）：全線共同目標＝完成 UI2＋OneBrain，Real Data First，先收口無 AI 可用的真實資料儀表板；文件／CI 通過不等於產品完成；六項 HOLD 不變。
- **CURRENT_PLAN R21：c7191389677**（A/B/C/Work/O 派工）＋ **R22 增量 c7192149293**（僅接續制度與 D 線）；三線平行、按可用功能分批交付，不是新施工授權。
- **CURRENT_GOVERNANCE r02：c7184169826**；r01 c7178099841 未被取代部分有效，其內舊入口 TARGET 7166092247／PLAN R3 已 SUPERSEDED。
- V1.2 HOT/WARM/COLD c7164122838；版本鏈及「接續」c7167230635：歷史保留，**與 V1.3 衝突部分 SUPERSEDED**，未衝突部分有效。V1.1／V1.3 接續制度不同於規格第十章產品 v1.1（Catalyst Radar／Signal Log／Canonical Evidence Store，HOLD）。
- APPROVED：R20 B 修正 c7191058929（全裝置 20/60，預設20，120另案，零JS／守衛不放寬）；R16 C 兩檔 c7186895108；R14 A 有限公開規格文件唯讀及六問方向 c7185508753。具名授權未被取代部分有效。

## 2. 接續方式與原正式 Gate

- 日常：新對話輸入「接續」→ 先讀本檔（唯一首讀索引）→ 再核 #1199（唯一 SSOT／權威）最新正式交接、CURRENT_TARGET/PLAN/GOVERNANCE 與其後有效裁示 → LIVE main/Open/Draft head/base → 必要差額；不重讀全部 repo/歷史/CI logs。
- 正式 QA／施工／合併：依 D2 原讀序與完整原 LIVE Gate，核精確 head/base/candidate、必要 diff/tree、五項 CI＋Slow AppTest 實際 step、reviews/threads、有效授權及獨立 QA；同 head 已 PASS 無差額不重驗。
- WARM：CLAUDE.md、PROCESS.md、PROJECT_RULES.md（§15、§25、D2）、docs/DECISIONS.md、docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md、docs/vnext/ONEBRAIN_ARCHITECTURE_DECISION_2026-10-31.md、docs/vnext/UI2_ONEBRAIN_FULL_PRODUCT_SPEC_V1_0_2026-11-23.md、docs/vnext/READ_FIRST_UI2_ONEBRAIN_VERSION_AND_DEC_DRAFT_2026-11-23.md；必要五檔/最新 HANDOFF。正式效力和原讀序優先，本檔不覆蓋。
- COLD：歷史成果、被取代版本、舊 logs 按需引用；不為更新索引重驗舊證據。

## 3. 三行硬約束（來源 c7110402272；正式規則優先）

- 【範圍鎖定】只改具名授權檔案／差額，不跨線共編、不順手重構、不新增 Gate、不解除 HOLD。
- 【誠實降級】missing≠0、unknown≠safe、STALE≠fresh、Real 不以 FAKE 補畫；確定性規則唯一權威；未核標 NOT VERIFIED。
- 【退回門檻】越權、權利/PIT、安全/契約衝突、守衛放寬、證據破壞、MF/CI FAIL 或 head/base 差額令證據失效即停，依原 Gate 補證。

## 4. 最新派工卡（僅 R21 衍生索引）

- A｜P0/P1：c7183081296 TWII、c7184227847 個股；R14 有限規格文件 B2/B3，尚無回存；六問 #1197 comment6947565503 需指定寄件者/管道/實際發送授權，未寄；不真取數、不落盤。
- B｜P0/P1：#1283 R20 修正已交（c7192318863，head 4a107bdd）；Work HOLD／MF1（c7192593347）：按具名 MF 修正；DEC-156 待合法交接。其後依 R21 唯讀收斂持股/我的一個合法操作候選，不擴權。
- C｜P2：#1284 兩檔隔離原型，Work HOLD／MF1／SF1（c7192593347）；大盤決策包已交 c7192861785（僅設計）：今日無合法路徑產出正式大盤結論，不建議再做大盤原型；客戶一題（推薦 A 維持 HOLD；不回覆＝A）。
- Work｜差額 QA 已回存 c7192593347（#1283／#1281／#1284 皆 HOLD／MF1）；修後新 head 到即核新增差額及原未驗項，依原正式 Gate；#1281 僅核索引差額，勿阻塞產品。不可代施工或以 CI 代 QA。
- D｜V1.2 唯讀瘦身，不占槽；R22（c7192149293）授權：確認單一 writer 後僅更新本檔、追加 commit、不另開 PR；寫入權衝突／有效裁示遺失／原 Gate 降級即停；分支清理獨立維護，唯一候選仍待外部依賴確認，不刪。O｜STANDBY，無具名合法空槽不啟動。
- **下一步排序（D 依 c7192864454 最小改動排列；PROPOSED，非授權）**：①B 修 #1283 MF1→Work 差額；②Work 複驗 #1281 新 head；③A #1197 TWII 合法更新缺客戶指定寄件者／發送授權（C 包指出無合法新鮮行情則大盤證據皆被擋）；④#1284 MF1／SF1：C 依既有 MF1/SF1（c7192593347、R22.2）處理；⑤C 大盤待客戶一題；其餘依原 HOLD。
- 文件治理｜c7190746609 歷史交接已存；#1274→B DEC writer 合法交接尚缺，不共寫、不改 #1274。
- A/B/C 現有 Claude/High、Work GPT-6.2/High、D 現有 Sonnet/Medium、文件治理 Sonnet/High、O 待命（依 R21）；已在執行不重啟，實際執行狀態 NOT VERIFIED。

## 5. FACT｜交接快照（精確 SHA/base 見 c7191455542／c7191602881；以 LIVE 為準）

| PR | 快照 head | 狀態／證據入口 |
|---|---|---|
| #1282（已合併） | d1c57c4c | 工程正式 Gate 及 main CI PASS（既驗）：c7183080873、c7185239838；Cloud 非 PASS |
| #1283 | 4a107bdd | Draft；Work HOLD／MF1／SF0（c7192593347）：20／60 實測、120 負控、四 JSON 通過；1.56.0「20 日」按左鍵跳資料頁待修；exact CI 5/5、Slow step 5 success；Cloud／真機 NOT VERIFIED |
| #1284 | 759600eb | Draft；舊 head CI 5/5、Slow step 5 success（R17）；Work HOLD／MF1／SF1：1.56.0 無障礙選取狀態缺失；Real degraded 隔離已實測（c7191602881） |
| #1281（本檔） | ad7fbc5b 之後 D 追加 commit | Draft；Work HOLD／MF1（c7192593347）：首讀順序已據以統一，待 Work 差額複驗；精確 head／CI 以 LIVE 為準；舊 head CI 不延伸；原 Merge HOLD |
| #1278 | a863b747 | Draft；K2 原型既驗差額沿用，正式 HOLD |
| #1274 | 9f016862 | Draft；治理歷史 QA PASS，Merge HOLD |
| #1268 | 826cc9e6 | Draft；技術 PASS/MF0（c7165198005），Merge HOLD |
| #1237 | c406fb5f | Draft；NAS merge/部署 HOLD |

- 已驗證據：R17 c7190579779、Work c7185239838、c7165198005；A MF-AC2 PASS 僅口徑閉合；#1283/#1284 作者交付 c7188933683/c7189779817 不代 Work。Work 新差額見 c7191602881；#1284 原生 browser lane 未涵蓋新檔，完整讀屏及非 Chromium 為 NOT VERIFIED。
- PROPOSED：B 持股/我的操作與 C 大盤正式整合候選僅設計；不自動施工。#1107 Cloud PARTIAL，deployed SHA/真機 NOT VERIFIED。

## 6. HOLD｜指標非窮舉；全部未解除項見 c7191455542、有效正式規則及後續裁示

- #1283 修後 Visual/DEC 同步/QA、#1284 1.56.0 無障礙選取態修正及驗收、#1281 新差額/provenance、#1274/#1278/#1268/#1237 原 Merge HOLD；無 Ready/merge/deploy 授權。
- #1197 DG-LIC/PIT/六問發送；個股 LOOKUP B1–B7、DG-LIC/PIT/SCOPE/COV、#1124–1126/#1119、DEC-185 三支停用 workflow、TWII-only 發布另案。
- #1107 Cloud、#1110 NAS/Proxy、Cloud cutover、Secrets、Sheet/OAuth/真持股/私人資料、I1144-WIRING-GATE。
- Q1/D-A/D-J/C3/D7、S2 正式准入、S4/S5、Stage F/G、正式 producer/caller/Provider/付費 AI、schema/快取/排程/外傳；不回加已取代 K2 原型限制。
- 產品 v1.1、正式 LINE、未核准資料/公式/風控、比較 producer/歷史快照、120另案、JS 例外、未核准分支刪除；所有其餘原 HOLD 保留。

## 7. NOT VERIFIED／永久靜默

- 本次非完整正式 Gate；舊 CI/QA 沿既驗證據，未重新實跑；AI 實際執行、A 規格取證、B／C 修後新版本驗收、DEC 交接、Cloud/實機及外部依賴未核。
- 最多三活躍施工線、單一 writer；D/Work 唯讀不占槽。P0/P1 優先交付，P2 平行；不因局部阻塞全面停工。
- 所有 AI 永久靜默；正常成果依權限回存 GitHub（D 先交總管）；不發過程/heartbeat、不無差額輪詢或重驗；僅重大 FAIL/安全、必要客戶裁示/人工操作通知，首行僅 🟢/🟡/🔴、最多五行。
