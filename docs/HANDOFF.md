# HANDOFF — 現行交接（my-stock-dashboard）

<!-- CURRENT_RESUME_SNAPSHOT_2026_11_09:BEGIN -->
> **~~最新接手優先讀本欄~~（2026-11-09；歷史快照，非即時 SSOT）**〔📌 已過期，最新接手點見檔尾 2026-11-12 段（有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）〕：查核時 main `f4d6e6a44aeb27b21921e6fa3316f97fbf581623`（#1091 docs-only merge），**Open PR 0**。#1088 macro-history 已合併 `da97d193cbbf30e187dc60b2d724e146622fa88d`，最新 head 原生 CI 5 success、非作者 QA 4912×8 逐列：OHLCV／date／source／NaN 零變更；僅 2026-11-06 列的可變 `fetched_at` 由 11/07 更新為 11/08。一次性窄範圍准許見 **DEC-155**（ChatGPT 裁示，非客戶逐字）。#1038 已 **closed／未合併**，PIT FAIL 證據保留；#1090／#1091 已合併。舊文中「#1038 仍 Draft/open」及「New UI2 只有四頁／五頁未施工」均為歷史時點，不可當現況。
>
> **現行產品區分**：New UI2 已有 📊市場／🎯標的／💼持股／👤我的／🗂資料五頁＋頂部兩列導覽（#1055），但預設仍為 FAKE Preview；資料頁、登入／Sheet、OneBrain 未因導航完成而具備正式接線。新頁或重大功能先依 `PROJECT_RULES.md` Old UI First 五步驟。
>
> **2026-11-09 唯讀校準確認**：`scripts/calibrate_health_weights.py::check_inputs_fresh` 的 `_REQUIRED_DATASETS` 只有 `twii_ohlcv`／`finmind_inst`／`finmind_m1m2`，**不含** `tw_pmi`；因此 `tw_pmi.fetch_outcome=UNDETERMINED` 不能被宣稱為此函式「直接」阻擋的原因。main 的必要 dataset metadata 為 `twii_ohlcv.last_updated=2026-11-06`（無錯），另兩項 `fetch_outcome=NO_NEW_DATA`；其當下 freshness 是否通過及實際季校準結果 **NOT VERIFIED**，需唯讀依現行 `shared/staleness.py` 評估，不放寬門檻或執行校準寫入。真實 cron 發布端到端仍 **NOT VERIFIED**。更正：DEC-155 後果句（docs/DECISIONS.md DEC-155『可能仍因 tw_pmi 為 UNDETERMINED 而阻擋』）與本檔尾 2026-11-09 補註的同句推論不成立——依 `scripts/calibrate_health_weights.py` 的 `_REQUIRED_DATASETS`（twii_ohlcv／finmind_inst／finmind_m1m2），tw_pmi 不在必要資料集內；原文保留為歷史紀錄，未改動。實際 freshness／校準是否通過仍 NOT VERIFIED。
>
> **安全下一步**：每次先做 LIVE GitHub Verification Gate；五頁 UI2 HTML 設計須舊 UI 功能盤點、三方案與使用者 Visual Gate，不擅動正式資料／公式／Risk Cap；季校準只做無寫入測試。下方 2026-11-07 的 Active Gate 與大段舊快照**原文保留為歷史**，若與本段不一致，仍以 LIVE GitHub／現行程式／DEC 為準。
<!-- CURRENT_RESUME_SNAPSHOT_2026_11_09:END -->

<!-- HANDOFF_HISTORY_INDEX:BEGIN lines=13-123 archive=docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md -->
- 📦 **路徑索引（2026-11-12，DEC-173 Q1；只搬不改）**：原 L13–L123 已逐字搬至 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md`（分冊 L9–L119）。現行最新接手段仍在**本檔末尾**（原樣保留）。
  - 原 L14–L75 `HANDOFF_ACTIVE_GATE`（2026-11-07 GitHub Resume Gate；含「### 0. 狀態誤判防止表」「### 4. 新對話最低成本恢復程序」）、原 L77–L122 2026-11-08 最新接手點。
  - 各段標題（節錄；刪除線內文與 markdown 標記略去，原文以分冊為準）：
    - 原 L14 → 分冊 L10：先讀這裡｜GitHub Resume Gate（2026-11-07；由 #1047 引入，…
    - 原 L20 → 分冊 L16：0. 狀態誤判防止表（每次接手必跑，不可只讀 PR 標題）
    - 原 L34 → 分冊 L30：1. 四種不同層次，不得再混淆
    - 原 L45 → 分冊 L41：2. 當下 GitHub 物件清單（時點快照，永遠須重取；更新於 main 9ca5441e…
    - 原 L62 → 分冊 L58：3. 唯一安全接手工作與分工（2026-11-07 晚更新；舊版「補 QA 合併 #1045…
    - 原 L69 → 分冊 L65：4. 新對話最低成本恢復程序（不讀千行歷史、不依賴聊天）
    - 原 L77 → 分冊 L73：最新接手點（2026-11-08｜#1057／#1054／#1059／#1060／ #106…
<!-- HANDOFF_HISTORY_INDEX:END -->

- 📦 **歷史接手點總指標（2026-11-12 追加；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕）**：2026-11-10 晚 Issue #1121 段以前的~~所有~~ Safe Handoff／舊接手點條目（含下方第 0 節前言所指「本檔最末 Safe Handoff」各段）逐字在 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md`；~~本檔只留第 0 節 2026-10-29 Resume Checkpoint 索引（historical）、仍有效的必讀規則，以及 2026-11-10 晚起的接手段；~~〔更正（有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕；#1160 獨立 QA 指出）：上句「所有」與「本檔只留」清單不成立。實情：#1121 以前的 Safe Handoff／舊接手點條目**大部分**逐字在上述分冊（三個 `HANDOFF_HISTORY_INDEX` 區塊標原行號→分冊行號），但仍有舊接手點留在本檔。本檔現存：檔頭 2026-11-09 快照（已標過期）；第 0 節前言的 2026-11-02／2026-11-03 現行接手點指標（所指段落已在分冊）；DEC-126 新永久規則索引；第 0 節 2026-10-29 Resume Checkpoint 索引（historical）；三個 `HANDOFF_HISTORY_INDEX` 區塊；仍有效的必讀規則與交接治理教訓；2026-11-10 晚起的接手段。〕；**現行接手點＝檔尾 2026-11-12 段**。

## 0. 短版交接（現行，2026-10-22）

> 📌 **2026-11-12 REORG3C-REF-SYNC（舊標題與歷史原文不改）**：本節的「現行，2026-10-22」僅為當時命名與分工規則，不代表其下 2026-10／11 舊接手快照仍有效；新對話請先即時驗證 GitHub，再讀**本檔最末尾**最新有效 Safe Handoff／Resume Checkpoint，並核對正式 DECISIONS／BACKLOG／PROJECT_STATE。早期 Safe Handoff 已部分逐字搬至 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md`，其餘保留段亦是時點紀錄；依 DEC-172 D2、DEC-173 Q1／Q6 與客戶 REORG3C-REF-SYNC 授權。

> 依客戶 2026-10-22 裁示（DEC-068），本檔改為**短版交接**：只保存 current active work、blocker、next safe point、必要的 main／PR／CI 狀態。完整專案知識見 `docs/PROJECT_STATE.md`；未完成工作見 `docs/BACKLOG.md`；新對話啟動程序見 `PROJECT_RULES.md` 第 15 節。**現況以本節與 GitHub 為準。**

> 📌 **2026-11-02 現行接手點**：見本檔**最末**「~~Safe Handoff（2026-11-02，Final UI Contract Freeze）~~ ~~Safe Handoff（2026-11-02 更新：Freeze 已拍板）~~ ~~Safe Handoff（2026-11-02 New UI2）~~ ~~Safe Handoff（2026-11-02 New UI2 Architecture 客戶核准）~~ **Safe Handoff（2026-11-02 New UI2 Semantic Correction Gate）**（④ 2026-11-02 DEC-124 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-124）＋AI 總管〔事實更新〕；原文刪除線保留；Batch 1 段亦已標過期）」（DEC-122）（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔事實更新〕；原文刪除線保留）；下方索引表為 2026-10-29 起的歷史索引，必讀規則仍有效（有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕）。② 2026-11-02 客戶 New UI2 裁示後更新（DEC-123；決策者 客戶（DEC-123）＋AI 總管〔事實更新〕；有意識的更新，不是漏刪）；③ 2026-11-02 客戶裁示 Q1～Q4＋#996 合併後更新（DEC-123 裁示；決策者 客戶（DEC-123 裁示）＋AI 總管〔事實更新〕；有意識的更新，不是漏刪）。（#997 稽核 m3：上一版把 #996 的括號標註改寫為「更新紀錄 ①」，已還原為 #996 原文逐字、再追加 ②③。）

> 📌 **2026-11-03 現行接手點更新（append）**：最新為本檔**最末**「**Safe Handoff（2026-11-03 New UI2 Batch 2 …；現行）**」；上一行所指 Semantic Correction Gate 段已標「~~現行~~」（有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕）。

> 📌 **2026-11-03 最新現行接手點（DEC-128，append）**：**先讀 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md` 與 `docs/DECISIONS.md` DEC-128**——它們是 New UI2 presentation 的唯一有效讀法（四頁 Human UI 不顯示完整 L2／L3、完整診斷集中 👤 資料健康度、UI VM ≠ Decision Digest）；⛔ 依舊 Wireframes L2／L3 expander 施工。現行 Safe Handoff＝本檔**最末**「Safe Handoff（2026-11-03 Presentation Compression ≠ Information Loss／DEC-128…）」（上方各 Safe Handoff 段已降為歷史，有意識的更新，不是漏刪）。

> 📌 **新永久規則（2026-11-03，DEC-126）**：**多元解法與最小成本決策規則**＝`PROJECT_RULES.md` **第 29 節**。一句話：遇到問題先在內部比較 ≥3 個方案、選 Minimum Sufficient Path，不得在同一路徑原地試錯或用更高模型／更多 Token 掩蓋錯誤路徑；僅 6 種情形才回報客戶 3 方案（須附推薦）。**新 session 先讀 `PROJECT_RULES.md` 第 29 節**（原文逐字見 `docs/DECISIONS.md` DEC-126）。本段僅為索引，非規格 SSOT。

### 📌 Resume Checkpoint 索引（現行；2026-10-29 Phase 1 SSOT Reset／Contract Freeze；DEC-086 欄位＋DEC-109 索引要求）

> 📌 **2026-11-12 REORG3C-REF-SYNC（原索引標題保留）**：此處「現行」已過期，本表是 **2026-10-29 歷史 Resume Checkpoint**，不可當成最新 main／PR／下一步；目前有效的 15 欄 Resume Checkpoint 在檔尾 2026-11-12 Safe Handoff，使用前仍須重查 GitHub。當前下一安全行動以即時 main／PR／CI 與已核准裁示交叉驗證，禁止按舊表執行。

> **HANDOFF 只是索引，不是規格 SSOT**（客戶 DEC-109 二十六）；本節只指向正式文件。**GitHub 操作事實優先於本節；不一致時修正本節**（`PROJECT_RULES.md` 第 20 節、第 25 節事實軸）。本節以下全部內容為 **historical**——⚠️ **例外**：舊段中仍有效的**必讀規則不屬 historical**，例如「⛔ 禁止事件回音」、Hard Output Gate（DEC-104）、DEC-106（Model×Effort 不重複要求切換）、Scope Inflation Guard（DEC-103）；其效力以 `docs/DECISIONS.md` 各條為準，不因所在段落被標 historical 而失效。

| 欄位 | 內容（2026-10-29） |
|---|---|
| latest verified main SHA | **`3bbdaf0f`＝Phase 1 合併點**（PR #971 squash；撰寫時 `git fetch origin` 實查 main＝`3bbdaf0fa704501633b90ccd7675c2c1413c4ef9`）。⚠️ 之後 cron 會推進 tip，**一律以 `git fetch origin` 實查為準**，不引用本欄當前值。<br>~~**本 PR 合併後的 main**（以 `git fetch origin main` 實查為準；cron 會推進 tip）。PR base＝`978ecedc`（cron；parent＝#969 `71587857`，最後非 cron 合併）~~（2026-10-29 Safe Handoff 有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；上一值刪除線保留） |
| current working branch | 交接後可為**任何新分支**。`ccr-6eace3b6-0gglrs` 在撰寫時已等於 main `3bbdaf0f`（僅加本 Safe Handoff docs commit，一般 push）；新 session 以 `git fetch` 實查為準。<br>~~`ccr-6eace3b6-0gglrs`（撰寫時基準 `55739129`＝`978ecedc`＋#970 commit `06a7a3e5` 的 merge；其上為 Phase 1 docs commits；一般 push，未 force）~~（2026-10-29 Safe Handoff 有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；上一值刪除線保留） |
| current PR | **無**（Open PR 0；2026-10-29 以 GitHub REST 實查，**以 GitHub 實查為準**）。Phase 1＝**PR #971 已 squash 合併**（merge `3bbdaf0f`；Fast checks／Slow tests 皆 success）；**#970 已關閉為 superseded、未合併**，原貌只在 commit `06a7a3e5`，**不在 main 歷史**。<br>~~**head=`ccr-6eace3b6-0gglrs` 的 open PR（取代 #970）**（號碼以 GitHub 實查為準；以 **squash merge** 合併，`06a7a3e5` 不進 main 歷史）；**#970＝superseded，由總管關閉**（留言指向 commit `06a7a3e5`；#970 原貌只保存在該 commit）~~（2026-10-29 Safe Handoff 有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；上一值刪除線保留） |
| current task／batch | ~~**無進行中施工；Phase 2 尚未開始。**（Phase 1 SSOT Reset／Contract Freeze 已完成並合併：DEC-109 客戶；DEC-110 總管內部）~~已被 📌 2026-10-30 取代（有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；已被 📌 2026-10-30 取代，原文保留）。現行首句：**Phase 2 已完成（步驟 0、1、2＋4、5；步驟 3 已取消）；無進行中施工；Phase 3 尚未開始。**<br>~~**Phase 1 SSOT Reset／Contract Freeze**（DEC-109 客戶；DEC-110 總管內部）——docs／governance＋非 production 工具 `tools/visual_fidelity/`；0 產品程式變更~~（2026-10-29 Safe Handoff 有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；上一值刪除線保留）<br>📌 **2026-10-30 更新（有意識的更新，不是漏刪；決策者 AI 總管（事實更新））**：~~**Phase 2 步驟 0 完成（docs-only，待本 PR merge）**；步驟 1～5 尚未開始。~~（已被取代，見下）實測結果＝Migration Plan **§12**（main `64fdeae`）。<br>📌 **2026-10-30 更新（步驟 1）**：~~**Phase 2 步驟 1 完成（共用層可選參數；工作樹 diff 未 commit）**；步驟 2～5 尚未開始。實測與結果＝Migration Plan **§13**。~~（已被取代，見下）<br>📌 **2026-10-30 更新（步驟 2＋4，有意識的更新，不是漏刪；決策者 AI 總管（事實更新））**：**Phase 2 步驟 2＋4 完成（tests-only；工作樹 diff 未 commit，`src/` 0 diff）**；步驟 3 已取消（Migration Plan §4）；~~**步驟 5 尚未開始**~~（已被 📌 2026-10-30 步驟 5 與收尾取代）。實測、等強論證、mutation 對照、已知缺口＝Migration Plan **§14**。單組實作＋兩組獨立 QA。<br>📌 **2026-10-30（步驟 5 與收尾）（有意識的更新，不是漏刪；決策者 AI 總管（事實更新））**：**Phase 2 步驟 0、1、2＋4、5 完成（步驟 3 已取消）；Phase 2 收尾（docs-only，`src/`、`tests/` 0 diff）。** mutation 判定表、零資料語意證明 (a)～(g)、DoD 對照＝Migration Plan **§15**。~~無進行中施工。~~（已被下方 📌 2026-10-30 Phase 3 步驟 0 取代）<br>📌 **2026-10-30（Phase 3 步驟 0，有意識的更新，不是漏刪；決策者 AI 總管（事實更新））**：~~**Phase 3 步驟 0 完成（docs-only；`src/`、`tests/` 0 diff；未 commit）——「Phase 3 共用視覺元件」文字線框草稿＋客戶裁示表已產出，待客戶拍板。**~~（已被下方 📌 2026-10-30 客戶裁示取代；原文保留） 文件＝`docs/vnext/PHASE3_SHARED_COMPONENTS_WIREFRAME_2026-10-30.md`（現況實測、11 項元件線框〔桌機 1440×900／手機 390×844、冷啟動／已載入〕、與 W1～W9 關係、驗收與守衛計畫、未驗）。📌 **rev2（2026-10-30，有意識的更新，不是漏刪；決策者 AI 總管（內部））**：~~rev1 的裁示題 D1～D9~~（已被取代）依兩組獨立 QA（QA-B 合規、QA-A 事實）修訂為**七題：D1a（客戶裁示色：CTA、中性灰藍；light 中性值為 AI 暫選可推翻）、D1b（非客戶色與圓角的收斂時程：Phase 3 全站一次〔R15 原時程〕vs 延到 Phase 4～6 逐頁〔＝調整 R15 時程〕）、D3（chip 三族外觀；護欄虛線與既有虛線語意衝突，推薦實線粗框）、D5（迷你線與小倍數是否顯示數字）、D6（冷啟動次要圖空槽是否縮小）、D8（切換鈕樣式；舊頁程式註解記載的偏好〔註解標為 2026-08-27，無對應 DEC〕，新四頁請裁示）、D10（圖 A chip 6 顆：來源進摺疊／兩護欄合併／6 顆）**；D2 併入 D1b，D4、D9 移除（契約與內部自決已定），**D7（站殼間距）改為內部先量測、量到真值後才另送客戶**。📌 **rev3（2026-10-30，有意識的更新，不是漏刪；決策者 AI 總管（內部））**：依複審修訂——裁示表題幹與選項去除內部代號（出處移文末腳註）、D1b 題幹明寫「不回應＝R15 改為逐頁收斂」並引 DEC-109 二十四、D6 補「調整契約冷啟動字面」註記與 B 方案冷啟動線框、D8 改述為舊頁程式註解記載的偏好、tile 內允許一顆窗口 chip 並補 chip 合計上限、「不等距」改放摺疊「限制」段、補 D10 (b) 已載入線框與合併護欄 chip 的 kind 規則；題號與七題不變。修訂版未再經下一輪驗證。~~**拍板前不寫任何 UI code。**~~（已被取代）<br>📌 **2026-10-30（客戶裁示後，DEC-115）（有意識的更新，不是漏刪；決策者 AI 總管（事實更新），依客戶 2026-10-30 裁示 DEC-115）**：**客戶已就 Phase 3 線框 §6 七題裁示：D1a=A／D1b=B／D3=A／D5=A／D6=B／D8=B／D10=(a)＋七項補充邊界**（`docs/DECISIONS.md` DEC-115；線框檔已改為『已核准』並新增 §6『裁示結果』；與裁示相左的草案內容就地標『未採用』）。契約 §4／§6／§8-4／§11／§14／§19／§22 已就地加註（D6 調整 §8-4 冷啟動字面、D1b 調整 R15 時程、D10(a) 調整圖 A chip 配額）。~~**current task＝Phase 3 步驟 1：新純字串模組 `src/ui_v2/compact.py`＋tokens 加性新增＋golden／mutation**（施工拆分與每步 DoD＝Migration Plan **§16**）。本批為 docs-only 落盤（`src/`、`tests/` 0 diff）；步驟 1 尚未開始。~~（已被下方 📌 2026-10-30 Phase 3 完成取代；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；原文保留）<br>📌 **2026-10-30（Phase 3 完成，待站殼裁示；有意識的更新，不是漏刪；決策者 AI 總管（事實更新））**：**Phase 3 步驟 1～5 已處理**：步驟 1＝`src/ui_v2/compact.py`（#979 已合併）；步驟 2（`_ui_kit` 薄封裝）**判定不需要、未做**（compact 純字串已足；掛頁時由 Phase 4 以最小薄封裝處理，受鏈／z60 屆時以當時 main 重測；已登 BACKLOG）；步驟 3 站殼量測完成、**AI 總管判定屬整體 layout 變更 → 待客戶裁示（D7）**；步驟 4 D8=B 在 floor 1.56.0（及 1.59.2）成立（5 條硬性約束；`st.html` 剝 svg）；步驟 5 預覽與 Gate 元件層自評完成。本輪（工作樹、**未 commit**）另含 compact.py／test_compact.py 修正（`non-scaling-stroke`、孤立點 r=2.5、`TopN.more_chip()` 等）。結果＝Migration Plan **§17**。**Phase 3 唯一未結＝站殼間距客戶裁示（D7）**；本批不新增 DEC（裁示尚未發生）。 |
| completed in this batch | Phase 1（已合併 #971）：新文件 7 份＋baseline 截圖 15 張＋`tools/visual_fidelity/`；DECISIONS（DEC-109 逐字、DEC-110、DEC-111／112 補登、14 條舊 DEC 條頭標記、DEC-108 客戶原文補登、§5 取代鏈）；PROJECT_RULES 第 24～26 節＋第 7／11／19.11 節補註；PR 模板 Visual Fidelity 段；BACKLOG §5.1.16＋過期列更正；PROJECT_STATE §48；本索引；移除 #970 線框檔＋15 png；0 產品程式變更。本 Safe Handoff 追加：DEC-113／114、Migration Plan §11 預備實測、GOV-CHATTER 第二次復發紀錄（docs-only）。<br>📌 2026-10-30：Phase 2 步驟 0 實測寫回 Migration Plan §12（append-only；3 組單組實測＋總管自驗 ①②④，未經第二輪 QA）；BACKLOG 登 2 項 P2；0 產品程式／tests 變更。<br>📌 2026-10-30（步驟 5 與收尾）：Migration Plan §15（M1～M13 判定：M5／M6／M13 實跑必紅、M10 部分適用實跑、步驟 1 的 spark／fold_label mutation 重跑，共 18 個 mutation 無存活；其餘 N/A 待 Phase 3／`CV1-DR-12`）；零資料語意證明 a～g 以 main `59201e2` 對 `64fdeae` 實測；全套 fast lane 35366 passed／0 failed／46 skipped／185 deselected（slow）；docs-only。 |
| exact current stopping point | ~~**Phase 1 完成並已合併；本對話已 Safe Handoff／Session Close，未開始 Phase 2。** `waiting_for_customer＝false`（無新客戶 Gate）。~~已被 📌 2026-10-30 取代（有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；已被 📌 2026-10-30 取代，原文保留）（現行見本欄末句：Phase 2 已完成，未開始 Phase 3）。<br>~~**Phase 1 文件落盤完成；合併＋main verification 前 Phase 1 未完成**；`waiting_for_customer＝false`（本 phase **無新客戶 Gate**）~~（2026-10-29 Safe Handoff 有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；上一值刪除線保留）<br>📌 2026-10-30：~~**Phase 2 步驟 0 已完成並落盤（待本 PR merge）；步驟 1 尚未開始。**~~（已被取代）~~**步驟 1 已完成（工作樹 diff 未 commit）；步驟 2 尚未開始。** `waiting_for_customer＝false`。~~（已被 📌 2026-10-30 步驟 5 與收尾取代）<br>📌 2026-10-30（步驟 5 與收尾）：**Phase 2 已完成（步驟 0、1、2＋4、5；步驟 3 已取消）；~~本對話可 Session Close，未開始 Phase 3。~~（已被取代，見本欄末句 📌 2026-10-30 客戶裁示）** `waiting_for_customer＝false`（無新客戶 Gate；Phase 3 的線框拍板 Gate 在線框送出後才成立）。<br>📌 **2026-10-30（客戶裁示落盤後，DEC-115）（有意識的更新，不是漏刪；決策者 AI 總管（事實更新），依客戶 2026-10-30 裁示 DEC-115）**：Phase 3 步驟 0 客戶裁示已落盤（docs-only，待本 PR merge）；**Phase 3 步驟 1 尚未開始**。`waiting_for_customer＝false`（七題已全裁示，無待客戶 Gate；站殼量測結論若屬整體 layout 變更才會成立新 Gate）。 |
| next single action | ~~**Phase 2（Helper／Test Contract Migration）第 0 步**：以**當時 main** 重新實測 T1～T26 測試清單、還原鏈 sha 守衛覆蓋、H 系列 caller，寫回 `docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md`（append-only），⛔ 改產品程式（Migration Plan §4；BACKLOG `P1R-PHASE2-HELPER-TEST-MIGRATION`）。**先讀 Migration Plan §11**（前一對話的單組預備實測，未經第二組驗證，以當時 main 重測為準）。開工前依 DEC-084／DEC-106 比對目前實際 Model×Effort，符合即靜默繼續。~~（已被 📌 2026-10-30 取代）<br>~~有序步驟（已完成，歷史）：① 總管關閉 #970 → ② 開新 Phase 1 PR → ③ CI 綠 → ④ squash merge → ⑤ main verification → ⑥ Phase 2 第 0 步~~ **①～⑤ 已完成**（#970 已關閉 superseded；#971 squash 合併 `3bbdaf0f`，CI 雙綠）；僅 ⑥ 留作下一步。<br>📌 **2026-10-30 更新**：步驟 0 完成（Migration Plan §12）。~~**下一唯一安全接手點＝Phase 2 步驟 1**（Migration Plan §4／§12.5：共用層可選參數，預設輸出逐 byte 不變；先讀 §12，動工前 `git fetch` 重確認 main）。~~（已被取代：步驟 1 已完成）<br>📌 **2026-10-30（步驟 1 完成後）**：~~**下一唯一安全接手點＝Phase 2 步驟 2**：改寫 T2～T7、T13、T5 為資訊守恆斷言（現行畫面下仍綠）；範圍限 p02～p05，⛔ 不碰今天頁 hover-only 測試與受鏈檔。先讀 Migration Plan §13（含已知限制），動工前 `git fetch` 重確認 main。~~（已被取代：步驟 2＋4 已完成）⚠️ **Model×Effort 以 DEC-113 為準＝Sonnet 5.5＋Medium**（R19 原文已被 DEC-113 取代）；開工前只需依 DEC-084／DEC-106 核對實際設定，不符才通知客戶切換。<br>📌 **2026-10-30（步驟 2＋4 完成後）**：~~**下一唯一安全接手點＝Phase 2 步驟 5**：§6 mutation 清單逐一拔守衛必紅（M1～M13 中與 Phase 2 現有碼相關者；M11／M12 欄數待 `CV1-DR-12` 裁示，不做），然後收尾 Phase 2（零資料語意證明、DoD、HANDOFF）。先讀 Migration Plan **§14**（含未覆蓋缺口與未驗項）；動工前 `git fetch` 重確認 main。Model×Effort 仍以 DEC-113 為準。~~（已被 📌 2026-10-30 步驟 5 與收尾取代）<br>📌 **2026-10-30（Phase 2 完成後）（有意識的更新，不是漏刪；決策者 AI 總管（事實更新））**：~~**下一唯一安全接手點＝Phase 3 步驟 0：重測 main、盤點 Shared Visual Components 規格並出文字線框草稿（含 W 點、版面差異、總管推薦）送客戶拍板；拍板前不寫 UI code~~（已完成：線框草稿已產出；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；現行見本欄末 📌 2026-10-30（Phase 3 步驟 0 完成後））（**Phase 3 以較嚴者為準：不論共用元件是否掛頁，寫 UI code 前先出文字線框供客戶拍板**）。**先讀 Migration Plan **§15**（含 15.1 的 N/A 待 Phase 3 mutation 清單、15.3 截圖 Gate 須恢復、`P1R-SPARK-TRUSTED-HTML`、`.blk-chips*` 尚無 CSS）；動工前 `git fetch` 重確認 main。Model×Effort：Phase 3 起判 Opus 5.5＋High，進入明確機械式實作後切 Sonnet 5.5＋Medium（依 Plan §1 與 DEC-084／DEC-106 開工前核對實際設定；DEC-113 對 Phase 2 的 Sonnet 5.5＋Medium 已隨 Phase 2 結束）。<br>📌 **2026-10-30（Phase 3 步驟 0 完成後）（有意識的更新，不是漏刪；決策者 AI 總管（事實更新））**：~~**下一唯一安全接手點＝等客戶就 `docs/vnext/PHASE3_SHARED_COMPONENTS_WIREFRAME_2026-10-30.md` §6 裁示表（rev2 七題：D1a、D1b、D3、D5、D6、D8、D10）拍板；拍板後才進 Phase 3 步驟 1：新元件模組 `src/ui_v2/compact.py`（純字串、無 streamlit）實作＋`compact_css()`（與 `page_css()` 分開）＋`_ui_kit` 薄封裝／`Basis` 合併。** 拍板前**不寫 UI code**；客戶不裁示者一律維持現況（各題「不裁示預設」見該檔 §6；D3 無現況可維持）。站殼間距（原 D7）**先做內部量測（步驟 1 前置工作項，無需客戶）**，量到真值後才另送客戶；若核准須獨立 PR＋全 Gate（Gate §5），且 `app.py` 受 z60 守衛。動工前 `git fetch` 重確認 main；先在 floor 1.56 wheel 實跑 `st.segmented_control` 等 API（`P1R-FLOOR-156-API`），Model×Effort 依 Plan §1 與 DEC-084／DEC-106 開工前核對。~~（已被取代：客戶已裁示，見下一句 📌）<br>📌 **2026-10-30（客戶裁示後，DEC-115）（有意識的更新，不是漏刪；決策者 AI 總管（事實更新），依客戶 2026-10-30 裁示 DEC-115）**：~~**下一唯一安全接手點＝Phase 3 步驟 1：新純字串模組 `src/ui_v2/compact.py`（無 streamlit）實作＋`tokens.py` 加性新增（不改既有值，今天頁 `page_css()` byte-identical）＋golden／mutation（M1～M4、M7～M10、M14～M20）**~~（已被下方 📌 2026-10-30 取代；原文保留）<br>📌 **2026-10-30（Phase 3 完成後；有意識的更新，不是漏刪；決策者 AI 總管（事實更新））**：**下一唯一安全接手點＝Phase 4 步驟 0**：`git fetch` 以**當時 main** 重測（`_ui_kit.py` 是否受還原鏈／z60、`TestStreamlitFloorCompatibility`、Phase 3 工作樹內容是否已合併），並出 **📊 市場頁文字線框（W2、W3、W9）送客戶拍板**——寫任何 UI code 前必須先拍板。**並行待辦（不阻擋 Phase 4 線框）**：站殼間距（D7）客戶裁示——AI 總管推薦方案 R（見量測報告 §5），裁示前 `app.py`／`shell_nav4.py` 0 行改動。；其後步驟 2（`_ui_kit` 薄封裝，若需要且不動受鏈檔）→ 3（站殼間距只量測）→ 4（D8 切換鈕 floor 1.56 獨立 venv 實跑）→ 5（離線靜態預覽）——**完整拆分與每步 DoD＝Migration Plan §16**。動工前：`git fetch` 重確認 main；以當時 main 重測 `_ui_kit.py` 是否受還原鏈／z60 守衛；**客戶授權依已核准範圍靜默施工**，Sonnet 5.5＋Medium 若符合最低必要設定直接繼續（核對實際設定，不重複要求切換，DEC-084／106）；僅在真正 Customer Decision Gate、Model×Effort 必須切換、需客戶手動操作、完整 Phase 3 完成、context 不安全時停手。**邊界**：D1a／D1b 不改任何既有色值；D3 護欄實線粗框、不得第四套視覺語言；D5 迷你圖不顯示數字；D6 Primary 同高、Secondary 缺資料縮一行且不隱藏 Missing；D8 膠囊先實跑 1.56、不成立退回 A 不請示、不升 floor；D10 兩護欄各自獨立、來源進摺疊；站殼先量測、屬整體 layout 變更才送客戶；W2～W9 維持原 Gate。<br>📌 **2026-10-30（Phase 4 步驟 0 完成後；有意識的更新，不是漏刪；決策者 AI 總管（事實更新））**：~~上一個 📌「下一唯一安全接手點＝Phase 4 步驟 0（重測、出線框）」~~已完成（線框草稿已產出，docs-only）；**現行：下一唯一安全接手點＝等客戶就 `docs/vnext/PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30.md` §6 決策表（Q1～Q8：W9／`CV1-DR-12`、W2、W3、主圖形態、結論句位置、風險卡縮短行、手機第一屏）拍板**；拍板前**禁止**任何 Phase 4 UI code、動 `page_today.py`、提前做 Phase 5～7、提高 floor；Phase 3 結案（獨立 QA、PR CI、客戶實機點驗）仍待，不因本批改變。<br>📌 **2026-10-30（DEC-117 客戶裁示後；有意識的更新，不是漏刪；決策者 客戶（DEC-117）＋AI 總管〔事實更新〕）**：上句「等客戶拍板」已完成（Q1～Q8 已裁示）。**現行：下一唯一安全接手點＝等客戶回覆「改好了」（確認 Opus 5.5＋High 已切換）後，才開始 Phase 4 步驟 1 UI code（Migration Plan §20 P4-1）**；細節與禁止事項見第 0 節「📌 2026-10-30 DEC-117 客戶裁示落盤補註」。<br>📌 **2026-10-30（P4-1 實作後；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕）**：客戶已回覆「改好了」，P4-1 已在分支本地完成（未 push）；**現行下一唯一安全接手點**見第 0 節「📌 2026-10-30 Phase 4 P4-1 施工後補註」（總管判定 C1-10／C1-9 ＋兩組 QA → PR → 才開 P4-2）。<br>📌 **2026-10-31（P4-2 圖區實作後；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕）**：P4-2（📊 市場頁圖區：Primary 圖 A＋國際 small multiples＋圖 D compact＋圖 C 一行＋四段摺疊）已在分支 `ccr-c8ef17de-9tw7yt` 本地 commit（基底＝P4-1 main `4c1546b5`；未 push、未開 PR；中間批，Gate 未判）；逐條狀態＝線框 §10.8，PR 五段＝`docs/vnext/phase4_market/p4_2/PR_NOTES.md`。~~**現行下一唯一安全接手點＝P4-3（正式 Visual Fidelity Gate，Migration Plan §20）**~~（已被 📌 2026-10-31 P4-3 Gate 後取代：Gate 初判 ❌ FAIL；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕；見第 0 節「P4-3 Gate 後」列）：先兩組獨立 QA 複驗 P4-2 全批 → push／開 PR／CI 綠，再以 P4-2 量測（`p4_2/_measure_p4_2*.json`）判 Gate；登記待 Gate 呈現：圖 D 手機容器 723px、Primary 手機在第一屏下方（Q7 例外）、手機圖例單行被裁（`P1R-P4-PRIMARY-LEGEND-MOBILE`，P4-1 既有）。⛔ 不得在 P4-3 前標 Stage complete／結案 BACKLOG。⚠️ 全部為實作組單組產出，未經第二組驗證。 |
| tests／CI 已完成 | **PR #971 CI 雙綠**：Fast checks／Slow tests 皆 success（`3bbdaf0f` check-runs，2026-10-29 `gh api` 實查）。Phase 1 撰寫組沙箱實跑（歷史，單組）：base＝32688 passed／1 failed（已知環境失敗 `test_batch_z59` markdown_it）；本批＝32686 passed／3 failed——另兩項（`test_ui_state_model`、`test_vix_honesty`）失敗訊息指向工作目錄內未追蹤的 `.claude/worktrees/agent-*/` 副本，非本批改動。本 Safe Handoff 為 docs-only，另跑讀治理文件的測試（結果見 commit／回報）。<br>📌 2026-10-30（步驟 5）：全套 fast lane（`pytest tests`，預設 not slow）35366 passed／0 failed／46 skipped／185 deselected，938.9 s；main `59201e2` 的 Fast checks／Slow tests 以 `gh api` 實查皆 success；18 個臨時 mutation 全被抓到（`src/` 已還原）。 |
| tests／CI 尚未完成 | ~~Phase 2 尚未開始~~（已被 📌 2026-10-30 取代：步驟 0 已完成，~~步驟 1～5 尚未開始~~（已被取代：步驟 1、2＋4、5 已完成，步驟 3 已取消））（無待驗施工）；客戶實機點驗（NAV1／XV-ASOF／UI-M／UI-T）仍待。<br>~~本 PR 的 GitHub CI（Fast checks／Slow tests）；客戶實機點驗（NAV1／XV-ASOF／UI-M／UI-T）仍待~~（2026-10-29 Safe Handoff 有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；上一值刪除線保留）<br>📌 2026-10-30（步驟 5 與收尾）：slow lane（AppTest）本次沙箱未跑；1440／390 截圖 Gate 未做（Phase 2 以 byte golden＋QA 差分替代，限制見 Plan §15.3）；手機與 Streamlit Cloud 未驗；客戶實機點驗仍待。 |
| unresolved true Stop Gates | **無新 Gate**。既有 open 客戶項（不變）：過期價是否計入市值／損益／停利（XV 報告 G4）、`XV-OLDUI-AI-CARD-HOLD`、`FX-CANONICAL-GATE`、`FUND-REPO-XVIEW-AUDIT`、RS-2、AB-2b（`BP-DR-20`）、AB-4w（HI-5）、`RC-VISIBILITY`、舊 UI Removal Gate、台股／國際趨勢正式定義、EPS×PE、產業趨勢新來源、HI-1～HI-6、`CV1-DR-04`（`PROCESS.md` §1 vs 五檔讀序）、`UIT-S9-NO-POINTER`（非阻擋一句話）、客戶實機點驗；未來 Gate（本 phase 不問）：`P1R-GOOGLE-LOGIN-SIDEBAR-GATE`、`CV1-DR-12`（`CLAUDE.md` v3 §00「固定 3 欄」vs KPI／Hero 4 欄；Phase 4 線框 W9）；各 UI phase 線框待客戶拍板點 W1～W9（Presentation Contract §22；Phase 3～7 寫 UI code 前一律先出文字線框；含 **Phase 5「選股條件預設展開 vs 收合」`P1R-P5-WF-SCREEN-COND`**——DEC-107 預設展開維持有效，總管 2026-10-29 改判 R3）<br>📌 **2026-10-30（DEC-115）（有意識的更新，不是漏刪；決策者 AI 總管（事實更新），依客戶 2026-10-30 裁示 DEC-115）**：Phase 3 線框七題（D1a、D1b、D3、D5、D6、D8、D10）**已全部裁示，不再是待客戶項**；仍成立的未來 Gate：站殼間距內部量測後若屬整體 layout 變更〔Migration Plan §16 步驟 3〕；W2～W9 維持原 Gate、不提前處理。 |
| uncommitted／unpushed work | ~~**無**（Safe Handoff commit 一般 push 後工作樹乾淨；以 `git status`／`git fetch` 實查為準）~~已被 📌 2026-10-30 取代（有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；已被 📌 2026-10-30 取代，原文保留）。現行：**本批 Phase 2 收尾 docs（Migration Plan §15、HANDOFF、PROJECT_STATE）於 PR 前尚未 commit（工作樹有 docs diff，`src/`、`tests/` 0 diff）；PR merge 後為「無」**（以 `git status`／`git fetch` 實查為準）<br>~~無（Phase 1 commits 提交後一般 push）~~（2026-10-29 Safe Handoff 有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；上一值刪除線保留） |
| relevant evidence location | 見下方「新文件索引」；客戶原文＝`docs/DECISIONS.md` DEC-109（含同日前序 PCM 指示附錄）；#970 歷史＝**只在** PR #970 commit `06a7a3e5`（squash 後不進 main 歷史；冷啟動量測亦只在該處 → `P1R-COLD-START-BASELINE`） |
| recommended Model | **Phase 2＝Sonnet 5.5**（客戶 2026-10-29 於 Phase 1 後的最新指示，見 DEC-113）。📌 2026-10-30：**Phase 2 已結束，DEC-113 對 Phase 2 之降級（Sonnet 5.5＋Medium）隨之結束；Phase 3 依 Plan §1 與 DEC-084／DEC-106 開工時核對實際設定。**（有意識的註記，不是漏刪；決策者 AI 總管（事實更新））兩者並列、**以最新客戶指示為準**：~~DEC-110 R19／客戶 DEC-109 三十二原記載 Phase 2＝Opus 5.5~~（被 DEC-113 降級；R19 原文未改）。**只有**碰投資語意、Risk Cap、資料契約、重大架構衝突或其他 High Gate 才升回 **Opus 5.5**。Phase 3 起視情況（明確機械式 UI implementation 用 Sonnet 5.5；線框與規格判斷 Opus 5.5）；Phase 7＝**Opus 5.5**。 |
| recommended Effort | **Phase 2＝Medium**（最新客戶指示，DEC-113）；~~High（R19 原記載）~~；升 Opus 時配 **High**；Phase 7＝**High**。 |
| 殘留風險 | Phase 1 文件皆單組撰寫、未經第二組驗證：見 `docs/PROJECT_STATE.md` §48「限制」、Presentation Contract §21、Decision Digest Contract §2.1；量化上限為依 blueprint 的建議值；手機實機、Streamlit Cloud、1.56 floor 未驗 |
| last checkpoint timestamp | 2026-10-29（Phase 1 已合併；Safe Handoff／Session Close 完成）<br>~~2026-10-29（Phase 1 撰寫完成；第二輪 QA 修正後）~~（2026-10-29 Safe Handoff 有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；上一值刪除線保留）<br>~~📌 2026-10-30（Phase 2 步驟 0 完成，待本 PR merge）~~（已被取代，見下一句）<br>2026-10-30（Phase 2 步驟 5 與收尾完成）（有意識的更新，不是漏刪；決策者 AI 總管（事實更新））。<br>2026-10-30（Phase 3 步驟 0 客戶裁示落盤，DEC-115；docs-only）（有意識的更新，不是漏刪；決策者 AI 總管（事實更新），依客戶 2026-10-30 裁示 DEC-115）。 |
| **新 UI 規則核心（必讀；精簡索引，全文見出處）** | 規範全文＝`docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md`（含 §22）、`docs/governance/UI_VISUAL_FIDELITY_GATE.md`、`PROJECT_RULES.md` 第 24～26 節、客戶原文 `docs/DECISIONS.md` DEC-109。要點（逐條保留）：<br>• **簡化 UI 不簡化判斷**（Presentation Simplification must never reduce AI Decision Context）<br>• **圖表 > 數字 > 短句 > 長文字**（Visual Priority ≠ Visual Quantity）<br>• **每頁 Visual Budget**：1 Primary＋≤2–3 Secondary<br>• **第一屏五問**（契約 §3；出處為準）<br>• **L1／L2／L3 三層**資訊（第一屏／展開／明細）<br>• **Missing 不得偽裝 0／中性／HOLD／安全**（`CLAUDE.md` §1；DEC-101）<br>• **Data View ≠ Decision Context ≠ AI Output**<br>• **One AI Brain, Many Data Views**（`docs/vnext/ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md`）<br>• **UI Stage 必須 CI 綠＋Visual Fidelity PASS**；**desktop＋390px mobile 驗收**<br>• **W1～W9 未拍板項不得自行決定**：見 Presentation Contract §22、BACKLOG `P1R-P3-WF-CUSTOMER-COLORS`／`P1R-P4-WF-POINTS`／`P1R-WF-FOLD-LABEL`／`P1R-P5-WF-SCREEN-COND`／`P1R-P5-WF-POINTS`／`P1R-P6-WF-TWO-SCALES`／`P1R-P7-WF-CHANGE-RANK`、`CV1-DR-12`（W9） |
| 本對話 Phase 2 預備實測（**未完成、單組、未經第二組驗證**） | 前一對話在 Phase 2 步驟 0 做了 H1～H35＋T1～T26 的預備實測（AST 窮舉＋抽查；未跑 pytest），濃縮存於 `docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md` **§11**。⚠️ 只當線索，**下一個 session 必須以當時 main 重測**；不是 Phase 2 實作，~~也不構成步驟 0 完成~~（已被 📌 2026-10-30 取代：步驟 0 已於 2026-10-30 完成，見 Migration Plan §12）。BACKLOG 去處＝`P1R-PHASE2-HELPER-TEST-MIGRATION` |

**必讀順序（新 session；`PROJECT_RULES.md` 第 25 節規範軸＋第 15 節）**：`git fetch` 實查 GitHub → `CLAUDE.md` → `PROCESS.md` → `PROJECT_RULES.md`（尤其第 3、15、18、20、23、24、25、26 節）＋`docs/governance/*` → `docs/DECISIONS.md`（DEC-109／110 起，往回看取代鏈第 5 節）→ 正式契約（下方索引）→ `docs/PROJECT_STATE.md`（§48）→ `docs/BACKLOG.md`（§5.1.16）→ 本索引。

**禁止事項（摘要；以出處原文為準）**：⛔ 依 #970／DEC-108 線框或較早 Presentation／Wireframe 規則施工（DEC-109 一）；⛔ 把 #970 當 production baseline；⛔ **不得在 Decision Digest contract 未凍結前直接開始寫新的 LLM prompt／glue**（客戶原文 DEC-109 三十一）——本批已凍結最低概念契約，但 **v2 schema（A1～A7）定案前不寫新 prompt／glue**；⛔ 每個 UI phase 未出文字線框、未經客戶拍板前寫 UI code（`CLAUDE.md` v3 §03-2 ①）；⛔ 新資料源／投資公式／趨勢公式／Risk Cap 算法／EPS×PE production rule／投資語意變更（DEC-109 三十）；⛔ 自行增刪頂層頁（DEC-109 十）；⛔ 改 `CLAUDE.md`／`PROCESS.md`（無授權）；⛔ 改刪舊 UI（DEC-019／020）；⛔ 過程訊息（Hard Output Gate，DEC-104）；⛔ force push。

**新文件索引**：
- Presentation Contract＋Visual SSOT：`docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md`
- Visual Fidelity Gate：`docs/governance/UI_VISUAL_FIDELITY_GATE.md`（工具 `tools/visual_fidelity/`）
- Visual gap audit（baseline）：`docs/vnext/visual_fidelity/phase1_baseline/VISUAL_GAP_AUDIT_2026-10-29.md`
- Decision Digest Contract：`docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md`
- One AI Brain Boundary：`docs/vnext/ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md`
- Supersede Map（含 #970 處置、清理 A／B／C／D、刪除 vs 保留、程式碼內客戶裁示盤點）：`docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md`
- Migration Plan（Phase 2→7）：`docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md`
- 治理：`PROJECT_RULES.md` 第 24～26 節；`.github/PULL_REQUEST_TEMPLATE.md`「Visual Fidelity Gate」段
- 現況知識：`docs/PROJECT_STATE.md` §48；未完成工作：`docs/BACKLOG.md` §5.1.16

⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本索引由 Phase 1 撰寫組單組撰寫，未經第二組驗證；「無新 Gate」「既有 open 客戶項」清單依 BACKLOG／舊 Checkpoint 轉錄，非窮舉。

<!-- HANDOFF_HISTORY_INDEX:BEGIN lines=178-297 archive=docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md -->
- 📦 **路徑索引（2026-11-12，DEC-173 Q1；只搬不改）**：原 L178–L297 已逐字搬至 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md`（分冊 L124–L243）。
  - **「HANDOFF 第 0 節」（`PROJECT_RULES.md` §15-5F／§15-6／§20 等引用）的新位置**：本檔 `## 0.` 標題、前言指標與「Resume Checkpoint 索引」（15 欄，原 L124–L176）**原位保留**；其下必讀規則四條＋交接治理教訓（原 L298–L325）**原位保留**；第 0 節其餘舊段（原 L178–L297、原 L327–L642）在分冊。
  - 原 L178–L237 2026-10-30／31 補註表（D7=B、Phase 4 步驟 0、DEC-117、P4-1 以後）；原 L239–L291「Resume Checkpoint（DEC-086）— ⛔ HISTORICAL」；原 L293–L296 AB-1／AB-2a／AB-4r 條目。
  - 各段標題（節錄；刪除線內文與 markdown 標記略去，原文以分冊為準）：
    - 原 L178 → 分冊 L124：📌 2026-10-30 站殼間距 D7=B 施工補註（ 已過時：D7=B 已隨 #981 …
    - 原 L190 → 分冊 L136：📌 2026-10-30 Phase 4 步驟 0 完成補註（ 已由下一段「DEC-117 …
    - 原 L202 → 分冊 L148：📌 2026-10-30 DEC-117 客戶裁示落盤補註（ 已由下一段「Phase 4 P…
    - 原 L216 → 分冊 L162：📌 2026-10-30 Phase 4 P4-1 施工後補註（現行；與上表及上兩段衝突處以…
    - 原 L239 → 分冊 L185：📌 Resume Checkpoint（DEC-086）— ⛔ HISTORICAL（202…
<!-- HANDOFF_HISTORY_INDEX:END -->

### ⛔ 禁止事件回音（客戶 2026-10-28 指示；決策者＝客戶；append-only）

> 來源：客戶 2026-10-28 指示（經總管轉交之要點，非逐字全文）。正式規則本文落在 `PROJECT_RULES.md` 第 3 節（Silent Autonomous Cruise）；本段為接手者的顯著提醒，兩處衝突時以 `PROJECT_RULES.md` 為準。

- **每個 Stage 只允許一次最終回報。**
- ready／merge／CI／workflow／subscription 等事件，若只是**確認既有結果**，一律**靜默**。
- 不得回覆「只是通知」「沒有新事項」「與上一則一致」；不得重複下一步、不得重複 Model×Effort。
- **沒有新的客戶行動需求就保持沉默。**
- **只在以下情況出聲**：(1) 真正需要客戶裁示；(2) Model×Effort 需切換且尚未通知；(3) 需客戶手動操作；(4) 整批完成；(5) context／token 不安全需交接；(6) 真實錯誤或 GitHub 狀態衝突。
- 📌 **2026-10-28 客戶第二次指示「零過程訊息」（決策者＝客戶；append-only）**：**Process chatter = governance violation.** 出聲情況收緊為 5 種（🔴 需客戶裁示／🟡 Model×Effort 需切換且未通知／🟡 需客戶手動操作／🟢 整個 Stage 完整完成／🟡 context／token 不安全需交接）；Stage 完成標準、最終回報 ≤5 行格式與完整禁止清單見 `PROJECT_RULES.md` 第 3 節「零過程訊息」條（以該條為準，取代上列 (6)）。
- 📌 **2026-10-28 客戶指示「Context Lifecycle／/compact 規則」（決策者＝客戶；append-only；來源：經總管轉交之要點，非逐字全文）**：安全 checkpoint 可**主動 `/compact`、不需先詢問客戶**；時機＝Stage 完整結束且正式文件已落盤後／context 明顯變長或重複增加／出現語言漂移、規則遺漏、重複回報等污染跡象／進入下一個大型 Stage 前；**不高頻、仍有大量未落盤 WIP 時不得草率壓縮**；`/compact` 前須確認 DECISIONS／BACKLOG／PROJECT_STATE／HANDOFF（Resume Checkpoint）／必要 spec 已落盤；**GitHub／repo 為 SSOT，compact summary 不得成為新 SSOT**；compact 後仍規則漂移或狀態不確定 → 回報「🟡 建議換新對話」；`/compact` 屬內部維護，**不向客戶回報**（與「零過程訊息」併存）。正式規則本文見 `PROJECT_RULES.md` 第 3 節「Context Lifecycle／/compact 規則」條（與第 22 節併讀取較嚴者；以該條為準）。

### 📌 必讀規則：Hard Output Gate（客戶 2026-10-29，DEC-104；append-only）

- 任何 user-visible 訊息送出前先過 `PROJECT_RULES.md` **第 3 節「小節：Hard Output Gate」**（客戶原文逐字，以該處為準）：只有 5 類可輸出，其餘一律 SILENT；harness 停止鉤子／久未收到訊息提示／背景任務通知**不是**出聲理由（見 BACKLOG `GOV-CHATTER-2026-10-29`）。

### 📌 必讀規則：Model×Effort 已符合時靜默繼續（客戶 2026-10-29，DEC-106；重申 DEC-084；append-only）

- 每個 Stage 起點先比對「目前實際 Model／Effort」與「下一 Stage 最低需求」：**已符合 → 靜默繼續，不得停手要求客戶切換或回覆「改好了」**；**不符才停**（`PROJECT_RULES.md` 第 18 節；見 BACKLOG `GOV-DEC084-REDUNDANT-STOP-2026-10-29`）。

### 📌 必讀規則：Scope Inflation Guard（客戶 2026-10-28，DEC-103；append-only）

- 開任何 Stage 前先讀 `PROJECT_RULES.md` **第 23 節**：新發現分 P0／P1／P2；P0 可插隊、P1 依主線排程、**P2 只能登記不得插隊**；不阻擋主線者只進 BACKLOG、不開新 Stage；不取代既有安全 Gate（以該節原文為準）。

**交接治理教訓（2026-10-27，AI 總管；單組，未獨立驗證）**：
- `CLAUDE.md` §-2：總管**所有寫入都派子代理**並自己複驗回報；子代理也會錯、過度自信（AB-1 WIP 即為未驗證草稿）。
- 沙箱缺 `markdown_it`：fast lane 須 deselect 1 項（待 CI 實跑）。
- 推送只用一般 push（不 force；分類器會拒絕 force）；遠端分支可能在 squash merge 後殘留舊歷史 → 以 `git merge -s ours origin/<branch>` 對齊，不用 force。

<!-- HANDOFF_HISTORY_INDEX:BEGIN lines=327-1400 archive=docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md -->
- 📦 **路徑索引（2026-11-12，DEC-173 Q1；只搬不改）**：原 L327–L1400 已逐字搬至 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md`（分冊 L248–L1321）。
  - 含：原 L327–L335 2026-10-22 短版狀態表；原 L336–L642 2026-10-23～10-25 append 段；原 L643 起「以下為歷史紀錄」與 §1–§6（§6 內含 2026-11-02～11-04 各 Safe Handoff 條目，DEC-124～DEC-133，原 L1031、L1047 等）；原 L1108 起 11-05～11-10 補註與接手點。
  - 各段標題（節錄；刪除線內文與 markdown 標記略去，原文以分冊為準）：
    - 原 L336 → 分冊 L257：📌 2026-10-23 安全收尾（append-only；客戶要求本對話進入安全收尾模式；…
    - 原 L349 → 分冊 L270：📌 2026-10-23 批 A＋1' 安全段落收尾（append-only； 已過時，見下…
    - 原 L363 → 分冊 L284：📌 2026-10-23 GitHub 交接 Freeze 版（append-only； 已…
    - 原 L383 → 分冊 L304：📌 2026-10-24 #910 合併後（append-only； 已過時，見下方「DEC…
    - 原 L402 → 分冊 L323：📌 2026-10-24 DEC-077 裁示後（append-only； 已過時，見下方「…
    - 原 L421 → 分冊 L342：📌 2026-10-24 C1 合併後（append-only； 已由下方「C2 Gate …
    - 原 L447 → 分冊 L368：📌 2026-10-24 C2 Gate 研究後（append-only； 已由下方「C2 …
    - 原 L462 → 分冊 L383：📌 2026-10-24 C2 裁示後（append-only； 已過時，見下方「2026-…
    - 原 L478 → 分冊 L399：📌 current handoff（2026-10-24 Safe Checkpoint）（…
    - 原 L494 → 分冊 L415：📌 current handoff（2026-10-24 C2a-2 後）（append-o…
    - 原 L512 → 分冊 L433：📌 current handoff（2026-10-24 大盤 Gate 後）（append…
    - 原 L530 → 分冊 L451：📌 current handoff（2026-10-25 大盤頁實作批）（append-on…
    - 原 L643 → 分冊 L564：以下為歷史紀錄與細節（非現況快照；現況以第 0 節與 GitHub 為準）
    - 原 L647 → 分冊 L568：1. 現況（ 量測：2026-10-22T15:00Z，origin/main＝d3a3e6…
    - 原 L669 → 分冊 L590：2. 最近完成（皆已合併、main CI success）
    - 原 L706 → 分冊 L627：3. Blocker／Decision Required（只列指標，細節見 BACKLOG）
    - 原 L726 → 分冊 L647：4. 下一安全接手點
    - 原 L757 → 分冊 L678：5. 新對話 takeover
    - 原 L767 → 分冊 L688：6. 本檔沒查證的部分
    - 原 L1108 → 分冊 L1029：補註（2026-11-05｜#1020 視覺完善 Batch 1 獨立 QA）
    - 原 L1114 → 分冊 L1035：補註（2026-11-05｜💼 W-11 批 1 版面空槽，ui2/hold-w11-bat…
    - 原 L1119 → 分冊 L1040：補註（2026-11-07｜P0-FWD-STORE-FAILCLOSED：總經前進式驗證帳…
    - 原 L1126 → 分冊 L1047：補註（2026-11-07｜P0-FWD-STORE-ATOMIC-WRITE：帳本寫入改原…
    - 原 L1132 → 分冊 L1053：2026-11-07｜GitHub 獨立治理可恢復接手點（本段優先於上方歷史 Handoff…
    - 原 L1148 → 分冊 L1069：2026-11-07 17:10 後續更正｜#1049 已合併（優先於上一個 checkpo…
    - 原 L1157 → 分冊 L1078：Safe Handoff（2026-11-07 晚｜New UI2 Batch 3 五頁頂部…
    - 原 L1174 → 分冊 L1095：2026-11-08｜DEC-153 客戶新裁示接手點（合併本 docs PR 後生效；Gi…
    - 原 L1189 → 分冊 L1110：2026-11-08｜DEC-153 執行結果接手點（AI 總管事實更新；GitHub 實況…
    - 原 L1202 → 分冊 L1123：Safe Handoff｜DEC-154 2026-11-08 客戶四項續行核准（（2026…
    - 原 L1218 → 分冊 L1139：2026-11-08｜DEC-154 執行結果接手點（AI 總管事實更新；GitHub 實況…
    - 原 L1229 → 分冊 L1150：2026-11-09 接手點補註｜#1088 已合併（DEC-155；只追加）
    - 原 L1237 → 分冊 L1158：2026-11-09｜New UI2 TWII 日 K 設計決策接手點（DEC-156，客戶…
    - 原 L1248 → 分冊 L1169：2026-11-09 接手點補註｜Issue #1099 PR-1 #1100 已合併、PR…
    - 原 L1258 → 分冊 L1179：2026-11-09 接手點補註｜Issue #1099 PR-1 #1100＋PR-2 #…
    - 原 L1273 → 分冊 L1194：2026-11-10 接手點補註｜資料 PR #1104／#1103 已合併、#1105 已…
    - 原 L1290 → 分冊 L1211：2026-11-10 接手點補註｜Issue #1108 市場頁順序 B（只追加；DEC-1…
    - 原 L1300 → 分冊 L1221：2026-11-10 合併後同步補註｜Issue #1108 順序 B 已合併（只追加；取代…
    - 原 L1312 → 分冊 L1233：2026-11-10 接手點補註｜Issue #1110 Secrets／API 唯讀驗證：…
    - 原 L1323 → 分冊 L1244：2026-11-10 接手點補註｜Issue #1113 舊診斷頁／側欄資安最小修補（只追加…
    - 原 L1334 → 分冊 L1255：2026-11-10 接手點補註｜PR #1114（Issue #1113，D6）已合併（只…
<!-- HANDOFF_HISTORY_INDEX:END -->


## 最新接手點（2026-11-10 晚，Issue #1121；只追加）

- **基準**：main `f4d86b4f`（`f4d86b4f9b45832cb784895342cecd5f9305c48b`）。cron 會推進 main，接手前先做 LIVE GitHub Verification Gate。
- **本批**：docs-only PR（**PR #1122，Draft；合併後補一行結果**）。內容＝三份新文件 `docs/vnext/NEWUI2_CAPMAP_3COL_2026-11-10.md`、`docs/vnext/NEWUI2_CUTOVER_GAP_MATRIX_2026-11-10.md`、`docs/vnext/NEWUI2_EPS_AND_DIGEST_ONEBRAIN_RESEARCH_2026-11-10.md`，加上 DECISIONS（DEC-158）／BACKLOG／本檔的純追加。三份文件皆單組產出、未經第二組獨立複驗；客戶裁示為轉錄，非逐字、非 QA PASS。
- **不可動項**：D1 僅定 FRED `DGS10` 口徑，不得實作 adapter／來源／排程／UI 接線；VIX、利差、PMI 維持空槽；不新增 cron；EPS 僅唯讀研究；Digest F／OneBrain G 暫列切換前置，OneBrain runtime 不動；#1119 HOLD；不 cutover、不刪碼。ETF Managers 2026-11-16 20:00 UTC 真實 Actions PR 與 Cloud UI2 仍 **NOT VERIFIED**。
- **下一個唯一安全工作**：等 QA／合併後，由客戶裁示下一階段；無裁示前不動工（`CLAUDE.md` §-1）。
- **舊快照說明**：前段快照（如 2026-11-09 的「Open PR 0」、#1038 Draft 等）已被本段取代，**僅為歷史紀錄，未刪除**。

### Issue #1121 合併後同步（2026-11-10）
- PR #1122 已 squash 合併，main `e43482188145b9dc4d75786dd32c151013f41a09`；取代前一段「PR #1122 Draft」措辭。同 head `4945c9d1` 原生 CI 5 項全 success（pytest fast、AppTest slow、ui2-browser 1.56.0／1.59.2、gate）；非作者獨立 QA PASS（14 項抽查，3 項 minor 措辭已修於 `4945c9d1`）；mergeable clean、0 未解決討論串。
- 仍 **NOT VERIFIED**：Cloud UI2、真機、ETF Managers 2026-11-16 20:00 UTC 真實 Actions PR。
- **下一個唯一安全工作**：等客戶裁示（EPS Gate E-0~E-6、Digest F／G 方案 P-1~P-4、D1 實作授權）；#1119 HOLD。


## 最新接手點（2026-11-11，Issue #1127 P-4；只追加）

- **基準**：main `5f98154c`（`5f98154c5bf4c4df3279855298e7778427420403`，Issue #1127 授權時的 main）。cron 會推進 main，接手前先做 LIVE GitHub Verification Gate。
- **本批**：P-4 S7/S8 程式＋文件同步的 PR（**PR 號待補**；分支 `ccr-588f897e-7wzywe`；原版 `7cfeb31d`，獨立 QA 共三輪皆發現問題並回修：第一、二輪 `571302e1`／`95bcf809`，第三輪 `50da5574`／`8dc1ddf0`）。授權範圍轉錄自 Issue #1127（非逐字）；設計決定見 `docs/DECISIONS.md` DEC-159（採側車、不升 Digest v2；設計決定為 AI 總管內部技術決策，非客戶裁示）。
- **第三輪重點（DEC-159 第 3、4 點）**：builder 每個站內掃描列必歸入互斥窮盡分類（分割恆等式 `rows_total == 候選 + non_action + not_held + excluded_invalid + unrecognized + unmatched + non_mapping`；`duplicate_rows` 為疊加計數）。`DigestCoverage` 欄位：`station_rows_unmatched`（由 `actions_unmatched_dropped` 更名，未發布）、`station_non_mapping_rows`、`holdings_non_mapping_rows`、`unrecognized_action_code_rows`、`duplicate_station_ticker_rows`、`holdings_without_station_row`、`digest_holdings_available`／`digest_actions_available`。`is_complete` 要求九個計數全 0＋兩旗標 True＋四段 used，**不判斷新鮮度**。
- **新檔／改動清單**：
  - 新增 `shared/decision_digest_coverage.py`（L0；`DigestCoverage`，`digest_coverage.v1`，尚未發布、三輪回修皆無升版）
  - 新增 `src/services/decision_digest_assembly.py`（L3；`assemble_digest`、`AssembledDigest`，建構時交叉驗證 coverage 與 digest）
  - 修改 `src/services/decision_digest_builder.py`（純加性：`plan_action_selection`、`ActionSelectionPlan`、共用掃描 `_scan_action_rows`／`_ScanResult`；24000 組隨機輸入與舊版逐位元相同）
  - 新增 `tests/test_decision_digest_coverage.py`、`tests/test_decision_digest_assembly.py`（合計 364 條）
  - 文件純追加：`docs/DECISIONS.md`（DEC-159）、`docs/BACKLOG.md`、本檔
- **測試狀態（據實）**：作者自跑 1361 passed（digest 相關＋c3 分層）。**獨立 QA 第四輪與原生 CI 結果待補**；三輪 QA 皆為發現問題非 PASS；尚未合併，不得寫成已通過。
- **不可動項**：Open 資料 PR **#1124（macro-history）、#1125（sector-flow）、#1126（macro-forward-test）禁止順手合併／改寫／rebase**（#1126 歷史曾有 PIT 失敗契約，須獨立驗證）；**#1119 維持 HOLD**；Digest v1 凍結契約（`SCHEMA_VERSION`／`MAX_ACTIONS`／列舉／既有 `shared/decision_digest*.py`）不得動；不建 production caller；不碰舊 UI、正式路由、Actions、Secrets、Risk Cap、D1～D5、EPS、OneBrain。
- **已知限制**：裸 `DecisionDigest` v1 仍無 omitted 欄位，完整性只在 coverage 側車；嵌入 Digest 屬未來 v2 Decision Gate。`AssembledDigest` 不防惡意偽造（total／omitted／excluded／unmatched 等在 digest 看不到）；零行動／`station_rows=[]` 一律 `is_complete=False`（v1 無法區分「沒事做」與「判不出來」，需 Digest v2）；證據被拒用時 `station_rows` 列層級型別錯誤不 fail loud；ticker 精確字串比對；`held` 缺失視為 not_held（與 builder 既有行為相同）；premium／cruise 在 builder 內為字串複本（有一致性測試）；risk_cap 舊快照仍 complete、`as_of` 如實揭露（`is_complete` 不判斷新鮮度）；無 production caller。側車的 `excluded_invalid_rows` 與契約 §6 A7、`segments` 與 A6／A1 語意部分重疊，A6／A7 仍未完成，不得形成第二個 SSOT。P-4 完成 ≠ Stage F／C1～C7 通過；Cloud UI2、ETF Managers 2026-11-16 20:00 UTC 首次排程、資料 PR #1124～#1126 PIT 皆 **NOT VERIFIED**。
- **下一個唯一安全工作**：等客戶裁示（P-1 其餘、v2 嵌入式 coverage 的 Decision Gate）；無裁示前不動工（`CLAUDE.md` §-1）。

- **2026-11-11｜P-4 合併後更新（只追加；以本段取代上一批「PR 號待補／獨立 QA 第四輪與原生 CI 待補／尚未合併」舊句之效力——有意識的更新，舊句保留不改）**：PR **#1128 已 squash 合併**，main `720ccbed420da1e7c6066d81c20ce71698f4bf1d`（head `05d2733c`）；同 head 原生 CI 5 項全 success（Fast pytest、AppTest slow、ui2-browser 1.56.0／1.59.2、gate），mergeability clean、0 未解決討論串。獨立非作者 QA 共四輪（前三輪發現問題並回修；第四輪 PASS：約 7 萬組 oracle、3 萬組新舊 builder 逐位元比對、25 突變 0 存活，無 blocker／major）。
- **據實揭露**：最後一個 commit（`tests/test_d3e_mrev_fail_cache.py` 的 `frozen_now` 補釘 `tw_now`，6 行，日期相依測試缺陷，2026-11-11 起 main 紅燈；`TEST-DATE-DEP-1` 已登記）僅由作者端驗證＋突變，**未另送獨立 QA**。
- **仍 NOT VERIFIED**：Cloud UI2、真機、ETF Managers 2026-11-16 20:00 UTC 首次真實 Actions PR、資料 PR #1124～#1126（PIT）。P-4 完成 ≠ Stage F ≠ C1～C7 通過；`assemble_digest` 無 production caller。#1119 維持 HOLD。
- **下一個唯一安全工作**：等客戶裁示（P-1 其餘、v2 嵌入式 coverage Decision Gate、EPS Gate、D1 實作授權）；無裁示前不動工（`CLAUDE.md` §-1）。

- **最新接手點（2026-11-11，Issue #1130；只追加；不改既有段落；依據 `docs/DECISIONS.md` DEC-160 轉錄，非客戶逐字、非 QA PASS）**：
  - **基準**：main `8df4797d898f7002ff6c55a3fa6c3b2371a93720`；**本批 PR 號待補**。本批為 docs-only 研究：新增 `docs/vnext/STAGE_F_HEADLESS_INPUT_AND_STALE_SEMANTICS_2026-11-11.md`（headless 輸入／授權矩陣、A2 stale 語意、Digest v2 B＋M1 方向、Gate G-F1～G-F6）；單組撰寫，未經第二組複驗。
  - **不可動項**：Open 資料 PR **#1124／#1125／#1126** 禁止順手合併／改寫／rebase；**#1119 維持 HOLD**；OneBrain、EPS、D1～D5、UI2 切換、舊 UI 刪除一律未授權；Digest v1 凍結契約未動、無 production caller。
  - **仍 NOT VERIFIED**：Cloud UI2、真機、ETF Managers 2026-11-16 20:00 UTC 首次真實 Actions PR、資料 PR #1124～#1126（PIT）。P-4 完成 ≠ Stage F ≠ C1～C7 通過。
  - **`TEST-DATE-DEP-1` 結果（作者端驗證，獨立 QA 待補；細節見 `docs/DECISIONS.md` DEC-160「裁示 4 執行結果補記」）**：測試端 +8／-1 於 `tests/test_c1_observability.py`（`os.utime` 對齊 pickle mtime）＋新增 `tests/test_date_dep_boundaries.py`（51 測試：公告延遲＝次月 11 日、當日／前一日、跨月含 2028-02-29、跨年；`no_real_clock` 證明只用注入 `as_of`；窄範圍時鐘模擬 2026-12-15／2027-01-15 皆綠）；未改正式程式。⚠️ **更正**：先前（Issue #1127 研究留言、先前 QA）稱 `TestPcrSource::test_old_pickle_returned_as_is` 於 2026-12-01 起轉紅——複查在真實時鐘與多種偽裝至 2026-11-11～2027-01-15 皆通過，**無真實日期相依**；紅燈最可能來自只偽裝 `time.time`、檔案 mtime 仍為真實時間的不一致偽裝（推測，未核對當時偽裝）；`os.utime` 僅為防禦性加固。已確認的日期相依測試只有 `test_d3e_mrev_fail_cache`（#1128 已補釘；`frozen_now` 只釘 `as_of`＝2026-09-28，延遲常數突變 0／9／11／12 使邊界測試紅 26／19／20／20 項、契約 grace 0→7 紅 7 項）。**NOT VERIFIED**：真正 libfaketime／freezegun（環境無）、未掃全 repo、其他測試檔日期相依未掃、單組驗證。
  - **下一個唯一安全工作**：等客戶裁示 G-F1～G-F6；無裁示前不動工（`CLAUDE.md` §-1）。

- **最新接手點（2026-11-11，Issue #1132；只追加；不改既有段落；依據 `docs/DECISIONS.md` DEC-161 轉錄，非客戶逐字、非 QA PASS）**：
  - **基準**：main `3cf13a02`；**本批 PR 號待補**。本批為 docs-only：新增 `docs/vnext/STAGE_F_GF1_HEADLESS_MARKET_CONTRACT_2026-11-11.md`（G-F1 方案 A：契約矩陣、缺口、對前份研究的二次核對更正、下一階段三方案）；兩位獨立 agent 二次核對，仍屬 agent 產出、未經人工複驗。
  - **更正（追加，舊段不改）**：上一段「Issue #1130」接手點寫「本批 PR 號待補」；實際 PR 為 **#1131**，已於 main `3cf13a02` squash 合併（同 head `07ad5909` 原生 CI 5 項 success，兩位獨立 QA PASS）。
  - **不可動項**：資料 PR #1124／#1125／#1126（PIT）；#1119 HOLD；D1～D5；OneBrain；Risk Cap；廣度旗標 `BREADTH_PROXY_SCORING_ENABLED`；runtime 接線；P-1／Digest v2／production caller。
  - **仍 NOT VERIFIED**：各上游授權／再散布、Cloud UI2、真機、ETF Managers 2026-11-16 20:00 UTC 首次排程。完成本批 ≠ Stage F ≠ C1～C7 通過。
  - **下一個唯一安全工作**：等客戶裁示（方案 2 前置問題、G-F2～G-F6）；無裁示前不動工（`CLAUDE.md` §-1）。

- **最新接手點（2026-11-11，Issue #1134；只追加；不改既有段落；依據 `docs/DECISIONS.md` DEC-162 轉錄，非客戶逐字、非 QA PASS）**：
  - **基準**：main `a6155dde`；**本批 PR 號待補**。本批為 docs-only：新增 `docs/vnext/NEWUI2_MARKET_CHIPS_OLD_UI_FIRST_MAPPING_2026-11-11.md`（三大法人／融資／板塊資金的 Old → Legacy New → UI2 能力對照、接線提案、A1／A2／A3 比較）；DECISIONS 追加 DEC-162；BACKLOG 追加。未改任何程式或測試。
  - **更正（追加，舊段不改）**：上一段「Issue #1132」接手點寫「本批 PR 號待補」；實際 PR 為 **#1133**，已於 main `a6155dde` squash 合併（同 head `90c33509` 原生 CI 5 項 success；兩輪獨立 QA：第一輪 FAIL 已修，第二位複驗 PASS）。
  - **不可動項**：資料 PR #1124～#1126（PIT）；#1119 HOLD；D1～D5；OneBrain；Risk Cap；廣度旗標；runtime 接線；P-1／v2／caller；UI2 切換。
  - **下一個唯一安全工作**：等客戶裁示（線框位置、inst 僅外資、正負值色彩語意是否沿用（現碼負值紅）、是否納融資）；無裁示前不動工（`CLAUDE.md` §-1）。

## 最新接手點（2026-11-11，Issue #1136；只追加）

- **基準**：main `5eef8863`。cron 會推進 main，接手前先做 LIVE GitHub Verification Gate。
- **本批**：docs-only 文字線框草案 PR（**PR 號待補**；分支 `ccr-588f897e-7wzywe`）。授權範圍轉錄自 Issue #1136（非逐字）；見 `docs/DECISIONS.md` DEC-163、`docs/vnext/NEWUI2_MARKET_CAPITAL_FLOW_TEXT_WIREFRAME_2026-11-11.md`（草案，待客戶正式拍板；**不是經驗證畫面，真機／Cloud 未驗**）。
- **更正（追加，舊段不改）**：上一段「Issue #1134」接手點寫「本批 PR 號待補」；實際 PR 為 **#1135**，已於 main `5eef8863` squash 合併（同 head `ba99bca5` 原生 CI 5 項 success、獨立 QA PASS）。
- **不可動項**：資料 PR #1124～#1126（PIT）；#1119 HOLD；D1～D5；OneBrain；Risk Cap；廣度旗標；runtime 接線；P-1／v2／caller；UI2 切換；A2 步驟 2 程式施工。
- **下一個唯一安全工作**：等客戶對線框正式拍板（G-1～G-10）；無裁示前不動工（`CLAUDE.md` §-1）。

## 最新接手點（2026-11-11，Issue #1138；只追加；不改既有段落；依據 Issue #1138 轉錄，非客戶逐字、非 QA PASS）

- **基準**：main `838f667a`（#1137 squash 合併後）。cron 會推進 main，接手前先做 LIVE GitHub Verification Gate。
- **本批**：Issue #1138 雙線 tests-only／docs 追加的 PR（**PR 號待補**；分支 `ccr-588f897e-7wzywe`）。獨立 QA 與原生 CI：**待補**（NOT VERIFIED，不得寫成已通過）。
- **兩條線各自的 tests-only 檔（FACT，收集數已實測；production 0 改動）**：
  - Digest 不變性線：`tests/test_decision_digest_invariants_guard.py`（31 測試；C1 UI 狀態不變性、C2 全域 0 production caller〔Gate 開啟時須同步更新〕、C3 L0 動態 import 閉包）。
  - UI2 市場頁渲染線：`tests/test_ui2_market_render_guards_extra.py`（27 測試；無值卡片 blank＋『—』、真 0 vs missing、核心卡 id 多／少／顛倒／重複、kbar 狀態禁詞）。
- **production 發現**：審計發現的設計限制／疑似缺陷（a～i）已登記 `docs/BACKLOG.md`『Issue #1138 雙線結果』，**均未修、均待 Gate**，不屬 tests-only。審計為單組，未經第二組驗證。
- **#1137 已合併事實（FACT）**：squash 於 main `838f667a`；同 head `277292ea` 原生 CI 5 項 success。
- **不可動項**：資料 PR #1124～#1126（PIT）；#1119 HOLD；D1～D5；Digest v2／Stage G；舊 UI。
- **NOT VERIFIED**：瀏覽器／viewport 測試（沙箱無 Playwright）；`DataStatus` 六態與 schema candidate 五態措辭不一致未裁決。
- **下一個唯一安全工作**：等客戶對 G 表（見 Issue #1138 留言）裁示；無裁示前不動工（`CLAUDE.md` §-1）。

## 最新接手點（2026-11-11，Issue #1140；只追加；不改既有段落；依據 `docs/DECISIONS.md` DEC-164 轉錄，非客戶逐字、非 QA PASS）

- **現在做到哪**：Issue #1140 三批完成——批 1 #1141（C1 價格≤0 一致拒用、C2 未來 `as_of` 不顯示負天數；main `907322aa0af9570fdcca9a496ffdc83e275bfdd3`）；批 2 #1142（融資＋板塊唯讀 L3 service，不接 UI；`1e5542a8`）；批 3 本 docs PR（Digest regime/light 相容性 Gate 研究＋DEC-164＋BACKLOG＋本段）。
- **main SHA**：#1141 合併為 `907322aa`、#1142 合併為 `1e5542a8`；本 docs PR 合併後的 SHA 以 GitHub main 為準。cron 會推進 main，接手前先做 LIVE GitHub Verification Gate。
- **Current Task**：無進行中施工。G-1～G-10 已裁（DEC-164）；兩個 L3 已有但**未接任何 UI**。
- **下一個唯一安全接手點**：**等待客戶裁示，無裁示則停手**（`CLAUDE.md` §-1）。需裁示項：
  1. **Digest A2 實作與否**（`DG-DIGEST-A2`）：見 `docs/vnext/DIGEST_REGIME_LIGHT_COMPAT_GATE_2026-11-11.md` §9；AI 推薦 A2（**非客戶裁示**）。
  2. **UI2 市場頁「市場資金與籌碼」runtime 接線 Gate**（需新 Gate，含 G-F2～G-F6；**外資 L3 另案**；最低覆蓋率門檻 `I1140-COVERAGE-MIN` 待裁示）。
- **禁止事項**：不接 UI2 feed／section runtime、不上線、不做外資 L3、不改資料來源；不改 Digest v1 凍結檔、不升 v2、不建 production caller／OneBrain；不改位階／燈號／公式／PIT、Risk Cap、D1–D5、EPS、登入／OAuth／Sheet、舊 UI；不動 Actions／cron／Secrets；#1119 HOLD；#1124～#1126 禁止順手合併／改寫／rebase（#1126 PIT 未驗）；不得把 AI 推薦寫成客戶裁示。
- **先讀哪些 SSOT**：`CLAUDE.md`（§-2、§-1.5、§-1、§1）→ `PROCESS.md` → `docs/DECISIONS.md` DEC-164（並回看 DEC-157／DEC-160～163）→ `docs/BACKLOG.md`『Issue #1140』段（`I1140-*` 缺口）→ `docs/vnext/NEWUI2_MARKET_CAPITAL_FLOW_TEXT_WIREFRAME_2026-11-11.md`（G 表原題）→ `docs/vnext/DIGEST_REGIME_LIGHT_COMPAT_GATE_2026-11-11.md`。
- **仍 NOT VERIFIED**：Cloud UI2、真機、Playwright／瀏覽器、資料來源授權／PIT、ETF Managers 2026-11-16 20:00 UTC 首次排程。

## 最新接手點（2026-11-11，Issue #1144 舊對話收尾；只追加；不改既有段落；依據 `docs/DECISIONS.md` DEC-165 轉錄，非客戶逐字、非 QA PASS）

> **更正過期狀態**：上方「最新接手點（2026-11-11，Issue #1140）」第 1 項「Digest A2 實作與否（`DG-DIGEST-A2`）等待客戶裁示」**已過期**——客戶已於 Issue #1144 裁示**同意方案 A（A2）**，見 DEC-165。該段原文保留不改（歷史）。UI2「市場資金與籌碼」runtime 接線**仍未授權**。

- **現在做到哪（FACT，GitHub main）**：PR #1141（`907322aa0af9570fdcca9a496ffdc83e275bfdd3`）、#1142（`1e5542a87cdc0006a6535b34457f8b59a85f6baa`）、#1143（`7060cafe618ab93b0afd3d871397aec2071b2034`）均已合併。本交接 docs PR 合併後的 SHA **以 GitHub main 為準**，接手時 LIVE 重查，不得把本文任何 SHA 當最新。
- **Current Task**：**無進行中施工。**A2 builder 與 UI2 前置 Gate 研究皆為「已授權、尚未施工」。
- **下一個唯一安全接手點**：依 Issue #1144，先做 LIVE GitHub Verification Gate，再 ① **A 線**：Digest builder A2（`I1144-A2-IMPL`；Sonnet 5.5、Effort High、靜默巡航）；② **B 線**：UI2 runtime 前置 Gate 研究（`I1144-UI2-PREGATE`；docs-only）。兩線各自獨立 PR。
- **仍需客戶裁示（AI 不得代決）**：最低 coverage 門檻（`I1140-COVERAGE-MIN`）；`G-F2～G-F6`；UI2 runtime 接線 Gate；A3 配對一致性（`I1144-DG-A3`）；`market.health` 0–100 範圍（`I1144-DG-HEALTH`）；外資 L3。
- **不得自行做**：A3、health 範圍、改 `shared/decision_digest*.py` 凍結檔／`normalize_regime`／`get_macro_state`／Risk Cap；改 `real_feed.py`／VM／views／allowlist；接 UI／上線；外資 L3；新來源／API／排程；Digest v2、OneBrain runtime／provider、production caller；公式／燈號／D1–D5／EPS／廣度；OAuth／Sheet／舊 UI／正式路由；碰 #1119（HOLD）或 #1124～#1126；把 AI 推薦或授權寫成「已完成」。
- **先讀 SSOT 順序**：`CLAUDE.md`（§-2、§-1.5、§-1、§1）→ `PROCESS.md` → `PROJECT_RULES.md`（第 32 節）→ `docs/DECISIONS.md` DEC-165、DEC-164（回看 DEC-157／160～163）→ `docs/BACKLOG.md`『Issue #1144』『Issue #1140』→ `docs/HANDOFF.md` 本段 → `docs/PROJECT_STATE.md` §70.6 → GitHub Issue #1144 → `docs/vnext/DIGEST_REGIME_LIGHT_COMPAT_GATE_2026-11-11.md` → UI2／OneBrain 契約（`docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md`、`docs/vnext/ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md`、`docs/vnext/NEWUI2_MARKET_CAPITAL_FLOW_TEXT_WIREFRAME_2026-11-11.md`）。
- **研究文件有效讀法**：`docs/vnext/DIGEST_REGIME_LIGHT_COMPAT_GATE_2026-11-11.md` §7.1／§9 的「等客戶裁示／本批不實作」已被 DEC-165 取代（客戶同意方案 A；A3 與 `market.health` 範圍除外）；研究文原文不改。
- **仍 NOT VERIFIED**：Streamlit Cloud UI2、iOS／Android 真機、Playwright／瀏覽器 viewport、TWSE／TPEX／FinMind 再散布授權、parquet `release_date`／PIT、ETF Managers 2026-11-16 20:00 UTC 首次排程、#1126 PIT。

### 舊對話已保存／未保存清單（本段撰寫時；FACT 除另標）

| 類別 | 內容 |
|---|---|
| **已保存（GitHub）** | main 上 #1141／#1142／#1143；Issue #1144（客戶裁示永久紀錄）；本 PR（DEC-165＋BACKLOG＋HANDOFF＋PROJECT_STATE；合併前仍只在 PR head） |
| **本地未推 commit** | 無；本交接 PR head 已 push（接手時以 GitHub 實況為準） |
| **未保存／未做** | A2 builder 實作、UI2 前置 Gate 研究文件（皆已授權、未施工） |
| **遠端 branches（全部保留，不刪）** | `auto/data-macro-forward-test`、`auto/data-macro-history`、`auto/data-sector-flow`（對應 open PR #1126／#1124／#1125）、`ccr-ed362375-uplnw7`、`claude/stock-dashboard-handoff-g9dtm0`、`data`、`docs/newui2-data-page-trend-onebrain-pdf-20261106`、`docs/newui2-hold-w11-draft-20261105`、`docs/newui2-top-five-nav-wireframe-gate-20261107`、`docs/stock-github-memory-governance-sync-20261106`、`v2` |
| **另有本 PR head** | `ccr-588f897e-7wzywe`（本交接 PR 的 head branch）；合併後由總管另判，**不在 cleanup 候選內** |
| **cleanup 候選** | 以上除 `main`／`data`／`v2`／`auto/data-*` 外的 handoff／docs branch 為**候選**；**皆未經核查是否可清理，僅列候選，待客戶授權；不是刪除授權**（`PROJECT_RULES.md` 分支清理規則：branch 清單屬狀態） |

### GPT 新對話接手提示語（可直接貼用）

```
你是 my-stock-dashboard（GitHub: linchen-20200325/my-stock-dashboard）的治理／驗收端（GPT）。你沒有舊聊天記憶，不得依賴 ChatGPT Memory。
1. 先重新做 GitHub Verification Gate：main 最新 SHA、Open/Draft PR（head、diff）、CI/QA 狀態、branches。GitHub 實況 > HANDOFF > PROJECT_STATE > 記憶；不得把任何文件內的 SHA 當成最新。若 main 尚無 DEC-165，改讀 Issue #1144 本文與 open docs PR（#1145）head 上的 DECISIONS／HANDOFF，並以 Issue 為準。
2. 再讀：CLAUDE.md、PROCESS.md、PROJECT_RULES.md（含第 32 節）、docs/DECISIONS.md（DEC-164、DEC-165）、docs/BACKLOG.md（Issue #1144／#1140 段）、docs/HANDOFF.md（Issue #1144 段）、docs/PROJECT_STATE.md（§70.6）、Issue #1144、docs/vnext/DIGEST_REGIME_LIGHT_COMPAT_GATE_2026-11-11.md、以及相關 Active UI2／OneBrain 契約。
3. 分工：你負責治理、需求釐清、驗收與文件審查；Claude Code 負責實作與測試。嚴格分工，不自己動手寫 production code。
4. 已授權（尚未完成）：Digest builder A2（僅 decision_digest_builder.py::_market_section 白名單驗證＋反例測試）；UI2 runtime 接線「前置 Gate」唯讀研究。未授權：A3、market.health 範圍、UI2 接線／上線、外資 L3、Digest v2、OneBrain runtime/provider、production caller、公式/燈號/Risk Cap/D1–D5/EPS/廣度、OAuth/Sheet、舊 UI、#1119（HOLD）、#1124～#1126。最低 coverage 門檻與 G-F2～G-F6 仍待客戶裁示，不得代決。
5. 驗收時區分 FACT／INFERENCE／RECOMMENDATION，區分「已授權／已完成／NOT VERIFIED」；Cloud、真機、Playwright 未測一律 NOT VERIFIED。不把授權寫成完成。
6. 最終回報 ≤5 行（需客戶裁示時可超過，但只保留裁示所需資訊）。
```

### Claude Code 新對話接手提示語（可直接貼用）

```
你是 my-stock-dashboard 的 Claude Code 實作端（建議 Claude Sonnet 5.5；Digest 語意／跨域稽核 Effort High，純文件 Medium；靜默自主巡航）。無舊 session 記憶。
1. 動工前先 LIVE GitHub Verification Gate：git fetch；確認 main SHA、Open/Draft PR（#1124/#1125/#1126 不得碰）、branches、CI。GitHub 實況優先，不把文件內 SHA 當最新。若 main 尚無 DEC-165，改讀 Issue #1144 本文與 open docs PR（#1145）head 上的 DECISIONS／HANDOFF，並以 Issue 為準。
2. 讀：CLAUDE.md（§-2 派工與獨立複驗、§-1.5、§-1、§1）、PROCESS.md、PROJECT_RULES.md（第 9.0 Model/Effort Gate、第 32 節）、docs/DECISIONS.md（DEC-164/165）、docs/BACKLOG.md（Issue #1144/#1140）、docs/HANDOFF.md（Issue #1144 段）、docs/PROJECT_STATE.md（§70.6）、Issue #1144、docs/vnext/DIGEST_REGIME_LIGHT_COMPAT_GATE_2026-11-11.md §7.1/§7.2、Decision Digest 與 OneBrain 契約。
3. 任務 A（Digest A2，已授權）：僅改 src/services/decision_digest_builder.py::_market_section；白名單由 shared/regime_arbiter.py::REGIME_LIGHT 推導 _VALID_REGIMES/_VALID_LIGHTS；strip().lower() 比對、合法 Fact.text 逐字保留；名單外非空值→INVALID；placeholder／is_loaded=False／無 stamp 維持 MISSING；加反例/正例/大小寫空白/fail-closed/等式 SSOT/mutation 測試。不做 A3、不夾帶 market.health 範圍。若會破壞合法值契約或原型 0 測試轉紅不成立→先停止並上報。
4. 任務 B（UI2 前置 Gate，已授權、docs-only）：唯讀查核 coverage／PIT／資料授權／缺口／G-F2～G-F6／I1140-* 阻塞等，產出研究文件與 3 方案比較；不改 real_feed.py／VM／views／allowlist／程式／測試；最低 coverage 門檻不得自設；缺 release_date 或找不到官方授權原文→NOT VERIFIED。
5. 禁止：改 shared/decision_digest*.py 凍結檔、normalize_regime、get_macro_state、Risk Cap、公式/燈號/D1–D5/EPS/廣度；Digest v2、OneBrain runtime、production caller；接 UI／上線／外資 L3／新來源/API/排程；OAuth/Sheet/舊 UI；#1119/#1124～#1126。
6. 流程：每線獨立 branch/PR；實作與驗收分離（非作者 QA）；同 head 原生 CI 全綠、mergeable clean、0 unresolved 才合併；合併後重查 main。context 不安全時依第 32 節先落盤再換對話。最終回報 ≤5 行；未驗證項明說。
```


---

## 最新接手點｜Issue #1144 執行完畢後（2026-11-11；只追加；依據 DEC-166；本 docs PR 號：#1147）

> **更正**：前段『Issue #1144 接手點』所寫「A2／研究已授權、尚未施工」**已過期**——A2 已完成（PR #1146，main `d4f7b3f6a64d177b7ee0953dc22563adf59120e4`），B 線研究文件已產出（`docs/vnext/UI2_RUNTIME_PREGATE_RESEARCH_2026-11-11.md`，獨立 QA PASS）。前段其餘內容（含完整 GPT／Claude Code 提示語）保留不改。

- **Current Task**：無。
- **下一個唯一安全接手點**：等客戶就 DEC-166 所列 Gate（最低 coverage、G-F2～G-F6、`WIRING-GATE`、A3、health 範圍、外資 L3）裁示；**無裁示即停手**（CLAUDE.md §-1）。AI 推薦方案 B 僅 RECOMMENDATION。
- **未授權**：UI2 runtime 接線、A3、health 範圍、外資 L3、Digest v2、OneBrain、production caller；#1119 HOLD、#1124～#1126 不碰。
- **NOT VERIFIED**：上游授權、PIT、Cloud、真機、Playwright、真實 macro_state。

**Claude Code 一行式接手**：先 LIVE GitHub Verification Gate，讀 DEC-166／DEC-165 與本段；無客戶新裁示不動工；完整提示語見前段『Issue #1144 接手點』，不重貼。
**GPT 一行式接手**：先 LIVE GitHub 驗證，區分已完成／已授權／未授權／NOT VERIFIED，等客戶裁 DEC-166 Gate；完整提示語見前段，不重貼。


## 最新接手點（2026-11-11，Issue #1144 後續「同意 B」；只追加；不改既有段落；依據 `docs/DECISIONS.md` DEC-167）

- **更正前段**：前段『Issue #1144 接手點』與 DEC-166 結尾「等客戶裁 DEC-166 Gate」中的方案選擇，**客戶已裁示「同意 B」**（唯讀證據補強、不接線）；其餘 Gate 仍未裁。
- **已完成**：補充證據文件 `docs/vnext/UI2_RUNTIME_PREGATE_EVIDENCE_SUPPLEMENT_2026-11-11.md`（docs-only；PR #1148）。
- **停點**：`WIRING-GATE`。**不得**改程式／allowlist／real_feed／VM／views；**不得**自設 coverage 百分比；方案 A／C 僅未來候選，非施工授權。
- **待客戶**：`DG-COV`、`DG-PIT`、`DG-LIC`、`DG-SCOPE`、接線授權。**不要把 Digest／OneBrain 的 Gate（G-F2、G-F6、A3、health）當成市場頁前提。**
- **NOT VERIFIED**：上游授權（TWSE／TPEX 全部；FinMind 僅 README 三句）、PIT 發布日、休市表、Cloud、真機、Playwright。證據單組、未經獨立複驗。

**一行式接手**：先 LIVE GitHub Verification Gate，讀 DEC-167／DEC-166 與補充文件；無客戶新裁示不動工。


## 最新接手點（2026-11-11，Issue #1144 B8「NAS 中繼站備援」；只追加；不改既有段落；依據 `docs/DECISIONS.md` DEC-168）

- **客戶指示 B8**：「如果連不上線，記得要用 NAS 中繼站，可以參考舊 UI 的方式。」僅授權唯讀查證，**不授權**改網路架構／Secrets／NAS Server／端點／認證／排程，不得自建第二套 Proxy。
- **已完成**：補充文件 §9（PR 號：#1149）。本環境 NAS 連線資訊**全未設定**（NAS_BASE_URL／NAS_RELAY_URL／NAS_API_KEY／NAS_PROXY_URL／PROXY_URL＝False）；沙箱 `HTTPS_PROXY` 是 agent proxy，不是 NAS，勿冒充。Direct 失敗、NAS 未測試、官方 GitHub 成功（僅 FinMind README）。
- **授權結論無變動**；`DG-LIC` 維持 NOT VERIFIED。**停點仍是 `WIRING-GATE`。**
- **待客戶**：貼條款原文／放行沙箱網域／提供已配置 NAS 的環境並授權唯讀 GET，三擇一或另議；以及 DG-COV／DG-PIT／DG-SCOPE。
- **一行式接手**：先 LIVE GitHub Verification Gate，讀 DEC-168／DEC-167 與補充文件 §9；無客戶新裁示不動工。


## 最新接手點（2026-11-11，Issue #1144 後續「Coverage 母體收斂＋官方條款證據」；只追加；不改既有段落；依據 `docs/DECISIONS.md` DEC-169；本 docs PR 號：#1149）

> **更正前段**：前段（DEC-166／167／168 接手點）寫「等客戶裁 Gate」仍有效；本段補述客戶已授權的**第二批 docs-only 查證**已完成，Gate 一個都沒有關閉。**新的 GPT／Claude Code 接手點以本段為準。**

- **客戶原文**：「同意先收斂 Coverage 母體並補上 TWSE、TPEX、FinMind 官方條款證據。僅授權 docs-only 查證與 GitHub SSOT 更新；其餘 Gate 保持 HOLD。」
- **已完成**：補充文件 `docs/vnext/UI2_RUNTIME_PREGATE_EVIDENCE_SUPPLEMENT_2026-11-11.md` §10（母體收斂）、§11（授權矩陣）、§12（抽查降級＋殘餘阻塞＋下一步）。只追加，§1～§9 未動。
- **要點**：41 板塊＝窗口標籤聯集；3 偶發標籤窗口內僅 7 股日；個股／金額／市值覆蓋皆算不出（`net_amt_yi` 是法人淨買賣超，非成交金額）；RECOMMENDATION 暫不改母體、日後至少 COV-A 強制揭露、候選 COV-C、不選 COV-B。FinMind PARTIALLY VERIFIED（官方 GitHub Pages 原文，**≠TWSE／TPEX 條款**，其稱對外再散布須自行取得原資料機關授權）；TWSE／TPEX／data.gov.tw 官方站沙箱不可連，**維持 NOT VERIFIED**。
- **停點**：`WIRING-GATE`。**不得**改程式／資料／Actions／Secrets／`data_cache`／allowlist／real_feed／VM／views；**不得**自設 coverage 百分比或採用新母體；**不得**據此宣稱已取得再散布授權、已驗證 PIT、已同意接線。repo 公開與 `data_cache` 落地面（含 `industry_raw.json`）只陳述事實，**不做法律結論**，待客戶／法律專業判斷。
- **待客戶**：覆蓋口徑與偶發標籤處理（DG-COV）、是否商業／是否公開／原始列落地（DG-LIC）、時間語意（DG-PIT）、範圍（DG-SCOPE）、接線授權；解封條款查證的方式見補充文件 §12.4（貼條款原文／放行網域／提供已配置 NAS 環境並授權唯讀 GET／法務判斷）。
- **NOT VERIFIED**：TWSE／TPEX／data.gov.tw 授權、OGDL 原頁、FinMind 方案等級與官網即時版本、PIT 發布日、3 偶發標籤個股成因、Cloud／真機／Playwright。證據單組、未經第二組獨立複驗。

**Claude Code 一行式接手**：先 LIVE GitHub Verification Gate（git fetch；確認 main、Open PR、CI；#1119／#1124～#1126 不碰），讀 DEC-169／168／167 與補充文件 §10～§12；無客戶新裁示不動工。
**GPT 一行式接手**：先 LIVE GitHub 驗證，區分已完成／已授權／未授權／NOT VERIFIED，等客戶就 DEC-169 所列 Gate 裁示；不自設門檻、不把網路可達或條款存在當授權；完整提示語見前段，不重貼。


## 最新接手點（2026-11-11，Issue #1144 後續「CI 環境最小修復」；只追加；不改既有段落；依據 `docs/DECISIONS.md` DEC-170；本 docs PR 號：#1151）

> **更正前段**：前段（含 DEC-169 接手點與更早段落）若寫「#1149 被 CI 環境阻塞／`ui2-browser` 因 apt 無法安裝 Chromium 而紅」——**已過期**。客戶已裁示「同意優先採 A，失敗再評估 B」並授權獨立最小修復；方案 A 經 CI 實證失效，方案 B（Playwright 官方容器，tag＋digest 固定）已由 PR #1150 完成並合併（main `96cb7614`）；#1149 內容未改，Update branch 後原生 CI 五項全綠並合併（main `d8d74ccd`）。**新的 GPT／Claude Code 接手點以本段為準；前段完整提示語保留不改、仍可沿用。**

- **客戶原文**：「同意優先採 A，失敗再評估 B。授權專案 AI 獨立進行最小 CI workflow 安裝環境修復，另開 PR，保留全部 Browser required checks 與測試門檻，不碰 #1149 內容或業務程式。」
- **已完成（CI 環境修復，已授權且已完成）**：`pr-check.yml` 的 `ui2-browser` 改在固定 digest 的 Playwright 容器內執行；全部 Browser 守衛保留；無 `continue-on-error`／`|| true`／skip／降門檻／新 Secret；未改 tests／production；獨立 QA PASS。
- **維護注意**：容器映像升級時 image tag、digest、`playwright==` pip pin 須一併更新；不得改用 `latest`；不得降低 Browser 守衛。
- **停點不變**：`WIRING-GATE`。Coverage 母體新算法／最低門檻（`DG-COV`）、PIT 正式語意（`DG-PIT`）、資料再散布最終授權（`DG-LIC`）、`DG-SCOPE`、UI2 接線、Digest A3／`market.health`／外資 L3 **全部仍 HOLD／未授權**；CI 修復**不構成**其中任何一項的核准。
- **待客戶**：就 Coverage 門檻／母體口徑與資料授權風險裁示；無裁示即停手。
- **NOT VERIFIED**：修復只證明在當日 runner 可執行；runner Ubuntu 來源 DNS 故障根因（GitHub 或 Canonical 端）未查明；Streamlit Cloud／真機未驗；`ui2-browser-gate` 是否為 required check（設定面）本工作階段無權限查證。

**Claude Code 一行式接手**：先 LIVE GitHub Verification Gate（git fetch；確認 main、Open PR、CI；#1119／#1124～#1126 不碰），讀 DEC-170／169／168 與本段；CI 已修復、#1149 已合併，勿重做；無客戶新裁示不動工；完整提示語見前段『Issue #1144 接手點』，不重貼。
**GPT 一行式接手**：先 LIVE GitHub 驗證，區分已完成（CI 環境修復 #1150）／已授權／未授權／NOT VERIFIED，等客戶就 `DG-COV`／`DG-LIC` 裁示；不自設門檻、不把 CI 綠燈或網路可達當授權；完整提示語見前段，不重貼。


## 最新接手點（2026-11-11，Issue #1144 後續「公開 Repository 資料曝露／來源授權／儲存架構唯讀稽核」；只追加；不改既有段落；依據 `docs/DECISIONS.md` DEC-171；本 docs PR 號：#1152）

> **更正前段**：前段（DEC-169／170 接手點）寫「等客戶就 Coverage／授權風險裁示」仍有效；本段補述：客戶已裁示「同意方案 B」（先唯讀稽核，再決定是否修改資料保存方式），**授權風險審計已完成**，現在**等客戶裁示儲存方案**。**新的 GPT／Claude Code 接手點以本段為準。**

- **客戶原文**：「客戶已同意方案 B：先執行公開 Repository 的資料曝露、來源授權與儲存架構唯讀稽核，再決定是否修改資料保存方式。」
- **已完成**：研究文件 `docs/vnext/PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT_2026-11-11.md`（docs-only）。要點：`data_cache` 29 檔／個股級 15 檔；僅 FinMind 條款原文 PARTIALLY VERIFIED，其餘來源 NOT VERIFIED，repo 內無授權證據；Git 歷史 1,036 blob／約 80 MB、停止追蹤不減歷史；`industry_raw.json` FinMind 列僅 3 欄（更正「全部原始列」）；無可確認的 Secret／個資事件；三方案比較與分階段候選（標明不可逆階段）。
- **停點**：`WIRING-GATE`。**不得**遷移、刪檔（含 `industry_raw.json`）、改寫歷史、改 repo 可見性、改 workflow／Secrets／儲存／網路；**不得**據此宣稱已授權或已違規；不自設門檻。
- **待客戶**：研究文件 §7（商業？公開？是否可保留個股級來源列？是否授權另案提出階段 1 最小方案？如何取得條款原文？）；其餘 `DG-COV`／`DG-PIT`／`DG-SCOPE`／接線授權仍 HOLD。
- **NOT VERIFIED**：TWSE／TPEX／MOPS／data.gov.tw／央行／Yahoo 條款、FinMind 方案等級與是否商業、Streamlit Cloud 設定、UI 來源標示、歷史 Secret 掃描窮盡性；證據單組、未經第二組獨立複驗。

**Claude Code 一行式接手**：先 LIVE GitHub Verification Gate（git fetch；確認 main、Open PR、CI；#1119／#1124～#1126 不碰），讀 DEC-171／170 與研究文件 §0、§5、§7；稽核已完成，勿重做；無客戶新裁示不動工、不遷移任何資料。
**GPT 一行式接手**：先 LIVE GitHub 驗證，區分已完成（唯讀稽核）／已授權／未授權（遷移、刪檔、改歷史、改可見性）／NOT VERIFIED，等客戶裁示儲存方案與授權三問；不自設門檻、不把公開或可取得當授權；完整提示語見前段，不重貼。


## 最新接手點（2026-11-12，文件重整 3C 收尾；只追加；不改既有段落；依據 `docs/DECISIONS.md` DEC-172／DEC-173；非 QA PASS）

> ~~**本段取代前面各「最新接手點」的現況效力**~~〔📌 現況效力已由檔尾「2026-11-12 Batch 1 完成接手點」接手：本段 Resume Checkpoint 的 current PR（#1160）、working branch、next single action 等皆已過期，不得當最新（有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）。本段對**更早**各段的取代關係仍成立，不因此恢復更早各段〕（前段原文保留為歷史，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕）。GitHub 操作事實優先於本段；接手前先做 LIVE GitHub Verification Gate。

### Resume Checkpoint（`PROJECT_RULES.md` §20.2 十五欄）

| 欄位 | 內容（2026-11-12） |
|---|---|
| latest verified main SHA | `cb3b698a828a797a45d2082c27636bc3a7331f09`（#1159 合併點；2026-11-12 `git fetch origin main` 實查；cron 會推進 main，一律重查） |
| current working branch | `docs/reorg-3c-closure-20261112`（本收尾 docs PR 的 head；合併後可為任何新分支） |
| current PR | 本收尾 docs PR **#1160**〔PR 號補記：有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕〕（Draft；以 GitHub 上 head＝上列分支的 PR 為準）；其餘 Open PR 只有資料 PR #1124／#1125／#1126（不碰） |
| current task / batch | 文件重整 3C（DEC-173 Q1～Q4、Q6）SSOT 收尾：HANDOFF 檔頭過期標示＋本段＋BACKLOG 後續待辦登記 |
| completed in this batch | 見下方「完成項」表（#1153～#1159 全已合併）；本收尾 PR 本身尚未合併 |
| exact current stopping point | 本收尾 PR 已推送、Draft；待非作者獨立 QA 與同 head 原生 CI |
| next single action | 本收尾 PR：非作者 QA＋同 head CI 綠＋mergeable clean 後合併；**合併後無客戶新指派即停手**（`CLAUDE.md` §-1）；若客戶授權，首選 `REORG3C-REF-SYNC`（BACKLOG 檔尾） |
| tests / CI 已完成 | #1153～#1159 各 head 原生 CI 五項 success（2026-11-12 REST check-runs 實查）；本 PR 作者端跑讀 HANDOFF／BACKLOG 的測試（結果見 PR 描述） |
| tests / CI 尚未完成 | 本 PR 的非作者獨立 QA、同 head 原生 CI |
| unresolved true Stop Gates | Q5（`REORG3C-Q5-GATE`）；`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、`I1144-DATA-STORAGE-DECISION`、`I1144-DG-A3`、`I1144-DG-HEALTH`、外資 L3、G-F2～G-F6（全部 HOLD） |
| 是否存在 uncommitted / unpushed work | 否（本 PR 推送後；以 `git status`／GitHub 實查為準） |
| relevant evidence location | `docs/DECISIONS.md` DEC-172／DEC-173；`docs/archive/historical/*_HISTORY_2026-11-12.md`；BACKLOG 檔尾「文件重整 3C 收尾」段；各 PR 頁 |
| recommended Model | Claude Sonnet 5.5（純文件；AI 總管建議，非客戶裁示） |
| recommended Effort | Medium（純文件；涉規範位階判斷時升 High） |
| last checkpoint timestamp | 2026-11-12（UTC 約 07:00） |

### 完成項（FACT：merge SHA 與 CI 為 2026-11-12 GitHub REST 實查）

| PR | 內容 | merge SHA | 同 head 原生 CI | 非作者 QA |
|---|---|---|---|---|
| #1153 | D1–D5 就地取代註記 | `e5a8ec05` | 5 項 success | 總管轉述 PASS；GitHub 上無 QA 紀錄 → NOT VERIFIED |
| #1154 | scratchpad 3 檔 → `docs/archive/historical/` | `a2374b5a` | 5 項 success | 同上 NOT VERIFIED |
| #1155 | DEC-172／DEC-173 登錄 | `a2926c8e` | 5 項 success | 同上 NOT VERIFIED |
| #1156 | Q1 HANDOFF 歷史段逐字歸檔 | `16a93a4e` | 5 項 success | 同上 NOT VERIFIED |
| #1157 | Q2 PROJECT_STATE 7 節 | `8988da08` | 5 項 success | 同上 NOT VERIFIED |
| #1158 | Q3 BACKLOG 已結案段＋附錄 B | `e51aa30e` | 5 項 success | 同上 NOT VERIFIED |
| #1159 | Q4 CLAUDE.md §0 填寫紀錄 | `cb3b698a` | 5 項 success | PR review 有獨立唯讀 QA 留言（判 PASS） |

### 量測結果（總管轉述；harness `subagent_tokens` 單次樣本，含系統提示與多輪累計，**非檔案 token**；本組未重測）

- 新 Agent 接手：HANDOFF 222,993／9 次工具 → 206,526／5 次（-7.4%；新讀者讀完全檔，舊讀者僅讀約 24%）；PROJECT_STATE（首版）224,859／13 → 315,683／18（**上升**；新讀者改讀全檔，收益僅在有效知識比例）；BACKLOG 232,943／32 → 205,531／12（-11.8%）；CLAUDE.md 未做 agent 實測。
- 估算檔案 token（CJK×1＋其餘÷4）：HANDOFF 162.1k→26.1k、PROJECT_STATE 101.1k→96.3k、BACKLOG 317.2k→302.2k、CLAUDE.md 58.1k→57.8k（-0.6%）。
- 限制：單次樣本、無對照重複、讀取策略不同；不得當成穩定成效或 Q5 的實測結論。

### 未完成／HOLD／待客戶

- **未執行**：Q5（DEC-173：不得拆分 `CLAUDE.md` §-1.5 判定本文）；DEC-173 範圍外的 `docs/DECISIONS.md`／`PROCESS.md`／`PROJECT_RULES.md`／`STATE.md` 等其他文件歸檔 —— 均需客戶另行裁示（`REORG3C-Q5-GATE`）。
- **待客戶裁示（2026-11-12 補列；有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕；附推薦者為 AI 推薦，非客戶裁示）**：
  1. `I1144-DATA-STORAGE-DECISION`（DEC-171；`docs/vnext/PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT_2026-11-11.md` §7）：是否修改資料保存方式（儲存方案），以及授權三問——本專案是否商業、是否公開對外、公開 repo 保留個股級來源列是否可接受（`I1144-LIC-THREE-QUESTIONS`）。
  2. `REORG3C-REF-SYNC` 的授權與範圍確認：是否授權引用同步；改 `PROJECT_RULES.md`／`docs/DECISIONS.md` 是否在 DEC-173 範圍內。
  3. Q5（DEC-173 原文）：「Q5＝暫不執行：不得拆分 CLAUDE §-1.5 判定本文，先實測 Q4 的 Token 成效與 Agent 遵循能力。」——是否及何時重議。
- **已知後續（登記於 BACKLOG 檔尾，皆未動工）**：`REORG3C-REF-SYNC`、`REORG3C-DEC092-L309-MOVE`、`REORG3C-DLF1S8-ROW`、`REORG3C-SEC3-HEADER`。
- **HOLD／不碰**：#1124～#1126（資料 PR）、#1119；UI2／OneBrain／資料 Gates（同上表 Stop Gates）。
- **禁止**：無客戶指派不動工；不合併／改寫／rebase #1124～#1126；不把 AI 推薦寫成客戶裁示；不把歸檔讀成刪除授權（DEC-173 Q6）；不刪客戶原文、DEC、hash 證據或有效規範。
- **先讀 SSOT**：`CLAUDE.md` → `PROCESS.md` → `PROJECT_RULES.md`（§15、§20）→ `docs/DECISIONS.md` DEC-173／DEC-172（回看 DEC-171）→ `docs/BACKLOG.md` 檔尾「文件重整 3C 收尾」段 → 本段；歷史接手點見 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md`。
- **仍 NOT VERIFIED**：#1153～#1158 的非作者 QA（GitHub 上無紀錄）；Cloud UI2、真機、Playwright；ETF Managers 2026-11-16 20:00 UTC 首次排程。本段單組撰寫，未經第二組驗證。


## 2026-11-12 Batch 1 完成接手點（只追加；不改既有段落；依據 `docs/DECISIONS.md` DEC-174 及其結果指標；非 QA PASS）

> 本段取代上方「最新接手點（2026-11-12，文件重整 3C 收尾）」的現況效力（有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）。GitHub 操作事實優先於本段；接手前先做 LIVE GitHub Verification Gate。**不另建第二份 handoff**（`PROJECT_RULES.md` §20.1）。

| 欄位（§20.2） | 內容（2026-11-12） |
|---|---|
| latest verified main SHA | ~~`68e56ff0`（#1165 合併點；2026-11-12 `git rev-parse origin/main` 實查；cron 與其他 PR 會推進 main，一律重查）~~ 【已被檔尾「2026-11-12｜DEC-175 最新安全接手點」取代；2026-11-12 Delta 修正，有意識的更正，不是漏刪；決策者 AI 總管〔事實更新，依獨立 QA 項目 1〕】 |
| current working branch | `docs/batch1-ssot-closure-20261112`（本收尾 docs PR 的 head；合併後可為任何新分支） |
| current PR | ~~本收尾 docs PR **#1167**（Draft；以 GitHub 上 head＝上列分支者為準）；其餘 Open PR：#1164（REORG3C 歸檔，Draft，不碰）、資料 PR #1124／#1125／#1126（HOLD，不碰）~~ 【已被檔尾「2026-11-12｜DEC-175 最新安全接手點」取代；2026-11-12 Delta 修正，有意識的更正，不是漏刪；決策者 AI 總管〔事實更新，依獨立 QA 項目 1〕】（#1167 已合併為 `6241ad3b`） |
| current task / batch | DEC-174 方案 B Batch 1 SSOT 收尾：DECISIONS 結果指標＋BACKLOG 後續待辦登記＋本段 |
| completed in this batch | A1／C1（#1165，兩份稽核文件）、DEC-174 登錄（#1166）；B1 結論＝未發現契約內可重現缺陷，故無 UI 修復 PR；本收尾 PR 本身尚未合併 |
| exact current stopping point | 本收尾 PR 已推送、Draft；待非作者獨立 QA 與同 head 原生 CI |
| next single action | 本收尾 PR：非作者 QA＋同 head CI 綠＋mergeable clean 後合併；**合併後無客戶新指派即停手**（`CLAUDE.md` §-1）；下一批候選見下，皆須客戶指派 【2026-11-12 Delta 修正註記，有意識的更正，不是漏刪；決策者 AI 總管〔事實更新，依 Delta QA N1〕：本欄為 #1167 當時的下一步。DEC-175（客戶 2026-11-12）~~**是否構成開工指派，待客戶確認；確認前維持 `CLAUDE.md` §-1 與「無客戶指派不動工」**~~ 【已由 DEC-176(c) 回答（客戶 2026-11-12，經派工訊息轉錄）：DEC-175 不是無條件施工授權、不解除 `CLAUDE.md` §-1 等既有 Gate；既有明確核准的工作不必重新請示；2026-11-12，有意識的更新，不是漏刪；決策者 客戶〔DEC-176(c)〕＋AI 總管〔事實更新〕】；原句不加刪除線、不視為被 DEC-175 取代（本註記不新增授權）】 |
| tests / CI 已完成 | 作者端 `tests/test_sec_s3_batch_s3.py`、`tests/test_sec_s4_batch_s4.py`、`tests/test_ui2_active_contract_docs.py` 及其餘讀此三檔的測試（結果見 PR 描述）；#1165 同 head 五項原生 CI 全綠（轉述自 PR 描述，本組未重查） |
| tests / CI 尚未完成 | 本 PR 的非作者獨立 QA、同 head 原生 CI；兩份稽核文件的第二組獨立複驗 |
| unresolved true Stop Gates | #1119 HOLD；`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、`I1144-DATA-STORAGE-DECISION`、`I1144-DG-A3`、`I1144-DG-HEALTH`、外資 L3、G-F2～G-F6、`REORG3C-Q5-GATE`（全部未動） |
| 是否存在 uncommitted / unpushed work | 否（本 PR 推送後；以 `git status`／GitHub 實查為準） |
| relevant evidence location | `docs/vnext/NEWUI2_FIVE_PAGE_DATA_CONTRACT_AUDIT_2026-11-12.md`（§0、§7、§11）、`docs/vnext/NEWUI2_MARKET_DATA_CONTRACT_VALIDATION_2026-11-12.md`（§0、§7、§10）；`docs/DECISIONS.md` DEC-174 結果指標；BACKLOG 檔尾「方案 B Batch 1 收尾」段（`DEC174-*`） |
| recommended Model | Claude Sonnet 5.5（純文件；AI 總管建議，非客戶裁示） |
| recommended Effort | ~~Medium（純文件；獨立複驗或涉規範位階判斷時升 High）~~ 【已被檔尾「2026-11-12｜DEC-175 最新安全接手點」取代；2026-11-12 Delta 修正，有意識的更正，不是漏刪；決策者 AI 總管〔事實更新，依獨立 QA 項目 1〕】（現行值只維護於檔尾新段一處，不在此重複） |
| last checkpoint timestamp | 2026-11-12 11:42 UTC（`date -u` 實查，為 QA 修正 commit 前最後查核時間；不早於 PR 推送時間） |

- **完成項（指標；merge SHA 取自 `git log origin/main`，CI／QA 見各 PR 頁，本組未逐項重查）**：#1153～#1159（3C Q1～Q4、DEC-172／173 登錄；見上一段）；#1160 `ced0232b`（3C 收尾）；#1161～#1163（REF-SYNC 與 BACKLOG 表頭，`755aee87`／`f57e7c77`／`7eb48d6c`）；#1166 `dae78eea`（DEC-174 登錄）；#1165 `68e56ff0`（Batch 1 兩份稽核文件）。
- **Batch 1 結論**：(1) 預設路徑只到 FAKE，REAL 軸帶真值僅台股卡與日 K，位階已接線但 UI2 獨立 session 目前恆未載入；(2) 「市場資金與籌碼」不在 UI2 VM，融資／板塊 L3 引用數為 0，外資無 L3；(3) 口徑問題：`finmind_inst` 同欄兩種 `source` 標籤、板塊外資分項與 FinMind 外資同日不等、stale 4 日 vs 7 日；(4) 台股卡資料日停在 2026-11-09，疑與資料 PR #1124～#1126 未合併有關（INFERENCE）；(5) B1：未發現契約內可重現缺陷，其餘為 Visual Gate 候選／文案漂移／守衛缺口，皆已登記 BACKLOG `DEC174-*`，皆非授權。
- **仍 HOLD／NOT VERIFIED**：上表 Stop Gates 全部；兩份文件的第二組複驗、PIT、授權原文、cron 成功率、Cloud UI2、真機、Real 軸瀏覽器量測、ETF Managers 2026-11-16 20:00 UTC 首次排程。
- **需客戶裁示**：(1) 是否處置資料 PR #1124～#1126（BACKLOG `DEC174-DATA-PR-1124-1126-DISPOSITION`；AI 推薦：本批與下一批皆不處置，先做唯讀 PIT 與 cron 成功率檢查）；(2) VG1／VG2 的**文字線框**（Visual Gate 候選，草稿先行，客戶拍板前不寫 UI code）；「只接 2 項真資料」文案漂移（`DEC174-COPY-DRIFT-2ITEMS`）**先確認類別**——開發面文案屬內部自決，產品畫面才需文字線框，不預設請客戶為它出線框；(3) Q5 沿用 DEC-173：暫不執行，是否及何時重議；(4) 既有 `I1144-DATA-STORAGE-DECISION`／`I1144-LIC-THREE-QUESTIONS`。
- **下一批施工候選（最多 3 項；照五頁稽核 §11 原文，皆為 RECOMMENDATION，非授權，不得自動跨越 Decision Gate）**：
  1. 獨立複驗兩份文件（派第二組非作者重做關鍵 FACT 與 CAPMAP 對帳，含部署端位階實況）——不需客戶裁示（仍須客戶指派）；稽核推薦先做。
  2. 把「接線前須客戶裁示」整理成商業語言的一頁決策單（DG-SCOPE／DG-COV／DG-PIT／DG-LIC 四問＋AI 推薦）——需客戶看；不解除 `I1144-WIRING-GATE`。
  3. （需客戶先裁示，未裁示則不計入該批）🗂 資料頁新鮮度總覽的文字線框草稿——稽核暫不推薦自動啟動。
- **禁止**：無客戶指派不動工；不碰、不合併、不改寫、不 rebase #1124～#1126、#1164；#1119 維持 HOLD；完整 HOLD 清單見 `docs/DECISIONS.md` DEC-174；不把 AI 推薦寫成客戶裁示；不把稽核分類（READY／BLOCKED）讀成 Gate 解除或資料可用；不把歸檔讀成刪除授權（DEC-173 Q6）。
- **先讀 SSOT**：`CLAUDE.md` → `PROCESS.md` → `PROJECT_RULES.md`（§15、§20、§23）→ `docs/DECISIONS.md` DEC-174（含結果指標）／DEC-173 → `docs/BACKLOG.md` 檔尾「方案 B Batch 1 收尾」段 → 兩份稽核文件 → 本段。
- **其餘 open 的 `REORG3C-*`**：見 BACKLOG 檔尾 3C 收尾段——`REORG3C-REF-SYNC`（P1）、`REORG3C-DLF1S8-ROW`、`REORG3C-SEC3-HEADER`（BACKLOG 該段列為 open）；#1164（Draft）＝`REORG3C-DEC092-L309-MOVE` 的搬移實作；`REORG3C-Q5-GATE` 待客戶。Q5 相關 Token 量測為單次樣本，不得當統計結論。本段單組撰寫，未經第二組驗證。



## 2026-11-12｜DEC-175 最新安全接手點（新增優先序；舊段保留為歷史；非 QA PASS）
> 客戶最新裁示：先處理股票 **UI2＋現有資料層／資料契約**，Actions 清理延後到最後 Old UI／死碼清理階段。正式裁示在 `docs/DECISIONS.md` DEC-175；本段是快照而非 GitHub SSOT。開始前必做 Live GitHub Verification Gate。**不另建第二份 handoff**（`PROJECT_RULES.md` §20.1）。
> 本段取代上方「Batch 1 完成接手點」的現況效力（有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）；該段被取代的句子已在原處加刪除線並註明。**「無客戶指派不動工」不在被取代之列**~~（DEC-175 是否構成開工指派待客戶確認；確認前維持 `CLAUDE.md` §-1）~~ 【已由 DEC-176(c) 回答（客戶 2026-11-12，經派工訊息轉錄）：DEC-175 不是無條件施工授權、不解除 `CLAUDE.md` §-1 等既有 Gate；既有明確核准的工作不必重新請示；2026-11-12，有意識的更新，不是漏刪；決策者 客戶〔DEC-176(c)〕＋AI 總管〔事實更新〕】。

> 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】：下表凡以刪除線標示的欄位（main SHA、分支、PR、task、停點、下一步、tests／CI、Model／Effort、timestamp）皆已過期（#1168 已合併為 `169b74ed`，main 已前進至 `76ed4b7b`，Open PR 清單已變）；未加刪除線的列（Stop Gates、uncommitted、evidence location）仍可參考，但一律以檔尾新段為準。

| 欄位（§20.2） | 內容（2026-11-12） |
|---|---|
| latest verified main SHA | ~~`2a1623e8ab9a09af6cb006956dbdfd2e326fd887`（#1171 合併點，2026-11-12T14:16:09Z；GitHub REST 實查，FACT）；其前為 `aa98de4c`（#1169）、`6241ad3b`（#1167）。main 會被其他 PR／cron 推進，一律重查~~ 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】 |
| current working branch | ~~`docs/dec175-ui-data-priority-continuity-20261112`（已 merge `aa98de4c` 與 `2a1623e8` 進分支，皆無衝突；merge 非 rebase）~~ 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】 |
| current PR | ~~**#1168**（Draft；docs-only）。其餘 Open PR：#1164（REORG3C 歸檔，Draft）、#1170（docs 對帳，Draft）、資料 PR #1124／#1125／#1126（HOLD）——皆不碰。#1119 不在 Open PR 清單，僅為 HOLD 項目名稱。#1171（CI 修復，2026-11-12T13:48:24Z 建立）已於 2026-11-12T14:16:09Z 合併為 `2a1623e8`（GitHub REST 實查，FACT），已併入本分支；其修正是否有效 NOT VERIFIED~~ 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】 |
| current task / batch | ~~DEC-175 續接規範登錄（DECISIONS／PROJECT_RULES／BACKLOG／HANDOFF 四檔）＋依獨立 QA 的 8 項文字修正（客戶「方案 A」授權（來源：經派工訊息轉錄；repo 與 PR 留言內無原文；與 PR #1168 留言 6824799769 的「方案 A」〔CI 最小環境修復〕是**兩件不同的授權**，不得混讀））＋Delta QA 後 N1～N6 追加修正~~ 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】 |
| completed in this batch | ~~DEC-175 四檔追加（原 head `4c1a7354`）；QA 8 項文字修正已套用；merge main 進分支~~ 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】 |
| exact current stopping point | ~~Delta QA（單組，轉述自派工訊息）判定 8 項大致落實、PASS with fixes；N1～N6 追加修正 commit 已推送；待再次 Delta QA 與同 head 原生 CI；維持 Draft，未合併、未轉 ready~~ 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】 |
| next single action | ~~非作者 Delta QA 核對 8 項修正 → 同 head 五項原生 CI 全綠＋review threads＝0＋mergeable clean → 依現行 Auto-Ship Gate 判斷。CI 紅燈屬環境類（見下）者，修復走獨立 PR（#1171，已合併為 `2a1623e8`；有效性 NOT VERIFIED），不在本 PR。**DEC-175 是否構成開工指派待客戶確認；確認前維持 `CLAUDE.md` §-1 與無客戶指派不動工**~~ 【已由 DEC-176(c) 回答（客戶 2026-11-12，經派工訊息轉錄）：DEC-175 不是無條件施工授權、不解除 `CLAUDE.md` §-1 等既有 Gate；既有明確核准的工作不必重新請示；2026-11-12，有意識的更新，不是漏刪；決策者 客戶〔DEC-176(c)〕＋AI 總管〔事實更新〕】 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】 |
| tests / CI 已完成 | ~~作者端本機：`tests/test_sec_s3_batch_s3.py`、`tests/test_sec_s4_batch_s4.py`、`tests/test_ui2_active_contract_docs.py` 及讀這四檔的其餘測試（結果見 PR 描述）；`scrub_secrets`／`scrub_prose_secrets` 對四檔零改寫；DEC-175 fence sha256 重算相符。單組非作者 QA（舊 head `4c1a7354`）已完成，判定 PASS with fixes（內容層）~~ 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】 |
| tests / CI 尚未完成 | ~~修正後的 Delta QA；**修正後新 head** 的原生 CI 五項（舊 head `4c1a7354` run 43216473677：`ui2-browser` 1.56.0／1.59.2 與 gate 為 exit 127 環境類失敗，轉述自 PR 留言、本組未重查 job log）；fence 與客戶原訊息的逐字一致性~~ 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】 |
| unresolved true Stop Gates | #1119 HOLD；#1124～#1126 HOLD（PIT／cron 先唯讀）；`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、`I1144-DATA-STORAGE-DECISION`、`I1144-DG-A3`、`I1144-DG-HEALTH`、外資 L3、G-F2～G-F6、`REORG3C-Q5-GATE`、Old UI Removal Gate（全部未動；DEC-175 未解除任何一項） |
| 是否存在 uncommitted / unpushed work | 否（推送後；以 `git status`／GitHub 實查為準） |
| relevant evidence location | `docs/DECISIONS.md` DEC-175（含 fence＋sha256、AI 整理分節、QA 軌跡）；`docs/BACKLOG.md` 檔尾「DEC-175」段（`DEC175-*`）；`PROJECT_RULES.md` 檔尾 DEC-175 索引；單組 QA 報告僅存於上一輪派工輸出，repo 內無，8 項已逐項記於 PR 描述；#1169 新增三份 `docs/vnext/` 文件（見下） |
| recommended Model | ~~Claude Sonnet 5.5（純文件；AI 總管建議，非客戶裁示）~~ 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】 |
| recommended Effort | ~~High（涉規範位階與 Gate 文字判斷；AI 總管建議，非客戶裁示；**現行值只維護於此處**）~~ 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】 〔📌 更正（有意識的更正，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）：此處劃線只表示「現行值改維護於檔尾新段」，**不是**被 Medium 取代；該 High 與客戶最新派工訊息（Effort：High）一致，檔尾新段現行值亦為 High。〕 |
| last checkpoint timestamp | ~~2026-11-12 14:17 UTC（`date -u` 實查；追加修正 commit 前；前一版 13:50 UTC）~~ 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】 |

- **PROJECT_STATE 未更新**：本批只新增優先序／續接索引，無新增有效架構知識，故未動 `docs/PROJECT_STATE.md`（`PROJECT_RULES.md` §0.3 五檔分工的有意識省略，非遺漏）。
- **FACT（main 現況，僅陳述存在，非授權）**：#1169（`aa98de4c`）於 `docs/vnext/` 新增三份文件——`NEWUI2_INDEPENDENT_REVERIFICATION_2026-11-12.md`、`DATA_WIRING_GATE_DECISION_SHEET_2026-11-12.md`、`DAILY_DATA_PR_PIT_CRON_INVESTIGATION_2026-11-12.md`。本 PR **未複核其內容**；它們不解除任何 Gate、不構成接線／資料 PR 處置授權；是否取代前段「下一批施工候選 1／2」**NOT VERIFIED**，由客戶／下一批 QA 判定。
- **已完成（前序）**：DEC-174 Batch 1，#1165 五頁稽核與市場資料契約、#1166 DEC-174、#1167 結果／BACKLOG／HANDOFF 收尾。尚缺外部／第二組獨立事實複驗，不可把 PR QA 等同於所有外部實測。
- **當前主線**：沿用 DEC-174「UI＋資料契約雙軌」，每批最多三項；先核查資料來源→快取→L3→Canonical→UI2 的既有讀取路徑、PIT／新鮮度／coverage／資料狀態，再做已核准範圍內 UI 安全改善。新 layout／文案／欄位／動線變更仍須文字線框及裁示。
- **資料 PR 處置**：#1124～#1126 保持 HOLD；唯讀 PIT／cron 先查證，AI 推薦暫不處置不是客戶的新決策。資料來源授權與 WIRING Gate、資料儲存架構及 #1119 等原 HOLD 均不變。〔📌 已被超前（有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）：唯讀 PIT／cron 查證已由 #1169（`aa98de4c`）與 #1172（`57885e6e`）完成；外部對帳／處置仍待客戶裁示，#1124～#1126 維持 HOLD（DEC-176(a)）。〕
- **CI（環境類，登記於 BACKLOG `DEC175-CI-UI2BROWSER-EXIT127-RECUR`）**：客戶 2026-11-12 以「方案 A」（PR #1168 留言 6824799769，CI 最小環境修復；**與上述 8 項文字修正的授權是不同的兩件事**）授權在獨立分支／獨立 PR 做最小 CI 環境修復；獨立 PR #1171（2026-11-12T13:48:24Z 建立）已於 2026-11-12T14:16:09Z 合併為 `2a1623e8`（GitHub REST 實查，FACT）；該 PR 描述稱失敗為 runner image 分流（預建 pip 26.3 失敗／26.2.2 成功，轉述自 #1171 描述，本組未重查日誌）〔📌 2026-11-12 更正（有意識的更正，不是漏刪；決策者 AI 總管〔事實更新〕）：「image 分流」推測**不成立**——失敗 job 131230664848 的 image 是 `20261111.127.1`，非 370.1；目前僅知預建 pip 26.3 與失敗共變（INFERENCE）；詳見 DEC-176(b)〕；**#1171 的修正是否有效 NOT VERIFIED**（#1171 描述自陳：其 CI 綠不構成驗證，須至少一個 cell 落在預建 pip 26.3 並成功）〔📌 2026-11-12 後續（有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕）：#1171 修正生效後已有至少 2 個預建 pip 26.3 的 1.59.2 cell 成功（其一 run 43232020099 job 131229652524 為 #1171 PR 自身 CI〔合併前〕，其一 run 43235464794 job 131241682819 為合併後；兩 job 的預建 pip 版本本組未逐一讀到，NOT VERIFIED），但樣本少、非證明，**有效性仍 NOT VERIFIED**；現況見檔尾「Batch 3 同步後最新接手點」〕。不得降低 matrix／gate／測試數量／no-skip。本 PR 不含 workflow 變更。
- **仍 NOT VERIFIED**：PIT、cron 成功率〔📌 已被 #1169／#1172 超前（有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）：唯讀查證已完成，但 PIT 仍未驗、外部對帳／處置仍待客戶〕、來源授權原文、Cloud／真機／Real 軸量測及資料能否供正式決策；下列兩項**來源僅在客戶／派工對話，repo 內無出處**（本組 2026-11-12 `git grep` docs／PROJECT_RULES.md 0 命中），不得當 repo 內可追溯事實：「V1 CSV 只盤點，不刪」（Actions Runs／Artifacts 盤點）、「11/10 與 11/11 市場交易日核查」。
- **暫緩**：GitHub Actions Runs／Artifacts 清理與舊 UI／死碼清理（DEC-175「這」＝Actions 清理，與「CSV 候選」皆為 **INFERENCE、來源僅派工對話**，可參 Issue #1119 留言 6768487486／6822675191 作脈絡，**未證實等同**），放到安全 cutover／rollback 驗收後；Runs／Artifacts 刪除屆時仍須客戶逐批明示授權（不可逆，`CLAUDE.md` §-1.5.D §03-2 ②），Old UI／死碼受 Old UI Removal Gate 與 DEC-173 Q6 拘束。
- ~~**下一安全動作**：依委派治理先做非作者獨立 QA 與來源契約決策材料，不在 HOLD 未解除時接線；每批同步既有 DECISIONS／BACKLOG／PROJECT_STATE／HANDOFF，避免跨對話失憶。此段不是獨立施工授權。~~ 【已被檔尾「2026-11-12｜Batch 3 同步後最新接手點」取代；2026-11-12，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕】（該段所列「來源契約決策材料」已由 #1169／#1172／#1173 產出）


## 2026-11-12｜Batch 3 同步後最新接手點（只追加；依據 `docs/DECISIONS.md` DEC-176；非 QA PASS；~~**本段為現行有效接手點**~~〔已被檔尾 2026-11-12「六處差異收尾後最新接手點」取代（有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）〕）

> 本段取代上方「DEC-175 最新安全接手點」的現況效力（有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）；該段被取代的欄位已在原處加刪除線並註明。GitHub 操作事實優先於本段；接手前先做 LIVE GitHub Verification Gate。**不另建第二份 handoff**（`PROJECT_RULES.md` §20.1）。本段不重複 BACKLOG／DECISIONS 全文，細項見指標。

### Resume Checkpoint（`PROJECT_RULES.md` §20.2 十五欄）

| 欄位（§20.2） | 內容（2026-11-12） |
|---|---|
| latest verified main SHA | `76ed4b7bb486f1fd3db51c0df09d09f15a93f797`（#1173 合併點；2026-11-12 `git fetch origin main` 與 GitHub MCP 取回 main 提交紀錄，FACT；cron 與其他 PR 會推進 main，一律重查） |
| current working branch | `docs/ssot-sync-batch3-20261112`（本同步 docs PR 的 head；合併後可為任何新分支） |
| current PR | 本同步 docs PR **#1174**〔PR 號補記：有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕〕（Draft；以 GitHub 上 head＝上列分支者為準）。其餘 Open PR：#1164（REORG3C 歸檔，Draft）、資料 PR #1124／#1125／#1126（HOLD；head `fc447def`／`1efb178a`／`428258b3`；check runs 0、pr-check 為 `action_required`）——皆不碰。#1119 不在 Open PR 清單，僅為 HOLD 項目名稱 |
| current task / batch | **無進行中的客戶批次**；僅有本同步 PR＝客戶 2026-11-12 派工三項安全工作之 ① GitHub SSOT 結果同步（②＝#1173、③＝#1172 已合併；見 DEC-176(c)）。本批做完即停止擴張並回報 |
| completed in this batch | 見下方「已完成」表（#1165～#1173 全已合併）；本同步 PR 本身尚未合併 |
| exact current stopping point | 本同步 PR 已推送、Draft；待非作者獨立 QA 與同 head 原生 CI。**未做**：任何 UI／資料／workflow 變更 |
| next single action | 本同步 PR：非作者 QA＋同 head 五項原生 CI 全綠＋review threads＝0＋mergeable clean 後依 Auto-Ship Gate 判斷（作者不自行合併）。**合併後無客戶新裁示即停手，只做被動觀察**（見下「唯一安全下一步」） |
| tests / CI 已完成 | 作者端本機：`tests/test_sec_s3_batch_s3.py`、`tests/test_sec_s4_batch_s4.py`、`tests/test_ui2_active_contract_docs.py` 及 grep 命中這五檔的守衛測試（結果見 PR 描述）；`scrub_secrets`／`scrub_prose_secrets` 對新增文字零改寫；DEC-173／174／175／176 fence sha256 重算（既有三者未變）。各已合併 PR 的 QA／CI 見下表（轉述，未逐 PR 重讀 check runs） |
| tests / CI 尚未完成 | 本 PR 的非作者獨立 QA、同 head 原生 CI；DEC-176(a)(b)(c) 與客戶原訊息的逐字一致性 |
| unresolved true Stop Gates | #1119 HOLD；#1124～#1126 HOLD（客戶 DEC-176(a) 方案 A；非合併授權）；#1164 HOLD；`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、`I1144-DATA-STORAGE-DECISION`、`I1144-DG-A3`、`I1144-DG-HEALTH`、外資 L3、G-F2～G-F6、`REORG3C-Q5-GATE`、Old UI Removal Gate、預設 UI 切換（全部未動；DEC-175／DEC-176 未解除任何一項） |
| 是否存在 uncommitted / unpushed work | 否（本 PR 推送後；以 `git status`／GitHub 實查為準） |
| relevant evidence location | `docs/DECISIONS.md` DEC-176（含兩個 fence＋sha256）／DEC-175；`docs/BACKLOG.md` 檔尾「DEC-176 結果同步」（`DEC176-*`）；`docs/PROJECT_STATE.md` §70.13；`docs/vnext/` 的 #1169（三份）、#1172、#1173、#1170 文件；`PROJECT_RULES.md` 檔尾 DEC-175 索引後的 DEC-176(c) 釐清 |
| recommended Model | Claude Sonnet 5.5（客戶最新派工訊息指定；經派工訊息轉錄，逐字 NOT VERIFIED；**現行值只維護於此處**） |
| recommended Effort | High（客戶最新派工訊息指定〔「CI 修復＋#1168／#1170…續工」與「DEC-175 權限釐清與下一批」兩則皆寫 Effort：High〕；經派工訊息轉錄，逐字 NOT VERIFIED）；Mode：靜默自主巡航（客戶派工訊息指定；轉錄，NOT VERIFIED）。**現行值只維護於此處**。〔更正（有意識的更正，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）：本欄初稿曾寫「Medium」，與客戶派工訊息相反，已改；初稿原字未保留於本欄，更正紀錄在此。〕 |
| last checkpoint timestamp | 2026-11-12T16:07:07Z（`date -u` 實查；PR 推送前最後查核） |

### 已完成（FACT：merge SHA 取自 2026-11-12 main 提交紀錄；QA／CI 為合併提交訊息與派工訊息自述，**本組未逐 PR 重讀 review／check runs**）

| PR | 內容 | merge SHA | 非作者 QA | 同 head 原生 CI |
|---|---|---|---|---|
| #1165 | 五頁／市場資料契約稽核（2 份 docs） | `68e56ff0` | 兩組 PASS（PR 描述自述） | 最終 head `9ef6b81a` 五項全綠（自述） |
| #1166 | DEC-174 登錄 | `dae78eea` | 獨立 QA 微修三條（提交訊息） | 全綠（派工訊息） |
| #1167 | Batch 1 SSOT 收尾 | `6241ad3b` | 獨立 QA 修正（提交訊息） | 全綠（派工訊息） |
| #1169 | A 獨立複驗／B 資料接線決策單／C 資料 PR PIT-cron 調查（3 份 docs） | `aa98de4c` | 兩組 ＋修正後複驗皆 PASS | 同 head 五項全綠 |
| #1171 | CI：`ui2-browser` 容器 job `pip`→`python -m pip` | `2a1623e8` | PASS with fixes（已補）；最後一次僅註解字句補修由總管看 diff 確認（**未經第二組**） | 同 head 五項全綠；**修正有效性 NOT VERIFIED** |
| #1168 | DEC-175 登錄 | `169b74ed` | 獨立 QA ＋兩輪 Delta PASS with fixes | 同 head `ba3532ae` 五項全綠 |
| #1170 | 5 Issues × 6 PR 決策追溯對帳（單檔 docs） | `40d21c7f` | 獨立 QA ＋三輪 Delta PASS | 同 head `c3da97cb` 五項全綠 |
| #1172 | 資料 PR 證據缺口 G-01～G-17／決策順序 DPE-1～DPE-7 | `57885e6e` | 獨立 QA ＋Delta PASS | 同 head `35bfc002` 五項全綠 |
| #1173 | 🗂 資料新鮮度總覽三方案文字線框 A／B／C（AI 推薦 A，展開層沿用 B；候選 C-1～C-17） | `76ed4b7b` | 獨立 QA ＋Delta PASS with fixes（小缺已記 BACKLOG） | 同 head `8140a952` 五項全綠 |

**CI 證據更正（#1171）**：FACT——#1171 描述所列 6 個失敗 run 為預建 pip 26.3 後 bare `pip` exit 127、成功 26/26 為預建 26.2.2（#1171 描述自述，本組未全驗）；本組另重讀失敗 job 131230664848（run 43232345078，不在該 6 個 run 內＝第 7 個失敗樣本，即 ≥7）；#1171 修正生效後至少 2 個預建 pip 26.3 的 1.59.2 cell 成功：run 43232020099（job 131229652524，head `abc0ec38`）是 **#1171 PR 自身**的 CI（合併前）、run 43235464794（job 131241682819，#1170 分支，14:16Z 之後）才是**合併後**；兩 job 的預建 pip 版本，#1170 對帳底稿記為 26.3（轉述），本組因日誌代理限制未逐一讀到（**NOT VERIFIED**）；其後 #1172／#1173 head CI 全綠但**未逐 cell 讀 pip 版本，不得宣稱走過失敗路徑**。~~先前「runner image 分流」推測~~ 已被反證（失敗 job 131230664848 的 image 是 `20261111.127.1`，非 370.1；有意識的更正，不是漏刪）。**NOT VERIFIED**：偶發故障是否完全消失，需後續樣本。**取代**上段過期的 `pip exit 127`「待修／有效性」敘述。

### blocking issues

**無工程阻塞。** 全部下一步都卡在**待客戶裁示**（見下表）；沒有裁示時預設維持 HOLD、不動工。

### 唯一安全下一步

本同步 PR 合併後：**無客戶新裁示 → 停手，只做被動觀察**（看後續 PR 的 `ui2-browser` cell 有無再出 exit 127；看 #1124～#1126 是否仍 open）。**若客戶回覆** DPE／DG／wireframe 任一裁示，再**依該裁示範圍**辦理，且仍須 `CLAUDE.md` §-1、文字線框 Gate（UI 新 layout／欄位／文案）、非作者 QA、同 head CI。DEC-175／DEC-176 不是施工授權（DEC-176(c)）。

### 待客戶裁示清單（最少題數；附推薦者為 AI 推薦＝RECOMMENDATION，非客戶裁示；沒答的項目視為維持 HOLD）

1. **資料 PR #1124～#1126**（`DEC176-DATA-PR-EVIDENCE-DECISIONS`）：若考慮日後放行，**最少答 2 題＝DPE-3**（外部對帳是否牽涉資料來源使用條款；答「先確認條款」即算答）、**DPE-6**（貼 Streamlit Cloud 設定頁的 Repository／Branch／Main file，不貼 secrets）；本輪完全不考慮放行則可都不答。處置（合併／關閉）本身仍須客戶另行裁示——DEC-176(a) 只定「維持 HOLD」。
2. **🗂 資料新鮮度總覽文字線框**（白話：選 A／B／C 這類**版面方案**，不是資料裁示；`DEC176-FRESHNESS-WIREFRAME-PICK`）：選 A／B／C（AI 推薦 A）；並裁示 **C-16**、**C-17**、文件 §10 的 **①⑥⑦**。一鍵回覆格式見 `NEWUI2_DATA_FRESHNESS_OVERVIEW_TEXT_WIREFRAME_2026-11-12.md` §7.2。
3. **「完整資料健康度改派 🗂」上報點**（`DEC176-HEALTH-ESCALATION-1`，即上項 §10 ①）：撰寫組未找到明確改派裁示，不自行折衷。
4. **接線前決策單**（`DEC176-GATE-SHEET-CUSTOMER`）：`DATA_WIRING_GATE_DECISION_SHEET_2026-11-12.md` 的 `DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC`／`I1144-WIRING-GATE`；不答＝維持 HOLD。
5. 既有：`I1144-DATA-STORAGE-DECISION`／`I1144-LIC-THREE-QUESTIONS`（DEC-171）；Q5（DEC-173：是否及何時重議）。

### 禁止事項

無客戶指派不動工；不合併／關閉／rebase／改寫 #1124～#1126、#1164；不改舊 UI、不切預設 UI、不解除任何 Gate、不提前做 Actions Runs／Artifacts／死碼清理（刪除不可逆，屆時須客戶逐批明示）；不新增 API／MCP／fetcher／cron／Secrets／workflow 變更（降低 matrix／no-skip／gate 一律禁止）；不把 AI 推薦（含「推薦 A」）寫成客戶裁示；不把 CI 綠燈說成 Cloud／資料來源已驗證；每批最多三項、寫入序列化；不把 DEC-175／DEC-176 讀成開工指派。

### 先讀 SSOT 順序

`CLAUDE.md`（§-2、§-1.5.D、§1）→ `PROCESS.md` → `PROJECT_RULES.md`（§15、§20、§23；檔尾 DEC-175 索引與 DEC-176(c) 釐清）→ `docs/DECISIONS.md` DEC-176／DEC-175／DEC-174 → `docs/BACKLOG.md` 檔尾「DEC-176 結果同步」→ `docs/PROJECT_STATE.md` §70.13 → 本段；歷史接手點見 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md`。

### 風險

(1) DEC-176 fence 與客戶原訊息的逐字一致性 NOT VERIFIED，(a) 連逐字都沒有；(2) 各 PR 的 QA／CI 數字為轉述；(3) #1171 修正有效性 NOT VERIFIED，且 Fast／Slow job 的 bare `pip` 在預建 pip 26.3 image 上無樣本；(4) 資料 PR 長期不處理：台股卡持續落後，且若來源回補已入庫日期且值不同，發布腳本會中止、workflow 每日轉紅（#1169 調查 §5.1 方案 A 的風險，尚未發生）；(5) 11-21 `update_fundamentals` 直推 main 預期被保護擋下（INFERENCE）；(6) 本同步 PR 單組撰寫，未經第二組獨立複驗。

### 下一批候選（最多 3 項；僅候選，非授權；啟動仍須客戶指派，`CLAUDE.md` §-1）

1. **docs 微批**：處理 BACKLOG `DEC176-GAP-*` 八項小缺口——**不需客戶裁示**，但**仍需客戶下達指派**（DEC-176(c)：既有明確核准的工作不必重新請示，新工作仍需指派）；屬補丁，無指派不動。
2. **等待客戶對 wireframe／DG／DPE 的回覆**——**需客戶裁示**；回覆前不施工。
3. **CI 偶發被動觀察**（`DEC176-CI-1171-VALIDITY`）——**不需客戶裁示**；再出現 exit 127 才評估。

### 新對話接手提示語（可直接貼入新對話）

```
你接手 my-stock-dashboard（GitHub: linchen-20200325/my-stock-dashboard）。先做 GitHub-first 重核，不要信聊天摘要：
1. 取回 main 最新 SHA、Open／Draft PR（head／base／CI／review）；2. 讀 docs/DECISIONS.md 最新 DEC（目前 DEC-176）；3. 讀 docs/HANDOFF.md 檔尾最新「接手點」段（十五欄 Resume Checkpoint）；4. 再讀 CLAUDE.md（§-2、§-1.5.D、§1）、PROCESS.md、PROJECT_RULES.md（§20）。
不得把舊 HANDOFF 段落或聊天摘要當最新事實；舊段已過期的敘述以刪除線標示。HANDOFF 不是完成證明。
HOLD／禁止（全部未解除）：#1124～#1126 資料 PR（不合併／關閉／rebase）、#1164、#1119；DG-COV／DG-PIT／DG-LIC／DG-SCOPE、I1144-WIRING-GATE、G-F2～G-F6、Digest A3、market.health、外資 L3、Q5；不改舊 UI、不切預設 UI、不提前清理 Actions Runs／Artifacts／死碼；不新增 API／cron／Secrets；不降低 CI matrix／no-skip／ui2-browser-gate。
權限邊界：DEC-175 與 DEC-176 都不是無條件 UI／資料施工授權，不解除 CLAUDE.md §-1、文字線框 Gate、資料接線 Gate、獨立 QA、CI；既有明確核准的工作可依已批准範圍繼續，不必重新請示。
新 UI layout／欄位／文案先出文字線框等客戶拍板；每批最多三項；作者不自行合併，須非作者獨立 QA＋同 head 五項原生 CI。
AI 推薦（如「推薦 A」）不是客戶裁示；FACT／INFERENCE／NOT VERIFIED 要分開寫；CI 綠不等於 Cloud／資料來源已驗證。
未合併 PR（以最新 GitHub 為準，head 會變）：#1164 `6fddc582`（Draft）、#1124 `fc447def`、#1125 `1efb178a`、#1126 `428258b3`——全部不碰。
Model／Mode／Effort（客戶最新派工訊息指定，經轉錄、逐字 NOT VERIFIED；PROJECT_RULES 第 9 節）：Claude Sonnet 5.5／Mode：靜默自主巡航／Effort：High；現行值只以 HANDOFF 最新 Resume Checkpoint 為準。
沒有客戶新指派時：停手，只做被動觀察，並回報目前狀態與待客戶裁示清單。
```

- **仍 NOT VERIFIED**：PIT、cron 成功率（台股缺 11-11 原因）、來源授權原文、Cloud／真機／Real 軸量測、Streamlit Cloud 追蹤分支、部署端市場位階實況、「V1 CSV」來源、ETF Managers 2026-11-16 20:00 UTC 首次排程、DEC-175／DEC-176 fence 逐字一致性。本段單組撰寫，未經第二組驗證。


## 2026-11-12｜六處差異收尾後最新接手點（只追加；非 QA PASS；~~本段為現行有效接手點~~〔已被檔尾 2026-11-12「DEC-177 登錄後」短段取代（有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）〕）

> **取代關係**：本段取代上方「2026-11-12｜Batch 3 同步後最新接手點」（`docs/HANDOFF.md` 第 517 行起，撰寫時 main `85c65dfc` 的行號，僅供定位）的現況效力（有意識的更新，不是漏刪；2026-11-12；決策者 AI 總管〔事實更新〕）。**該段（含其 Resume Checkpoint 表 `:525`～`:539` 各欄的「Draft／待 QA／待合併」敘述、時間戳 `2026-11-12T16:07:07Z`、main 欄 `76ed4b7b`、分支 `docs/ssot-sync-batch3-20261112`、current PR 欄「#1174（Draft）」、「已完成」表缺 #1174）皆為 #1174 合併前的時點快照，已過期**；該段標題中的「本段為現行有效接手點」已就地以刪除線標示（同一行內、原文保留）。GitHub 操作事實優先於本段；接手前先做 LIVE GitHub Verification Gate。**不另建第二份 handoff**（`PROJECT_RULES.md` §20.1）。本段不重複 BACKLOG／DECISIONS 全文，細項見指標。 **另：標題的「六」為派工用詞，與下方處置表的列數無對應。**
> **單組聲明**：本段與本 PR 的四檔同步為**單組作者撰寫，未經非作者獨立 QA**（`CLAUDE.md` §-2 規則 6）；不得被引用為「已 QA PASS」。**不是授權**；不解除任何 Gate／HOLD。

### Resume Checkpoint（`PROJECT_RULES.md` §20.2 十五欄；欄位名稱與上方 `:523` 表頭一致）

| 欄位（§20.2） | 內容（2026-11-12） |
|---|---|
| latest verified main SHA | `85c65dfcfc95abd34b9da3762fb2499200edc336`（#1174 squash 合併點；2026-11-12 `git fetch origin main` 實查，FACT；cron 與其他 PR 會推進 main，**一律重查**） |
| current working branch | `claude/stock-dashboard-handoff-sync-ulwq8s`（本同步 docs PR 的 head；合併後可為任何新分支） |
| current PR | 本 PR（號碼以 GitHub 為準；head＝上列分支者）。其餘 Open PR（各 PR 最後更新／fetched_at 約 2026-11-12 17:29–17:45Z 的**時點快照**，讀取時間以本段 checkpoint 為準，base 皆為 main `85c65dfc`〔#1164 除外，其 base 為 `7eb48d6c`〕，**cron 會推進，一律重查**）：**#1164**（REORG3C 歸檔，**Draft**，mergeable_state=`behind`，head `6fddc582`，base `7eb48d6c`）；資料 PR **#1124** head `3cd3f525c345327ef9f90b71b28f2e262202d5dd`（派工訊息所述 5 commits、PR 自述 fetched_at 17:29:27Z、check runs 0〔本組 MCP 重讀 0〕）、**#1125** head `cf4739c525052f38410d991eec24da83966f4738`（fetched_at 17:41:57Z）、**#1126** head `1654ae6096c31157417c0fe2731bb214d4a2b077`——三者皆 open、非 draft、mergeable_state=blocked（派工訊息所述）、**HOLD，皆不碰**。#1119 不在 Open PR 清單，僅為 HOLD 項目名稱 |
| current task / batch | **無進行中的客戶批次**；僅有本同步 PR＝總管派工的 docs-only 收尾（三個 Item：① #1169 複驗結論同步、② 76ed4b7b push CI 紅燈證據記錄、③ 其餘交接差異同步）。做完即停止擴張並回報 |
| completed in this batch | 見下方「已完成」表；本同步 PR 本身尚未合併 |
| exact current stopping point | 本 PR 三個 commit 已推送（作者不建立 PR，由總管建立）；待非作者獨立 QA 與同 head 原生 CI。**未做**：任何 UI／資料／workflow／測試變更；#1165 兩份文件的勘誤回寫；D6 測試修復 |
| next single action | 本 PR：非作者 QA＋同 head 五項原生 CI 全綠＋review threads＝0＋mergeable clean 後依 Auto-Ship Gate 判斷（作者不自行合併）。**合併後無客戶新裁示即停手，只做被動觀察**（見「唯一安全下一步」） |
| tests / CI 已完成 | 作者端本機：grep 命中這四檔（`HANDOFF`／`BACKLOG`／`DECISIONS`／`PROJECT_STATE`／`PROJECT_RULES`）的守衛測試與 `tests/test_sec_*` 系列等 17 檔實跑，結果見 PR 描述（作者端自查，**非 QA**）。各已合併 PR 的 QA／CI 見「已完成」表（轉述，未逐 PR 重讀 check runs） |
| tests / CI 尚未完成 | 本 PR 的非作者獨立 QA、同 head 原生 CI；#1169 複驗內事實的再驗；D6 紅燈的 CI 當次實例直接驗證 |
| unresolved true Stop Gates | #1119 HOLD；#1124～#1126 HOLD（客戶 DEC-176(a) 方案 A；非合併授權）；#1164 HOLD；`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、`I1144-DATA-STORAGE-DECISION`、`I1144-DG-A3`、`I1144-DG-HEALTH`、外資 L3、G-F2～G-F6、`REORG3C-Q5-GATE`、Old UI Removal Gate、預設 UI 切換（全部未動；本 PR 未解除任何一項）。**VG1／VG2 是 Visual Gate 候選，不是 Stop Gate**，但列入待客戶裁示清單 |
| 是否存在 uncommitted / unpushed work | 否（本 PR 推送後；以 `git status`／GitHub 實查為準） |
| relevant evidence location | `docs/DECISIONS.md` 檔尾兩小節「DEC-174／DEC-176 後續註記：#1169 獨立複驗結論的有效讀法」「後續註記：76ed4b7b push CI 紅燈證據」；`docs/BACKLOG.md` 檔尾（#1169 勘誤指標、`DEC176-REVERIFY-R1R5-CANDIDATES`、`DEC176-CI-D6-NOSECRET-ID-NONDETERMINISM`、REORG3C 進度追加、`DEC176-DPE7-1119-CHECKPOINT`、`DEC176-VG1-VG2-PENDING-TRACK`）；`docs/PROJECT_STATE.md` §70.14；`docs/vnext/NEWUI2_INDEPENDENT_REVERIFICATION_2026-11-12.md`、`NEWUI2_DATA_FRESHNESS_OVERVIEW_TEXT_WIREFRAME_2026-11-12.md`、`DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md`、`DAILY_DATA_PR_PIT_CRON_INVESTIGATION_2026-11-12.md` |
| recommended Model | Claude Sonnet 5.5（沿用上段所載客戶派工訊息指定；經派工訊息轉錄，逐字 NOT VERIFIED；**現行值只維護於此處**） |
| recommended Effort | High；Mode：靜默自主巡航（沿用上段所載客戶派工訊息指定；經派工訊息轉錄，逐字 NOT VERIFIED；**現行值只維護於此處**） |
| last checkpoint timestamp | 2026-11-12T22:01:33Z（`date -u` 實查；PR 推送前最後查核） |

### 已完成（FACT 除另註；QA／CI 為合併提交訊息與派工訊息自述，**本組未逐 PR 重讀 check runs**）

| PR／commit | 內容 | merge／commit SHA | 非作者 QA | 同 head 原生 CI |
|---|---|---|---|---|
| #1165～#1173 | 見上方「Batch 3 同步後最新接手點」段的「已完成」表（含 #1173 `76ed4b7b`） | 見該表 | 見該表 | 見該表 |
| #1174 | DEC-176 登錄與五檔同步（Batch 3 SSOT 同步） | `85c65dfc`（head `e589be3b`；GitHub MCP 重讀：2026-11-12T17:02:54Z squash 合併，FACT） | 獨立 QA ＋兩輪 Delta PASS（提交訊息自述） | 同 head `e589be3b` 五項全綠（提交訊息自述）；main push run 43265246088 success（本組 MCP 重讀 run 層級） |
| 本 PR commit 1 | #1169 複驗結論有效讀法：DECISIONS 小節、BACKLOG 勘誤指標＋`DEC176-REVERIFY-R1R5-CANDIDATES`、PROJECT_STATE §70.14.1 | `0e2bf37d`（分支上；squash 後以 main 為準） | 未做（本 PR 待 QA） | 未做 |
| 本 PR commit 2 | 76ed4b7b push CI 紅燈證據：DECISIONS 小節、BACKLOG `DEC176-CI-D6-NOSECRET-ID-NONDETERMINISM`、PROJECT_STATE §70.14.2 | `22e313c9`（同上） | 未做 | 未做 |
| 本 PR commit 3 | 其餘交接差異同步（本段、BACKLOG 進度追加與新列、PROJECT_STATE §70.14.3） | 本段所在 commit（SHA 以 `git log` 為準） | 未做 | 未做 |

### 六處差異處置表（「①②③」＝本批三個 Item；「a～g」＝Item 3 內的七個子項；**此對映為撰寫組的解讀，總管若另有定義請更正**）

| 項 | 差異 | 處置 | 狀態 |
|---|---|---|---|
| ① | #1169 複驗結論未同步到 DECISIONS／BACKLOG／PROJECT_STATE | 檔尾追加有效讀法與勘誤指標（E-1～E-13、R1～R5、B1、N-1 部分推翻）；#1165 兩份文件本身**不改** | 已記錄（單組；未經 QA）。#1165 文件回寫勘誤＝待總管／客戶 |
| ② | main push `76ed4b7b` PR Check 紅燈 | 記錄證據與口徑（高度可能為測試偵測器非決定性缺陷，**未直接驗證**），不修 | 已記錄；修測試＝待客戶另案授權 |
| ③ | 其餘交接差異 | 見下 a～g | 見下 |
| a | 資料 PR 最新 head 與 HANDOFF 舊 head（`fc447def`／`1efb178a`／`428258b3`）不一致；三個資料 PR 各「3 個提交」（`DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md` §1 第 1 點約第 21 行、資料 PR 現況表約第 37 行；行號為撰寫時 main `85c65dfc`，僅供定位）已過期（現 5 commits，派工訊息所述） | 本段 Resume Checkpoint 記時點快照；`docs/vnext/` 文件已標「開工時實取」屬時點快照，**不改** | 已記錄（時點快照，cron 會推進） |
| b | HANDOFF 檔尾段停在 #1174 合併前；BACKLOG 背景段與 PROJECT_STATE 基準停在 `76ed4b7b` | 本段取代；舊段標題以刪除線標示；BACKLOG／PROJECT_STATE 以檔尾追加更新基準 | 已修（以追加方式） |
| c | REORG3C 三列（`REORG3C-REF-SYNC`／`REORG3C-SEC3-HEADER`／`REORG3C-DEC092-L309-MOVE`）進度未記 | BACKLOG 檔尾追加進度註記（不改原列）；REF-SYNC 剩餘舊引用是否已處理 | 已記錄；**剩餘舊引用 NOT VERIFIED** |
| d | PROJECT_STATE §70.13 基準 main 過期一個 commit | §70.14.3 追加基準更新（#1174 docs-only，未改 §70.13 所述 UI2／資料層事實） | 已記錄 |
| e | DPE-7 的 11-19 提早決定檢查點只在 `docs/vnext/` 文件，BACKLOG／HANDOFF 十五欄沒有 | BACKLOG 新列 `DEC176-DPE7-1119-CHECKPOINT`；本段待客戶裁示清單列入 | 已記錄（11-19 是 AI 推薦的檢查點，**非客戶裁示**；不答＝維持 A） |
| f | VG1／VG2 未列入待客戶裁示清單 | BACKLOG 新列 `DEC176-VG1-VG2-PENDING-TRACK`；本段待客戶裁示清單列入 | 已記錄 |
| g | 使用者點名仍待客戶正式選擇的項目（🗂 A／B／C、C-16、C-17、§10 ①⑥⑦） | 本段待客戶裁示清單如實列出（已讀 `NEWUI2_DATA_FRESHNESS_OVERVIEW_TEXT_WIREFRAME_2026-11-12.md` 確認各編號所指） | 已記錄；**AI 推薦 A ≠ 客戶核准** |

### blocking issues

**無工程阻塞。** 所有施工類下一步都卡在**待客戶裁示**（見下表）；沒有裁示時預設維持 HOLD、不動工。

### 唯一安全下一步

本同步 PR 合併後：**無客戶新裁示 → 停手，只做被動觀察**（看後續 PR 的 `ui2-browser` cell 有無再出 exit 127；看 main push CI 有無再出 D6 紅燈〔紅燈時先看失敗片段是否在元素 ID 內，**rerun 通過不等於已修**〕；看 #1124～#1126 是否仍 open；11-21 `update_fundamentals` 的實際結果）。**若客戶回覆**任一裁示，再**依該裁示範圍**辦理，且仍須 `CLAUDE.md` §-1、文字線框 Gate（UI 新 layout／欄位／文案）、非作者 QA、同 head CI。DEC-175／DEC-176 不是施工授權（DEC-176(c)）。

### 待客戶裁示清單（附推薦者為 AI 推薦＝RECOMMENDATION，非客戶裁示；沒答的項目視為維持 HOLD）

1. **🗂 資料新鮮度總覽 A／B／C**（`DEC176-FRESHNESS-WIREFRAME-PICK`）：選 A／B／C／A首屏＋B展開層／其他。**AI 推薦 A（展開層沿用 B）＝RECOMMENDATION，不是客戶核准**。出處：`NEWUI2_DATA_FRESHNESS_OVERVIEW_TEXT_WIREFRAME_2026-11-12.md`（#1173）§0、§7；一鍵回覆格式 §7.2。
2. **C-16**（B 案列順序：依 §1.2 固定清單順序，或改依 `data_categories` 分類 SSOT）、**C-17**（C 案「未載入」放進「需要注意」或另設「尚未檢查」區）。出處：同文件 §9 候選總表。
3. 同文件 **§10 ①**（完整資料健康度落點：👤 我的 或 🗂；撰寫組未找到明確改派裁示，不自行折衷；`DEC176-HEALTH-ESCALATION-1`）、**⑥**（方案 A 的 Level 1 逐項狀態在預設收合明細內：(a) 接受 A／(b) 明細預設展開／(c) 改採 B；AI 推薦 (a)）、**⑦**（本草案與 HANDOFF／五頁稽核 §11「需客戶先裁示」的張力，含是否占用 DEC-174「每批最多三項」名額）。§10 另有 ②③④⑤，非使用者本次點名項，本清單不展開。
4. **VG1／VG2**（`DEC174-VG1-FAKE-REAL-LOOK`／`DEC174-VG2-FAKE-ACCOUNT-CONFLICT`，P2、blocked-on-customer，追蹤 `DEC176-VG1-VG2-PENDING-TRACK`）：FAKE／Real 標示樣式、FAKE 👤 預設帳戶態衝突。Visual Gate 候選（不是 Stop Gate）；先文字線框＋推薦理由，客戶拍板前不寫 UI code。複驗 R4 併入 VG1。
5. **資料 PR #1124～#1126**（`DEC176-DATA-PR-EVIDENCE-DECISIONS`）：若考慮日後放行，最少答 **DPE-3**（外部對帳是否牽涉資料來源使用條款）、**DPE-6**（貼 Streamlit Cloud 設定頁的 Repository／Branch／Main file，不貼 secrets）；本輪完全不考慮放行則可都不答。處置（合併／關閉）本身仍須客戶另行裁示。
6. **DPE-7 的 11-19 檢查點**（`DEC176-DPE7-1119-CHECKPOINT`）：11-21 的 `update_fundamentals` 仍裸推 main、預期被分支保護擋下（INFERENCE）；`docs/vnext/DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md` DPE-7 現推薦 A（不處理、11-21 觀察），「11-19 前若客戶希望 11-21 的財報更新進 main，再改選 B（設計稿）」。**11-19 是 AI 推薦的提早決定檢查點，不是客戶裁示；不答＝維持 A（觀察）。**
7. **接線前決策單**（`DEC176-GATE-SHEET-CUSTOMER`）：`DATA_WIRING_GATE_DECISION_SHEET_2026-11-12.md` 的 `DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC`／`I1144-WIRING-GATE`；不答＝維持 HOLD。
8. **`DEC174-B1-INDEP-QA` 需總管／客戶指派**：#1169 複驗是單組產出，是否視為「非作者獨立 QA」由總管裁定；若要真正的非作者獨立 QA（含 R1～R5 渲染重現的再驗），啟動需客戶指派（DEC-174 每批最多三項）。連帶：**#1165 兩份文件是否回寫勘誤附註**、複驗 E-10（`READY` 標示）／E-13（Digest 查法）的處置，待總管／客戶。
9. **D6 測試偵測器缺陷是否修**（`DEC176-CI-D6-NOSECRET-ID-NONDETERMINISM`，P2）：需客戶另案授權才可修測試；方向＝掃描前正規化 `$$ID-<32hex>`，不得放寬禁字集。
10. 既有：`I1144-DATA-STORAGE-DECISION`／`I1144-LIC-THREE-QUESTIONS`（DEC-171）；Q5（DEC-173：是否及何時重議，`REORG3C-Q5-GATE`）。

### 禁止事項

無客戶指派不動工。**#1124～#1126 維持 HOLD：不合併、不關閉、不 rebase**；**#1164 不擅自處置**（不 rebase、不評論、不動 branch）；**不清理 `.claude/worktrees/`**（含一個有 5 個 staged changes 的舊 worktree——該 worktree 不在本容器，**未從此處驗證**）；不刪來源未確認的遠端分支；不改舊 UI、不切預設 UI；不改 UI／資料來源／DB 結構／cron／Secrets／OneBrain／Risk Cap／投資公式；**不解除 `DG-SCOPE`／`DG-LIC`／`DG-PIT`／`DG-COV` 或 `I1144-WIRING-GATE`**；**不執行 Actions 歷史清理**（Runs／Artifacts 刪除不可逆，屆時須客戶逐批明示）與死碼清理；不新增 API／MCP／fetcher／cron／Secrets／workflow 變更（降低 matrix／no-skip／`ui2-browser-gate` 一律禁止）；不改 `CLAUDE.md`／`PROCESS.md`／`PROJECT_RULES.md`；不把 AI 推薦（含「推薦 A」「11-19 檢查點」）寫成客戶裁示；不把 CI 綠燈說成 Cloud／資料來源已驗證；不把 DEC-175／DEC-176 讀成開工指派；每批最多三項、寫入序列化。

### 先讀 SSOT 順序

`CLAUDE.md`（§-2、§-1.5.D、§1）→ `PROCESS.md` → `PROJECT_RULES.md`（§15、§20、§23）→ `docs/DECISIONS.md`（DEC-176／DEC-175／DEC-174 與檔尾兩小節）→ `docs/BACKLOG.md` 檔尾（由「DEC-176 結果同步」起往下）→ `docs/PROJECT_STATE.md` §70.13～§70.14 → 本段；歷史接手點見 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md`。

### 風險

(1) 本 PR 單組作者撰寫，未經非作者獨立 QA；(2) #1169 複驗內事實（含紅隊渲染重現）未被再次重驗，且 #1165 兩份文件仍含被修正措辭（本批不改）；(3) D6 紅燈機制為兩組調查一致的推論，**CI 當次實例未直接驗證**，且「其他測試是否有同類缺陷」未掃——每個跑到該測試檔的 pytest 行程（PR CI 與 main push 的 fast lane 都會跑到該檔）約有 0.54～0.63% 機率再出紅燈（機率為調查組估算，兩組自算一致，本組未重算），rerun 通過不等於已修；(4) concurrency `cancel-in-progress: true` 使連續 push 的前一個 push run 可能被取消，push CI 不一定完整；(5) #1171 修正有效性仍 NOT VERIFIED；(6) 資料 PR 長期不處理：台股卡持續落後；11-21 `update_fundamentals` 直推 main 預期被保護擋下（INFERENCE）；(7) 資料 PR head 為各 PR 最後更新／fetched_at 約 17:29–17:45Z 的時點快照（讀取時間以本段 checkpoint 為準），cron 會推進，一律重查；(8) DEC-176 fence 與客戶原訊息逐字一致性 NOT VERIFIED。

### 下一批候選（最多 3 項；僅候選，**需客戶指派，非授權**；啟動仍須客戶指派，`CLAUDE.md` §-1）

> 方向：回到 **UI 與資料契約雙軌**（DEC-174／DEC-175），每批最多三項。

1. **等待客戶對 wireframe／DG／DPE／VG 的回覆**（上方清單 1～7）——需客戶裁示；回覆前不施工。
2. **docs 微批**：BACKLOG `DEC176-GAP-*` 八項小缺口＋#1165 兩份文件勘誤附註回寫（若客戶／總管同意）——不需新裁示，但需客戶下達指派。
3. **被動觀察**（`DEC176-CI-1171-VALIDITY`、`DEC176-CI-D6-NOSECRET-ID-NONDETERMINISM`、11-21 `update_fundamentals`）——不需客戶裁示；再出現才評估。

### 新對話接手提示語（可直接貼入新對話）

```
你接手 my-stock-dashboard（GitHub: linchen-20200325/my-stock-dashboard）。先做 GitHub-first 重核，不要信聊天摘要：
1. 取回 main 最新 SHA、Open／Draft PR（head／base／CI／review）；2. 讀 docs/DECISIONS.md 最新 DEC（目前 DEC-176，檔尾另有兩則只追加後續註記）；3. 讀 docs/HANDOFF.md 檔尾最新「接手點」段（十五欄 Resume Checkpoint；以標題「六處差異收尾後最新接手點」為準，其上各 2026-11-12 接手點段為過期時點快照）；4. 再讀 CLAUDE.md（§-2、§-1.5.D、§1）、PROCESS.md、PROJECT_RULES.md（§20）。
不得把舊 HANDOFF 段落或聊天摘要當最新事實；舊段已過期的敘述以刪除線標示。HANDOFF 不是完成證明。
HOLD／禁止（全部未解除）：#1124～#1126 資料 PR（不合併／關閉／rebase）、#1164（不擅自處置）、#1119；DG-COV／DG-PIT／DG-LIC／DG-SCOPE、I1144-WIRING-GATE、G-F2～G-F6、Digest A3、market.health、外資 L3、Q5；不改舊 UI、不切預設 UI、不清理 .claude/worktrees/、不提前清理 Actions Runs／Artifacts／死碼；不新增 API／cron／Secrets；不降低 CI matrix／no-skip／ui2-browser-gate。
權限邊界：DEC-175 與 DEC-176 都不是無條件 UI／資料施工授權，不解除 CLAUDE.md §-1、文字線框 Gate、資料接線 Gate、獨立 QA、CI；既有明確核准的工作可依已批准範圍繼續，不必重新請示。
新 UI layout／欄位／文案先出文字線框等客戶拍板；每批最多三項；作者不自行合併，須非作者獨立 QA＋同 head 五項原生 CI。
AI 推薦（如「推薦 A」「DPE-7 11-19 檢查點」）不是客戶裁示；FACT／INFERENCE／NOT VERIFIED 要分開寫；CI 綠不等於 Cloud／資料來源已驗證；#1169 複驗是單組產出，不等於 DEC174-B1-INDEP-QA 結案；D6 紅燈「高度可能為測試偵測器非決定性缺陷」未被直接驗證，不得記為已證實的偶發誤報，rerun 通過不等於已修。
未合併 PR 的 head 是各 PR 最後更新／fetched_at 約 2026-11-12 17:29–17:45Z 的時點快照（讀取時間以本段 checkpoint 為準），cron 會推進，一律以最新 GitHub 為準：#1164 6fddc582（Draft）、#1124 3cd3f525、#1125 cf4739c5、#1126 1654ae60——全部不碰。
Model／Mode／Effort（客戶派工訊息指定，經轉錄、逐字 NOT VERIFIED；PROJECT_RULES 第 9 節）：Claude Sonnet 5.5／Mode：靜默自主巡航／Effort：High；現行值只以 HANDOFF 檔尾最新 Resume Checkpoint 為準。
沒有客戶新指派時：停手，只做被動觀察，並回報目前狀態與待客戶裁示清單。
```

- **仍 NOT VERIFIED**：PIT、cron 成功率（台股缺 11-11 原因）、來源授權原文、Cloud／真機／Real 軸量測、Streamlit Cloud 追蹤分支、部署端市場位階實況、D6 紅燈 CI 當次實例、REORG3C-REF-SYNC 剩餘舊引用、`.claude/worktrees/` 舊 worktree 內容、DEC-175／DEC-176 fence 逐字一致性。本段單組撰寫，未經第二組驗證。


## 2026-11-12｜DEC-177 登錄後（~~現行有效接手點~~〔已被檔尾 2026-11-13「UI 實作前調查與裁示單提交後最新接手點」取代（有意識的更新，不是漏刪；2026-11-13；決策者 AI 總管〔事實更新〕）〕；只追加；非 QA PASS；15 欄 Resume Checkpoint 於下方）

> 本段取代上方「六處差異收尾後最新接手點」的現況效力（該段標題已就地以刪除線標示；有意識的更新，不是漏刪）。15 欄 Resume Checkpoint 見本段下方「Resume Checkpoint」表（`PROJECT_RULES.md` §20.2）；細項見 `docs/DECISIONS.md` DEC-177、`docs/BACKLOG.md` 檔尾「DEC-177 登記」、`PROJECT_RULES.md` 第 33 節。GitHub 實況優先於本段；接手前先做 LIVE GitHub Verification Gate（`PROJECT_RULES.md` 第 32 節）。**單組撰寫；本段所在 PR（#1176）兩組非作者 QA 已回報 PASS with fixes，修正於後續 commit，QA 複驗與同 head 原生 CI 仍待完成。不是授權。**
> **PROJECT_RULES 落點**：本 PR 修改 `PROJECT_RULES.md` 的落點為撰寫組依該檔為永久規則 SSOT 的角色所選，客戶訊息二.1 只要求「以獨立 docs PR 記錄…預防性交接制度」，未逐字點名檔案；#1175 時期 HANDOFF 的「不改 `PROJECT_RULES.md`」為該批範圍限制，不適用本批。
> **新對話接手提示語改指本段**：上一段「六處差異收尾後最新接手點」內「新對話接手提示語」中「以標題『六處差異收尾後最新接手點』為準」的指引**已過期**，改指本段（標題「DEC-177 登錄後」）；新提示語見本段末。

### Resume Checkpoint（`PROJECT_RULES.md` §20.2 十五欄；欄位名稱與次序與上方「六處差異收尾後最新接手點」表頭一致）

| 欄位（§20.2） | 內容（2026-11-12） |
|---|---|
| latest verified main SHA | `880bc17c784ad8ec2ac674bf52f8b98929786304`（#1175 squash 合併點；2026-11-12 `git fetch origin main` 實查，FACT；cron 與其他 PR 會推進 main，**一律重查**） |
| current working branch | `claude/stock-dashboard-handoff-sync-ulwq8s`（本 docs PR 的 head；合併後可為任何新分支） |
| current PR | **#1176**（本 docs PR「A」，head＝上列分支；非 Draft 與否以 GitHub 為準）。其餘 Open PR（2026-11-12 GitHub MCP 實查，時點快照）：**#1164**（Draft，head `6fddc582`，HOLD）；資料 PR **#1124**（head `3cd3f525`）、**#1125**（head `cf4739c5`）、**#1126**（head `1654ae60`），皆 HOLD；cron 會推進，一律重查 |
| current task / batch | 客戶 2026-11-12「UI 主線恢復與預防性交接制度」（DEC-177）本批三項：① 獨立 docs PR（本 PR）；② 最小 UI 第一版實作（尚未開始）；③ 非作者 QA／同 head CI／手機首屏與缺值語意驗收＋收尾同步（尚未開始）。依序進行，不得多組同時寫同一治理文件 |
| completed in this batch | DEC-177 登錄（DECISIONS）、`PROJECT_RULES.md` 第 33 節、BACKLOG 三列、本段；見下方「已完成」表。本 PR 尚未合併 |
| exact current stopping point | 本 PR 已推送，兩組非作者 QA 回報 PASS with fixes，修正 commit 已推送；待 QA 複驗與同 head 五項原生 CI。**未做**：任何 UI／資料／workflow／測試變更；最小 UI 第一版的前置調查（`SHOWN_FOLDS`／UI 契約／測試 allowlist 是否需突破） |
| next single action | 本 PR：QA 複驗＋同 head 五項原生 CI 全綠＋review threads＝0＋mergeable clean 後依 Auto-Ship Gate 判斷（作者不自行合併）。**合併後**：調查確認 `DEC177-UI-DATA-FRESHNESS-OVERVIEW-V1` 是否需要突破白名單／契約／allowlist；結論出來前不寫 UI code。無客戶新裁示則不做其他事 |
| tests / CI 已完成 | #1175 已合併，其 main push CI run 43325022430（event=push、head `880bc17c`）conclusion＝success（2026-11-12 GitHub MCP 重讀 run 層級，FACT；未逐 job 展開）。本 PR 作者端：grep 命中四份治理文件名稱的 6 個測試檔（`test_batch_z60`、`test_p02_find_v2_cards`、`test_p04_hold_v2_cards`、`test_ui2_active_contract_docs`、`test_ui2_contract_teeth_pending`、`test_ui2_p1_human_text`）實跑 3232 passed、6 skipped、1 deselected、3 xfailed（作者端自查，**非 QA**；修正 commit 後已重跑，結果見 PR 描述／後續回報） |
| tests / CI 尚未完成 | 本 PR 的非作者 QA 複驗、同 head 五項原生 CI；D6 紅燈偶發機率（約 0.5～0.6%）依舊存在，rerun 通過不等於已修；最小 UI 實作的 QA／CI（尚未開始） |
| unresolved true Stop Gates | #1119 HOLD；#1124～#1126 HOLD；#1164 HOLD；`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、`I1144-DATA-STORAGE-DECISION`、`I1144-DG-A3`、`I1144-DG-HEALTH`、外資 L3、G-F2～G-F6、`REORG3C-Q5-GATE`、Old UI Removal Gate、預設 UI 切換（全部未動；本 PR 未解除任何一項）。VG1／VG2 是 Visual Gate 候選，不是 Stop Gate |
| 是否存在 uncommitted / unpushed work | 以 `git status` 實查為準：撰寫本段時，修正內容於本 commit 提交並推送後為「否」（若讀到此段時分支落後或有新 commit，請重查） |
| relevant evidence location | `docs/DECISIONS.md` DEC-177（檔尾）；`PROJECT_RULES.md` 第 33 節；`docs/BACKLOG.md` 檔尾「DEC-177 登記」；`docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_TEXT_WIREFRAME_2026-11-12.md`；`docs/vnext/DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md`；`docs/vnext/DATA_WIRING_GATE_DECISION_SHEET_2026-11-12.md`；歷史接手點 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md` |
| recommended Model | Sonnet 5.5（依客戶本次訊息；經派工訊息轉錄，逐字 NOT VERIFIED；**現行值只維護於此處**） |
| recommended Effort | High；Mode：靜默自主巡航（依客戶本次訊息；**現行值只維護於此處**） |
| last checkpoint timestamp | 2026-11-12T23:47:13Z（`date -u` 實查；本 commit 撰寫時） |

### 已完成（FACT 除另註）

| PR／commit | 內容 | merge／commit SHA | 非作者 QA | 同 head 原生 CI |
|---|---|---|---|---|
| #1175 | 六處交接差異收尾（#1169 複驗有效讀法、76ed4b7b CI 紅燈證據、HANDOFF／BACKLOG／PROJECT_STATE 基準同步） | `880bc17c`（main） | 獨立 QA 兩組＋Delta（提交訊息自述） | 同 head `6e4dfc16` 五項全綠（提交訊息自述）；main push run 43325022430 success（本組 MCP 重讀 run 層級） |
| #1176（本 PR，commit `57d3bfdc` 及其後修正 commit） | DEC-177 登錄、`PROJECT_RULES.md` 第 33 節、BACKLOG 三列、HANDOFF 本段 | 未合併 | 兩組非作者 QA 回報 PASS with fixes（總管轉述）；修正後複驗待做 | 待同 head 五項原生 CI |
| DEC-177 | 客戶 2026-11-12 UI 主線恢復與預防性交接制度裁示轉錄（fence sha256 `8b059bb5…`） | 隨 #1176 | 同上 | 同上 |

### 摘要與待辦（補充；與上表並讀）

- **main**：`880bc17c`（#1175 squash；2026-11-12 本組 `git fetch origin main` 實查；**時點快照，會漂移，一律重查**）。DEC-177 所在 docs PR 合併後 main 會前進。
- **Open PR（2026-11-12 GitHub MCP 實查，時點快照）**：#1164（Draft，REORG3C DEC092 歸檔，head `6fddc582`，HOLD）；#1124／#1125／#1126（每日資料 PR，head 各自推進，HOLD）。
- **本批三項狀態（客戶 2026-11-12 DEC-177「二」）**：① 獨立 docs PR（記錄 UI 方向、授權邊界、預防性交接制度）＝**本 PR（A），待非作者 QA 與同 head 五項原生 CI，未合併**；② 最小 UI 第一版實作＝**尚未開始**；③ 非作者 QA／同 head CI／手機首屏與缺值語意驗收＋同步收尾＝**尚未開始**。
- **已裁示（DEC-177）**：🗂 資料新鮮度總覽採 **A 首屏＋B 展開明細**（八項固定清單與既有順序；首屏顯示已接入／尚未接線／五態計數含 0；明細預設收合；只用既有資料日與距今天數、不新增 `fetched_at`／`published_at`；保留授權與發布時點「未知／未評估」說明；保留手機首屏四問與主 CTA；完整資料健康度仍在 👤 我的、不搬入口；C-16 採既有固定順序、C-17 不適用；§10 ⑥ 採 (a)；§10 ⑦ 確認為本次明確派工）。允許依核准線框做**最小 UI 第一版實作**，**不解除**資料接線、來源授權、PIT、Coverage、Old UI Removal、正式切換 Gate。**預防性交接制度**已登錄 `PROJECT_RULES.md` 第 33 節（「更早核准紀錄」NOT FOUND，依本次客戶訊息登錄）。
- **仍 HOLD**：#1124～#1126、#1164、#1119；`DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC`、`I1144-WIRING-GATE`；D6 偵測器程式修復（另批提案）；DPE-7 維持 A（觀察）、**11-19 檢查點**保留；Old UI、正式 UI 切換、資料庫重建、新 API／來源、Actions 清理；不清理 `.claude/worktrees/`。
- **待客戶裁示（A／B／C、C-16／C-17、§10 ⑥⑦ 已裁示，不再列；以下為仍待項，附推薦者為 AI 推薦＝RECOMMENDATION，非裁示；沒答＝維持 HOLD）**：(1) **`DEC177-SHOWN-FOLDS-QUESTION`**（條件式：UI 調查若確認第一版需新增 `SHOWN_FOLDS` 條目／UI 契約／測試 allowlist，須先提精確範圍與最小修改方案；**尚未確認是否需要**）；(2) **DPE-7**：客戶已定維持 A（觀察）；11-19 為保留之檢查點，僅在客戶想讓 11-21 財報進 main 時才需另答（`DEC176-DPE7-1119-CHECKPOINT`），不屬「仍待裁示」；(3) **VG1／VG2**（`DEC174-VG1-FAKE-REAL-LOOK`／`DEC174-VG2-FAKE-ACCOUNT-CONFLICT`）；(4) **DPE-3／DPE-6**（若日後考慮放行 #1124～#1126；`DEC176-DATA-PR-EVIDENCE-DECISIONS`）；(5) 接線前決策單 `DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC`／`I1144-WIRING-GATE`（`DEC176-GATE-SHEET-CUSTOMER`）；(6) `DEC174-B1-INDEP-QA` 判定與 #1165 勘誤附註回寫；(7) D6 偵測器是否修（`DEC176-CI-D6-NOSECRET-ID-NONDETERMINISM`，客戶已定為「另批提案」）；(8) `I1144-DATA-STORAGE-DECISION`／`I1144-LIC-THREE-QUESTIONS`、Q5（`REORG3C-Q5-GATE`）。（此清單由 HANDOFF 前一段「待客戶裁示清單」扣除已裁示項目整理，**單組核對，非窮舉宣稱**；`DEC176-HEALTH-ESCALATION-1` 的結案與否由總管判定。）
- **下一個唯一安全動作**（AI 排序，沿客戶「依序進行」；客戶原文允許在不突破 Gate 的範圍直接最小實作，是否有此範圍由調查決定）：本 docs PR 通過非作者 QA、同 head 五項原生 CI 並合併後，由**調查**確認 `DEC177-UI-DATA-FRESHNESS-OVERVIEW-V1` 第一版是否需要突破 `SHOWN_FOLDS`／UI 契約／測試 allowlist。**調查結論出來之前不得寫 UI code。** 不需要突破 → 依核准線框做最小實作；需要 → 停在安全點、提裁示單。
- **先讀 SSOT 順序**：`CLAUDE.md`（§-2、§-1.5.D、§1）→ `PROCESS.md` → `PROJECT_RULES.md`（§15、§20、§32、§33）→ `docs/DECISIONS.md`（DEC-177、DEC-176、DEC-174）→ `docs/BACKLOG.md` 檔尾（「DEC-177 登記」）→ `docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_TEXT_WIREFRAME_2026-11-12.md`（§1.2、§2、§3、§4、§8、§9、§10）→ `docs/PROJECT_STATE.md` §70.13～§70.14（收尾 PR 才會更新 PROJECT_STATE）→ 本段；歷史接手點見 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md`。
- **NOT VERIFIED**：DEC-177 fence 與客戶原訊息的逐字一致性；預防性交接制度更早核准紀錄；`SHOWN_FOLDS` 是否必須新增條目；#1124～#1126 之 PIT／cron／授權；其餘同上一段。

### 新對話接手提示語（可直接貼入新對話；改指本段）

```
你接手 my-stock-dashboard（GitHub: linchen-20200325/my-stock-dashboard）。先做 GitHub-first 重核，不要信聊天摘要：
1. 取回 main 最新 SHA、Open／Draft PR（head／base／CI／review；含 #1176 是否已合併）；2. 讀 docs/DECISIONS.md 最新 DEC（目前 DEC-177，其上 DEC-176／175／174）；3. 讀 docs/HANDOFF.md 檔尾最新接手點段（標題「DEC-177 登錄後」，含十五欄 Resume Checkpoint；上一段「六處差異收尾後最新接手點」及其內舊提示語已過期，不要照舊提示語行事）；4. 再讀 CLAUDE.md（§-2、§-1.5.D、§1）、PROCESS.md、PROJECT_RULES.md（§20、§32、§33）。
客戶已裁示：🗂 資料新鮮度總覽採 A 首屏＋B 展開明細（DEC-177），允許依核准線框做最小 UI 第一版實作，但不解除資料接線、來源授權、PIT、Coverage、Old UI Removal、正式切換 Gate。若第一版需突破 SHOWN_FOLDS 白名單、UI 契約、測試 allowlist，先提精確範圍與最小修改方案、等客戶另行裁示，不得自行放寬；調查結論出來前不寫 UI code；不以 placeholder 冒充真資料。
HOLD／禁止（全部未解除）：#1124～#1126、#1164、#1119；DG-SCOPE／DG-COV／DG-PIT／DG-LIC、I1144-WIRING-GATE；D6 偵測器程式修復（另批提案）；DPE-7 維持 A（觀察），11 月 19 日為保留檢查點；Old UI、正式 UI 切換、資料庫重建、新 API／來源、Actions 清理；不清理 .claude/worktrees/。
每批最多三項；未授權的新工作不得自行啟動；作者不自行合併，須非作者獨立 QA＋同 head 五項原生 CI。預防性交接制度見 PROJECT_RULES 第 33 節：每批結束檢查交接風險，約三批或長篇 QA／CI、重大決策變動時優先安排安全交接；先寫入 GitHub 並驗證，才結束舊對話；Agent 進度回報最小化。
AI 推薦不是客戶裁示；FACT／INFERENCE／NOT VERIFIED 要分開寫；CI 綠不等於 Cloud／資料來源已驗證。
Model／Mode／Effort：Sonnet 5.5／Mode：靜默自主巡航／Effort：High（客戶訊息指定，經轉錄；現行值只以 HANDOFF 檔尾最新 Resume Checkpoint 為準）。
沒有客戶新指派時：停手，只做被動觀察，並回報目前狀態與待客戶裁示清單。
```


## 2026-11-13｜UI 實作前調查與裁示單提交後最新接手點（~~現行有效接手點~~〔已被檔尾 2026-11-13「Agents 批次後最新接手點」取代（有意識的更新，不是漏刪；2026-11-13；決策者 AI 總管〔事實更新〕）〕；只追加；非 QA PASS）

> **取代關係**：本段取代上方「2026-11-12｜DEC-177 登錄後」段的現況效力（該段標題已就地以刪除線標示；有意識的更新，不是漏刪）。**該段內的「新對話接手提示語」已過期，改指本段末的提示語**。GitHub 操作事實優先於本段；接手前先做 LIVE GitHub Verification Gate（`PROJECT_RULES.md` 第 32 節）。不另建第二份 handoff（`PROJECT_RULES.md` §20.1）。
> **單組聲明**：本段與本 PR 為**作者單組撰寫，未經非作者獨立 QA**（`CLAUDE.md` §-2 規則 6）；裁示單內的事實來自三組單組調查，作者另自行重核檔案行號並重跑複本實驗。**不是授權**；不解除任何 Gate／HOLD。AI 推薦（含決策單內全部「總管推薦」）一律是 RECOMMENDATION，不是客戶裁示。

### Resume Checkpoint（`PROJECT_RULES.md` §20.2 十五欄；欄位名稱與次序與上方 2026-11-12 各段表頭一致）

| 欄位（§20.2） | 內容（2026-11-13） |
|---|---|
| latest verified main SHA | `093b323d5f88ce5a1b590948fd7ebbb007131be6`（#1176 squash 合併點；2026-11-13 `git fetch origin main` 實查，FACT；cron 與其他 PR 會推進 main，**一律重查**） |
| current working branch | `claude/stock-dashboard-handoff-sync-ulwq8s`（本 docs PR「B」的 head；#1176 合併後遠端同名分支已刪除，本 PR 為重新推送；合併後可為任何新分支） |
| current PR | **#1177**＝本 docs PR「B」（head＝上列分支者）。其餘 Open PR（2026-11-13 GitHub MCP 實查，時點快照）：**#1164**（Draft，head `6fddc582`，HOLD）；資料 PR **#1124**（head `3cd3f525`）、**#1125**（head `cf4739c5`）、**#1126**（head `1654ae60`），皆 HOLD，cron 會推進，一律重查 |
| current task / batch | 客戶 2026-11-12 DEC-177 本批三項：① 獨立 docs PR＝**完成（#1176 已合併）**；② 最小 UI 第一版實作＝**停在安全點**（未改 `src/`、`tests/`；已提交裁示單 Q1～Q7）；③ 非作者 QA／同 head CI／手機首屏與缺值語意驗收＋同步＝本 PR 為其 docs 同步部分，UI 驗收部分隨 ② 未開始。依序進行，不得多組同時寫同一治理文件 |
| completed in this batch | #1176（DEC-177 登錄、`PROJECT_RULES.md` 第 33 節、BACKLOG 三列、HANDOFF 15 欄段）；本 PR：裁示單 `docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_IMPLEMENTATION_DECISION_SHEET_2026-11-13.md`、DECISIONS 檔尾後續註記、BACKLOG 檔尾追加、PROJECT_STATE §70.15、本段。見下方「已完成」表 |
| exact current stopping point | 實作前調查完成、裁示單已提交；**等客戶回覆 Q1～Q7**。本 PR 待非作者獨立 QA 與同 head 五項原生 CI。**未做**：任何 UI／資料／workflow／測試變更；`SHOWN_FOLDS`、`WIRED_PATHS`、詞彙守衛、viewport 證據、P3 基準一律未動 |
| next single action | 本 PR：非作者 QA＋同 head 五項原生 CI 全綠＋review threads＝0＋mergeable clean 後依 Auto-Ship Gate 判斷（作者不自行合併）。**合併後依第 33 節安全交接**；客戶回覆 Q1～Q7 前不寫 UI code（見下方「下一個唯一安全動作」） |
| tests / CI 已完成 | #1176 同 head `1af7976a` 五項原生 CI 全綠（總管訊息與 #1176 合併提交訊息自述，作者未逐項重讀 check runs）；#1175 main push CI run 43325022430 success（2026-11-13 GitHub MCP 重讀 run 層級）。本 PR 作者端：17 個 `tests/test_ui2_*.py` 基準 1705 passed、3 xfailed、41 deselected（複本實驗用；repo 工作樹未動）；grep 命中治理文件名稱的 6 個測試檔（`test_batch_z60`、`test_p02_find_v2_cards`、`test_p04_hold_v2_cards`、`test_ui2_active_contract_docs`、`test_ui2_contract_teeth_pending`、`test_ui2_p1_human_text`）作者端實跑 3232 passed、6 skipped、1 deselected、3 xfailed（作者端自查，**非 QA**；非作者 QA-B 另實跑 16 檔 `test_sec_*` 等 4651 passed；`test_batch_z59` 在缺 `markdown_it` 的 venv 為環境失敗、裝 markdown-it-py 後全綠〔QA-B 實跑，總管轉述〕；作者的 venv 同樣缺 `markdown_it`，該失敗與本 PR 無關） |
| tests / CI 尚未完成 | #1176 合併後 main push CI run 43334257638（head `093b323d`）撰寫時為 in_progress（2026-11-13 MCP 查），結果 **NOT VERIFIED**；本 PR 的非作者 QA 與同 head 五項原生 CI；D6 測試（`tests/test_d6_diagnostic_no_secret_display.py`）有已知約 0.54～0.63%（每個跑到該檔的 pytest 行程）的非決定性紅燈機率，rerun 通過不等於已修；最小 UI 實作的 QA／CI（尚未開始） |
| unresolved true Stop Gates | #1119 HOLD；#1124～#1126 HOLD；#1164 HOLD；`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、`I1144-DATA-STORAGE-DECISION`、`I1144-DG-A3`、`I1144-DG-HEALTH`、外資 L3、G-F2～G-F6、`REORG3C-Q5-GATE`、Old UI Removal Gate、預設 UI 切換（全部未動；本 PR 未解除任何一項）。Q1～Q7（`DEC177-FRESHNESS-IMPL-DECISION-SHEET`）是**實作 Gate**（blocked-on-customer）；VG1／VG2 是 Visual Gate 候選，不是 Stop Gate |
| 是否存在 uncommitted / unpushed work | 以 `git status`／GitHub 實查為準：本段撰寫時尚未提交；本 PR 推送後預期為「否」（若讀到此段時分支落後或有新 commit，請重查） |
| relevant evidence location | `docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_IMPLEMENTATION_DECISION_SHEET_2026-11-13.md`（裁示單；§5 複本實驗、§6.1 工程對照）；`docs/DECISIONS.md` DEC-177 與檔尾「DEC-177 後續註記：實作前調查結果」；`docs/BACKLOG.md` 檔尾「2026-11-13｜DEC-177 實作前調查與裁示單提交」；`docs/PROJECT_STATE.md` §70.15；`PROJECT_RULES.md` 第 33 節；線框 `docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_TEXT_WIREFRAME_2026-11-12.md`；歷史接手點 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md` |
| recommended Model | Sonnet 5.5（依客戶 2026-11-12 訊息；經派工訊息轉錄，逐字 NOT VERIFIED；**現行值只維護於此處**） |
| recommended Effort | High；Mode：靜默自主巡航（依客戶 2026-11-12 訊息；**現行值只維護於此處**） |
| last checkpoint timestamp | 2026-11-13T00:19:50Z（`date -u` 實查；本段撰寫時） |

### 已完成（FACT 除另註）

| PR／commit | 內容 | merge／commit SHA | 非作者 QA | 同 head 原生 CI |
|---|---|---|---|---|
| #1175 | 六處交接差異收尾 | `880bc17c`（main） | 獨立 QA 兩組＋Delta（提交訊息自述） | 同 head `6e4dfc16` 五項全綠（提交訊息自述）；main push run 43325022430 success（2026-11-13 MCP 重讀 run 層級） |
| #1176 | DEC-177 登錄（fence sha256 `8b059bb5…eae053`）、`PROJECT_RULES.md` 第 33 節、BACKLOG 三列、HANDOFF 15 欄段 | `093b323d`（2026-11-13T00:05:39Z squash；GitHub MCP 重讀 PR 狀態 merged，FACT） | 兩組非作者 QA 首輪 PASS with fixes（已修於 `1af7976a`）＋兩組 Delta PASS（PR 描述與合併提交訊息自述；作者未重讀 review 紀錄） | 同 head `1af7976a` 五項原生 CI 全綠、review threads 0（PR 描述與合併提交訊息自述）；其 main push run 43334257638 撰寫時 in_progress，**NOT VERIFIED** |
| 本 PR「B」 | 裁示單（Q1～Q7）、DECISIONS 後續註記、BACKLOG 追加列、PROJECT_STATE §70.15、本段 | 未合併 | 待 | 待 |

### 本批三項狀態

1. **獨立 docs PR（登錄 UI 方向、授權邊界、預防性交接制度）＝完成**（#1176 `093b323d`）。
2. **最小 UI 第一版實作＝停在安全點**：實作前調查發現完整「A 首屏＋B 收合明細」在不放寬既有守衛下做不出來（複本實驗：只追加無資料骨架〔方案 X〕全綠但無新鮮度資訊，**總管不建議**；多一列帶台股資料日〔方案 Y〕19 個測試紅，皆為「只有白名單欄位可帶資料」守衛）。**未改任何 `src/`、`tests/`**，已提交裁示單（Q1～Q7）。
3. **非作者 QA／同 head CI／手機首屏與缺值語意驗收＋同步**：docs 同步部分＝本 PR；UI 驗收部分待 ② 有實作後才有對象，**尚未開始**。

### 待客戶裁示（附推薦者為 AI 推薦＝RECOMMENDATION，非客戶裁示；沒答的項目視為維持 HOLD／現狀）

**A. 新增：🗂 資料新鮮度總覽實作裁示單（`DEC177-FRESHNESS-IMPL-DECISION-SHEET`）Q1～Q7**（可一行回覆「全部照總管推薦」；範本見裁示單 §0.1）：Q1 是否允許 🗂 頁出現帶真值的欄位（推薦 A 允許：在自動檢查的允許清單新增計數欄位〔階段 2 再加台股／位階兩列〕，並附反向驗證）；Q2 「尚未接線」字樣（推薦 B 改用既有「尚未提供」）；Q3 第一屏三問與舊區塊文字自相矛盾（推薦 A 有意識改寫，裁示單附擬議文案）；Q4 狀態符號（線框 ✅◷◇⛔ vs 現行全站字樣；**推薦 B 沿用現行全站字樣**——2026-11-13 修訂，原推薦 A：作者重現確認這組符號放進狀態欄位會被 `FieldVM`／`ALLOWED_STATUS_PREFIXES` 拒絕，A 的明細列需改共用契約）；Q5 規格缺口（推薦 A）；Q6 收合明細（推薦 C 分兩階段，先做 A 首屏）；Q7 線框文案候選 C-2／C-4 照線框原文（Q4＝B 時 C-4 的「正常」改為「資料日在規則內」，總管草擬待核可），C-7／C-8 階段 2 才定，C-9 不顯示。
**B. 仍待（前段清單扣除已裁示項目；單組核對，非窮舉宣稱）**：(1) **VG1／VG2**（`DEC174-VG1-FAKE-REAL-LOOK`／`DEC174-VG2-FAKE-ACCOUNT-CONFLICT`，Visual Gate 候選，先文字線框＋推薦理由）；(2) **DPE-3／DPE-6**（若日後考慮放行 #1124～#1126；`DEC176-DATA-PR-EVIDENCE-DECISIONS`；處置本身仍須另行裁示）；(3) 接線前決策單 `DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC`／`I1144-WIRING-GATE`（`DEC176-GATE-SHEET-CUSTOMER`）；(4) `DEC174-B1-INDEP-QA` 判定與 #1165 兩份文件勘誤附註回寫、複驗 E-10／E-13 的處置；(5) `I1144-DATA-STORAGE-DECISION`／`I1144-LIC-THREE-QUESTIONS`（DEC-171）；Q5（DEC-173，`REORG3C-Q5-GATE`）是否及何時重議。
**C. 已有客戶定論、不列為待裁示**：DPE-7 **維持 A（觀察）**，保留 **11 月 19 日檢查點**（`DEC176-DPE7-1119-CHECKPOINT`；僅在客戶想讓 11-21 `update_fundamentals` 財報進 main 時才需另答）；D6 偵測器程式修復＝**另批提案**（`DEC176-CI-D6-NOSECRET-ID-NONDETERMINISM`，客戶未授權修測試前不動）。

### 仍 HOLD

#1124～#1126（不合併／關閉／rebase）、#1164（不擅自處置）、#1119；`DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC`、`I1144-WIRING-GATE`；D6 偵測器程式修復（另批提案）；DPE-7 維持 A（觀察）＋11-19 檢查點保留；Old UI、正式 UI 切換、資料庫重建、新 API／來源、Actions 清理（Runs／Artifacts 刪除不可逆，屆時須客戶逐批明示）；不清理 `.claude/worktrees/`（含一個有 staged changes 的舊 worktree——不在本容器，**未從此處驗證**）；不改 `CLAUDE.md`／`PROCESS.md`；不降低 CI matrix／no-skip／`ui2-browser-gate`；不把 AI 推薦寫成客戶裁示；不把 DEC-175／DEC-176／DEC-177 讀成無條件開工指派。

### 風險

(1) 本 PR 與裁示單單組撰寫，未經非作者獨立 QA；(2) 裁示單事實來自三組單組調查，作者重核了檔案行號並重跑 X、Y 與收合區三個複本實驗，但**未重跑組 V 的 15 檔子集基準**；(3) 部署端位階是否恆 unloaded、viewport 證據能否重生（本沙箱無 Python Playwright）、真瀏覽器 390／1440 實際畫面均 NOT VERIFIED；(4) 階段 1 不動 `src/ui2/**` 是推測，實作時若需動即停手回報；(5) D6 測試約 0.54～0.63% 非決定性紅燈機率仍在，紅燈時先看失敗片段是否在元素 ID 內；(6) `concurrency: cancel-in-progress` 使連續 push 的前一個 push run 可能被取消；(7) 資料 PR 長期不處理：台股卡持續落後（自 2026-11-09）；11-21 `update_fundamentals` 直推 main 預期被保護擋下（INFERENCE）；(8) 未合併 PR head 為 2026-11-13 查詢時點快照，cron 會推進。

### 交接風險檢查（`PROJECT_RULES.md` 第 33 節）

本對話已累積多批（#1175、#1176、本 PR）、長篇 QA／CI 往返與重大決策變動（DEC-177、實作停在安全點、7 題裁示單）→ 依第 33 節「累積約三批或出現長篇 QA／CI、重大決策變動時優先安排安全交接」，**建議在本 PR 合併後安全交接**：先確認本 PR 內容已進 main 並驗證 main push CI、本段與裁示單已在 GitHub，**然後**才結束舊對話，再依 GitHub 最後狀態使用下方提示語開新對話。此為 AI 建議，不是硬性規則；不承諾能讀取剩餘上下文 Token。

### 下一個唯一安全動作

**客戶回覆 Q1～Q7 前不寫 UI code。** 客戶回覆後的第一步：依回覆範圍，以**獨立 PR**做階段 1（A 首屏；預期只動 `src/services/ui2/data_page.py`、`real_canonical.py` 與測試，不動 `src/ui2/**`），遵守寫入序列化、一次一模組、每個放寬附突變測試且不得全域放寬、非作者 QA、同 head 五項原生 CI；若實作中發現需動 `src/ui2/**`（會使 4 份 viewport 證據過期）或超出客戶回覆的範圍，**立即停手回報**。客戶無回覆時：停手，只做被動觀察。

### 先讀 SSOT 順序

`CLAUDE.md`（§-2、§-1.5.D、§1）→ `PROCESS.md` → `PROJECT_RULES.md`（§15、§20、§32、§33）→ `docs/DECISIONS.md`（DEC-177 與檔尾「DEC-177 後續註記」、DEC-176、DEC-174）→ **裁示單** `docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_IMPLEMENTATION_DECISION_SHEET_2026-11-13.md` → `docs/BACKLOG.md` 檔尾 → 線框 `docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_TEXT_WIREFRAME_2026-11-12.md` → `docs/PROJECT_STATE.md` §70.13～§70.15 → 本段；歷史接手點見 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md`。

### #1176 已知 Low 級瑕疵更正註記（有意識的更正，不是漏刪；2026-11-13；決策者 AI 總管〔事實更新〕；上方各段原文不改）

1. 上一段「六處差異收尾後最新接手點」標題上的取代註記稱「DEC-177 登錄後**短段**」——實際上該段是**完整接手點段**（含 15 欄 Resume Checkpoint、已完成表與新對話接手提示語），不是短段。
2. 「DEC-177 登錄後」段 Checkpoint「tests / CI 尚未完成」欄把 D6 機率寫成「約 0.5～0.6%」——以 **0.54～0.63%（每個跑到該檔的 pytest 行程）** 為準（出處：DECISIONS 檔尾 `76ed4b7b` 小節，調查組估算）。
3. `PROJECT_RULES.md` 33.2 開頭註記稱「『風險提前觸發』出自客戶訊息二.1 與四」——更正：「風險提前觸發」字樣**只出現在客戶訊息二.1**（制度摘要）；第四節原文是「每批結束檢查交接風險；累積約三批或出現長篇 QA／CI、重大決策變動時，優先安排安全交接」，並無該詞。（`PROJECT_RULES.md` 本批不改，僅在此更正。）
4. 「DEC-177 登錄後」段待裁示清單把 DPE-7 的 11-19 檢查點放在列表中（位置與「不屬仍待裁示」的說法拉扯）——更正：DPE-7 **客戶已定維持 A（觀察）**，11-19 僅為保留檢查點，**不屬待裁示**；本段已移至「已有客戶定論」。
5. **本 PR（#1177）初稿的 Q4 前提錯誤已於修正 commit 更正**：初稿曾寫「五態符號 ✅◷◇⛔ 用在 🗂 不會使測試紅、程式內無守衛」——不正確（`FieldVM`／`ALLOWED_STATUS_PREFIXES` 會拒絕這組符號作為狀態欄位字樣；僅純文字可行），Q4 總管推薦因而由 A 改為 B（見裁示單 Q4、§5）。

### 新對話接手提示語（可直接貼入新對話；改指本段）

```
你接手 my-stock-dashboard（GitHub: linchen-20200325/my-stock-dashboard）。先做 GitHub-first 重核，不要信聊天摘要：
1. 取回 main 最新 SHA、Open／Draft PR（head／base／CI／review；含本批 docs PR「B」〔裁示單那一個〕是否已合併）；2. 讀 docs/DECISIONS.md 最新 DEC（目前 DEC-177，檔尾另有「DEC-177 後續註記：實作前調查結果」，其上 DEC-176／175／174）；3. 讀 docs/HANDOFF.md 檔尾最新接手點段（標題「2026-11-13｜UI 實作前調查與裁示單提交後最新接手點」，含十五欄 Resume Checkpoint；其上各 2026-11-12 接手點段及其內舊提示語已過期，不要照舊提示語行事）；4. 讀裁示單 docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_IMPLEMENTATION_DECISION_SHEET_2026-11-13.md；5. 再讀 CLAUDE.md（§-2、§-1.5.D、§1）、PROCESS.md、PROJECT_RULES.md（§20、§32、§33）。
狀態：客戶已裁示 🗂 資料新鮮度總覽採 A 首屏＋B 展開明細（DEC-177），允許最小 UI 第一版實作但不解除任何 Gate；實作前調查發現須先裁示 Q1～Q7（裁示單；可一行回覆「全部照總管推薦」，範本見裁示單 §0.1）。客戶回覆前不得寫 UI code，不得改 SHOWN_FOLDS／WIRED_PATHS／詞彙守衛／viewport 證據／P3 基準。回覆後第一步＝依回覆範圍以獨立 PR 做階段 1（預期只動 src/services/ui2/* 與測試，不動 src/ui2/**；若需動 src/ui2/** 立即停手回報）；每個放寬附突變測試、不得全域放寬；非作者 QA＋同 head 五項原生 CI；作者不自行合併。
HOLD／禁止（全部未解除）：#1124～#1126 資料 PR（不合併／關閉／rebase）、#1164、#1119；DG-SCOPE／DG-COV／DG-PIT／DG-LIC、I1144-WIRING-GATE；D6 偵測器程式修復（另批提案）；DPE-7 維持 A（觀察），11 月 19 日為保留檢查點；Old UI、正式 UI 切換、資料庫重建、新 API／來源、Actions 清理；不清理 .claude/worktrees/；不降低 CI matrix／no-skip／ui2-browser-gate。
每批最多三項；未授權的新工作不得自行啟動；Agent 進度回報最小化（僅阻塞、需客戶裁示、重大里程碑才報告；其餘依既有靜默巡航規則〔整批完成、Model×Effort 需切換、context 不安全等〕）；預防性交接見 PROJECT_RULES 第 33 節。AI 推薦（含裁示單全部「總管推薦」）不是客戶裁示；FACT／INFERENCE／NOT VERIFIED 要分開寫；CI 綠不等於 Cloud／資料來源已驗證。
未合併 PR 的 head 為 2026-11-13 查詢時點快照，一律以最新 GitHub 為準：#1164 6fddc582（Draft）、#1124 3cd3f525、#1125 cf4739c5、#1126 1654ae60——全部不碰。
Model／Mode／Effort：Sonnet 5.5／Mode：靜默自主巡航／Effort：High（客戶訊息指定，經轉錄；現行值只以 HANDOFF 檔尾最新 Resume Checkpoint 為準）。
沒有客戶新指派時：停手，只做被動觀察，並回報目前狀態與待客戶裁示清單。
```

- **仍 NOT VERIFIED**：DEC-177 fence 與客戶原訊息逐字一致性；預防性交接制度更早核准紀錄；部署端位階是否恆 unloaded；viewport 證據重生可行性；真瀏覽器 390／1440；#1176 合併後 main push CI（run 43334257638）結果；裁示單 §6.1 與調查事實的單組性。本段單組撰寫，未經第二組驗證。


## 2026-11-13｜Agents 批次後最新接手點（現行有效接手點；只追加；非 QA PASS）

> **取代關係**：本段取代上方「2026-11-13｜UI 實作前調查與裁示單提交後最新接手點」段的現況效力（該段標題已就地以刪除線標示；有意識的更新，不是漏刪）。**該段末的「新對話接手提示語」已過期，改指本段末的提示語**。GitHub 操作事實優先於本段；接手前先做 LIVE GitHub Verification Gate（`PROJECT_RULES.md` 第 32 節）。不另建第二份 handoff（`PROJECT_RULES.md` §20.1）。
> **單組聲明**：本段與本 PR 為**作者單組撰寫，未經非作者獨立 QA**（`CLAUDE.md` §-2 規則 6）。**不是授權**；不解除任何 Gate／HOLD。AI 推薦一律是 RECOMMENDATION，不是客戶裁示。

### Resume Checkpoint（`PROJECT_RULES.md` §20.2 十五欄）

| 欄位（§20.2） | 內容（2026-11-13） |
|---|---|
| latest verified main SHA | `63da9515c2f35549aa943a2728e287168632cdb0`（#1177 squash 合併點；2026-11-13 作者 `git fetch origin main` 實查，FACT；cron 與其他 PR 會推進 main，**一律重查**） |
| current working branch | `claude/stock-dashboard-handoff-sync-ulwq8s`（本批 Agents PR 的 head；#1177 合併後遠端同名分支已刪，本批為重新推送；合併後可為任何新分支） |
| current PR | **尚未建立**（作者依派工不建 PR，由總管建立；PR 號與 head SHA 以 GitHub 為準）。其餘 Open PR 本批**未重查**，沿用前段時點快照：**#1164**（Draft，head `6fddc582`，HOLD）；資料 PR **#1124**（`3cd3f525`）、**#1125**（`cf4739c5`）、**#1126**（`1654ae60`），皆 HOLD，cron 會推進，一律重查 |
| current task / batch | 客戶 2026-11-13「專業 AI Agent＋六項品質補強」（DEC-178）：**Agents 批次（`DEC178-AGENTS-BATCH-A`）＝本 PR**（三項：三個 Agent 檔＋守衛測試、`PROJECT_RULES.md` 第 34 節路由、DEC-178／BACKLOG／PROJECT_STATE／HANDOFF 同步）。品質補強 Quality Batch 1～3 **尚未開始** |
| completed in this batch | 見下方「已完成」表。本 PR 內容：`.claude/agents/stock-data-integrity.md`、`stock-ui-ux.md`、`stock-independent-qa.md`；`tests/test_agent_definitions_guard.py`（含突變測試）；`PROJECT_RULES.md` 第 34 節；DEC-178（fence sha256 `3479c09d…b473`）；BACKLOG 檔尾 `DEC178-*` 七列；PROJECT_STATE §70.16；本段 |
| exact current stopping point | 本 PR 已推送、待非作者多組獨立 QA 與同 head 五項原生 CI。**未做**：任何 `src/`、`scripts/`、`.github/`、`.claude/settings*`、`CLAUDE.md`、`PROCESS.md`、資料變更；Agent 實際載入驗證（須新對話） |
| next single action | **本 PR 合併後**：新對話以零記憶方式啟動 → **先 `/agents`（及 `/doctor`）驗證三個 Agent 是否被載入**，結果寫回 BACKLOG `DEC178-AGENT-LOAD-VERIFY` → 再開工 **Quality Batch 1（①②③，`DEC178-QUALITY-BATCH-1`）**。本 PR 本身：非作者 QA＋同 head 五項原生 CI 全綠＋review threads＝0＋mergeable clean 後依 Merge Gate 判斷（作者不自行合併） |
| tests / CI 已完成 | 作者端實跑（venv，會漂移）：`tests/test_agent_definitions_guard.py` 31 passed（含 20 個突變測試類測試）；grep 命中治理文件名稱的 6 個測試檔＋`test_ui2_active_contract_docs`＋`tests/test_sec_*`＋`test_c3_layering_guard`＋`test_resample_audit`＋新守衛，合計 **4712 passed、6 skipped、13 deselected、3 xfailed**（含本段 HANDOFF 變更後的完整重跑，同為 4712 passed）。**作者自查，非 QA** |
| tests / CI 尚未完成 | 本 PR 的非作者多組 QA 與同 head 五項原生 CI；#1177 合併後 main push CI 結果本批**未重查（NOT VERIFIED）**；D6 測試（`tests/test_d6_diagnostic_no_secret_display.py`）有已知約 0.54～0.63% 非決定性紅燈機率，rerun 通過不等於已修；三個 Agent 的實際載入（NOT VERIFIED） |
| unresolved true Stop Gates | #1119 HOLD；#1124～#1126 HOLD；#1164 HOLD；`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、`I1144-DATA-STORAGE-DECISION`、`I1144-DG-A3`、`I1144-DG-HEALTH`、外資 L3、G-F2～G-F6、`REORG3C-Q5-GATE`、Old UI Removal Gate、預設 UI 切換（全部未動）。🗂 資料新鮮度總覽 Q1～Q7（`DEC177-FRESHNESS-IMPL-DECISION-SHEET`）仍 blocked-on-customer，**本批未回答其中任何一題** |
| 是否存在 uncommitted / unpushed work | 以 `git status`／GitHub 實查為準：本段寫入時作者工作樹有待提交變更；推送後預期為「否」（若讀到此段時分支落後或有新 commit，請重查） |
| relevant evidence location | `.claude/agents/`（三檔）；`tests/test_agent_definitions_guard.py`；`PROJECT_RULES.md` 第 34 節；`docs/DECISIONS.md` DEC-178（客戶原文 fence）；`docs/BACKLOG.md` 檔尾「2026-11-13｜DEC-178 登記」；`docs/PROJECT_STATE.md` §70.16；客戶訊息逐字見 DEC-178 fence；🗂 裁示單 `docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_IMPLEMENTATION_DECISION_SHEET_2026-11-13.md`；歷史接手點 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md` |
| recommended Model | Sonnet 5.5（依客戶 2026-11-13 訊息，不可用則選目前高可靠程式模型；經派工訊息轉錄，逐字 NOT VERIFIED；**現行值只維護於此處**） |
| recommended Effort | High；Mode：靜默自主巡航（依客戶 2026-11-13 訊息；**現行值只維護於此處**） |
| last checkpoint timestamp | 2026-11-13T01:27:20Z（`date -u` 實查；本段撰寫時） |

### 已完成（FACT 除另註）

| PR／commit | 內容 | merge／commit SHA | 非作者 QA | 同 head 原生 CI |
|---|---|---|---|---|
| #1175 | 六處交接差異收尾 | `880bc17c`（main） | 見前段（自述） | 見前段（自述） |
| #1176 | DEC-177 登錄、`PROJECT_RULES.md` 第 33 節、BACKLOG 三列、HANDOFF 15 欄段 | `093b323d`（main） | 兩組＋Delta（前段自述） | 同 head `1af7976a` 五項全綠（前段自述） |
| #1177 | 🗂 資料新鮮度總覽實作前調查與裁示單（Q1～Q7）、DECISIONS／BACKLOG／PROJECT_STATE／HANDOFF 同步 | `63da9515`（main；作者 `git fetch` 實查 main 頂端 commit 為此 SHA，FACT） | 派工訊息稱已完成（本組未重讀 review 紀錄，NOT VERIFIED） | 派工訊息稱已完成（本組未重讀 check runs，NOT VERIFIED） |
| 本 PR（Agents 批次） | 三個 Agent 入庫、守衛測試、第 34 節、DEC-178 等同步 | 未合併 | 待 | 待 |

### 本批三項狀態

1. **三個 Agent 檔＋守衛測試**＝已撰寫並於作者端靜態驗證通過；**實際載入 NOT VERIFIED**（須新對話 `/agents`、`/doctor`）。
2. **最小任務路由規則**＝`PROJECT_RULES.md` 第 34 節（只追加）。
3. **DEC-178／BACKLOG／PROJECT_STATE／HANDOFF 同步**＝本 PR。
**品質補強三批尚未開始**：Quality Batch 1（①現有覆蓋與缺口稽核、②DoR／DoD、③五頁資料／功能／驗收矩陣）→ Batch 2（④E2E／Golden／Mutation、⑤最小 PR Impact Check、⑥Production 健康度五軸）→ Batch 3（⑦Agent 路由整合、⑧Token 與返工基準、⑨零記憶接手測試）；順序、前置與限制見 DEC-178 與 BACKLOG `DEC178-QUALITY-BATCH-1`～`3`。

### 待客戶裁示

🗂 資料新鮮度總覽 **Q1～Q7** 仍待客戶回覆（見裁示單與前段「待客戶裁示」A～C，**不在此重複細節**）；回覆前不寫 UI code。`DEC178-AGENT-BASH-READONLY-ENFORCEMENT`（是否在 settings 層機械強制 Bash 唯讀）屬客戶另行裁示事項，**非阻塞**；沉默＝維持現狀。

### 仍 HOLD（客戶 2026-11-13 訊息第五節＋既有）

#1124～#1126（不合併／關閉／rebase）、#1164、#1119（不處置）；`DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC`、`I1144-WIRING-GATE`、OneBrain／New UI2 資料接線 Gate；D6 偵測器程式修復（另批提案）；DPE-7 維持 A（觀察），11 月 19 日檢查點保留；不修改投資公式、Risk Cap、System Action；不新增未授權 API／來源／cron／Secrets；不擅改 UI 布局、`SHOWN_FOLDS`、UI 契約與測試 allowlist；不把 missing 填 0；Old UI、正式 UI 切換、資料庫重建、Actions 清理；不清理 `.claude/worktrees/`；不降低 CI／QA／Merge Gate；第二批候選 Agent（Investment Logic、OneBrain、GitHub Auditor）未授權、不建立。

### 風險

(1) 本 PR 單組撰寫，未經非作者獨立 QA；(2) Agent frontmatter 格式依派工訊息轉述的官方文件（單組，作者未重新查官方文件）；無法辨識的欄位會被靜默忽略，故以守衛測試擋拼錯；(3) Bash 唯讀僅為指示性約束；(4) 三檔實際載入與路由效果 NOT VERIFIED；(5) MCP 工具名在其他環境是否存在，官方未明載；(6) D6 測試約 0.54～0.63% 非決定性紅燈機率；(7) 未合併 PR head 為時點快照，cron 會推進；(8) 本批 `description` 常駐父層 context，三檔合計很短，但實際 Token 成本未量測（NOT VERIFIED，屬 Quality Batch 3 ⑧）。

### 交接風險檢查（`PROJECT_RULES.md` 第 33 節）

本對話已累積多批（#1175、#1176、#1177、本批 Agents）、長篇 QA／CI 往返與重大決策變動（DEC-177、DEC-178）→ 依第 33 節「累積約三批或出現長篇 QA／CI、重大決策變動時優先安排安全交接」，**建議在本 PR 合併後安全交接**：先確認本 PR 內容已進 main 並驗證 main push CI、本段已在 GitHub，**然後**才結束舊對話，再依 GitHub 最後狀態使用下方提示語開新對話。此為 AI 建議，不是硬性規則；不承諾能讀取剩餘上下文 Token。

### Low 級備忘（指標；不重述）

PROJECT_STATE §70.15 與 🗂 裁示單已更正的 Q4 前提（五態符號 ✅◷◇⛔ 放進狀態欄位會被 `FieldVM`／`ALLOWED_STATUS_PREFIXES` 拒絕，Q4 總管推薦因而由 A 改為 B）：見上一接手點段「#1176 已知 Low 級瑕疵更正註記」第 5 點與裁示單 Q4、§5；本批未再改動。

### 下一個唯一安全動作

**本 PR 合併後**，新對話零記憶啟動，先驗證三個 Agent 是否被載入（`/agents`，必要時 `/doctor`），再開工 Quality Batch 1（①②③）。載入失敗或與定義不符：停手回報，不自行改權限或 settings。客戶回覆 🗂 Q1～Q7 前不寫 UI code。無新指派時：停手，只做被動觀察。

### 先讀 SSOT 順序

`CLAUDE.md`（§-2、§-1、§-1.5、§1）→ `PROCESS.md` → `PROJECT_RULES.md`（§15、§20、§32、§33、**§34**）→ `docs/DECISIONS.md`（**DEC-178** 與客戶原文 fence；其上 DEC-177 及其後續註記、DEC-176、DEC-174）→ `docs/BACKLOG.md` 檔尾 `DEC178-*` → `.claude/agents/`（三檔）→ `docs/PROJECT_STATE.md` §70.13～§70.16 → 本段；🗂 裁示單與線框見上一接手點段；歷史接手點見 `docs/archive/historical/HANDOFF_HISTORY_2026-11-12.md`。

### 新對話接手提示語（可直接貼入新對話；改指本段）

```
你接手 my-stock-dashboard（GitHub: linchen-20200325/my-stock-dashboard）。先做 GitHub-first 重核，不要信聊天摘要：
1. 取回 main 最新 SHA、Open／Draft PR（head／base／CI／review；含本批 Agents PR 是否已合併）；2. 讀 docs/DECISIONS.md 最新 DEC（目前 DEC-178，含客戶 2026-11-13 原文 fence；其上 DEC-177 及其後續註記）；3. 讀 docs/HANDOFF.md 檔尾最新接手點段（標題「2026-11-13｜Agents 批次後最新接手點」，含十五欄 Resume Checkpoint；其上各接手點段及其內舊提示語已過期，不要照舊提示語行事）；4. 讀 docs/BACKLOG.md 檔尾 DEC178-* 七列；5. 再讀 CLAUDE.md（§-2、§-1、§-1.5）、PROCESS.md、PROJECT_RULES.md（§20、§32、§33、§34）。
狀態：客戶已核准兩項工作（DEC-178）：(1) 三個按需專業 Agent（.claude/agents/ 下 stock-data-integrity、stock-ui-ux、stock-independent-qa；路由見 PROJECT_RULES 第 34 節；三者皆無 Write／Edit／NotebookEdit／Agent 工具，QA 另有 GitHub 讀取類 MCP 工具；Bash 唯讀僅為指示性約束；「按需」不改 CLAUDE.md §-2 每次任務都派工與多組獨立稽核）；(2) 六項品質補強，分三批、每批最多三項、依序進行：Batch 1＝①現有覆蓋與缺口稽核（REUSE／GAP／BLOCKED／NOT VERIFIED）、②Definition of Ready／Done 最小補強、③New UI2 五頁資料／功能／驗收矩陣；Batch 2＝④E2E／Golden／Mutation Tests（只補真正缺口，不放寬 PIT／Risk Cap／資料完整性）、⑤最小 PR Impact Check、⑥Production 健康度五軸（CI／資料更新／資料有效／正式 UI 接線／投資決策與通知可用；缺證據標 NOT VERIFIED）；Batch 3＝⑦Agent 路由整合、⑧Token 與返工基準（真實量測／估算／NOT VERIFIED 分開，禁止 bytes 冒充 Token；是 REORG3C-Q5-GATE 的前置證據、不構成 Q5 重議）、⑨零記憶接手測試。每批：GitHub-first、非作者多組獨立 QA、同最新 head 五項原生 CI、review threads 與 Merge Gate 核實、合格才 merge、GitHub 留證後才進下一批。
唯一 NEXT：確認 Agents PR 已合併後，先以 /agents（必要時 /doctor）驗證三個 Agent 是否被載入並把結果寫回 BACKLOG DEC178-AGENT-LOAD-VERIFY；載入失敗就停手回報，不自行改權限或 settings。然後開工 Quality Batch 1。不要重做已完成工作（#1175～#1177、Agents 批次）。
HOLD／禁止（全部未解除）：#1124～#1126 資料 PR（不合併／關閉／rebase）、#1164、#1119；DG-SCOPE／DG-COV／DG-PIT／DG-LIC、I1144-WIRING-GATE；OneBrain／New UI2 資料接線 Gate；🗂 資料新鮮度總覽 Q1～Q7 仍待客戶回覆（回覆前不寫 UI code，不改 SHOWN_FOLDS／WIRED_PATHS／詞彙守衛／viewport 證據／P3 基準）；D6 偵測器程式修復（另批提案）；DPE-7 維持 A（觀察），11 月 19 日為保留檢查點；不修改投資公式／Risk Cap／System Action；不新增未授權 API／來源／cron／Secrets；不把 missing 填 0（unavailable ≠ neutral、not evaluated ≠ safe、FAKE Preview ≠ 正式接線）；Old UI、正式 UI 切換、資料庫重建、Actions 清理；不清理 .claude/worktrees/；不降低 CI／QA／Merge Gate；第二批候選 Agent（Investment Logic、OneBrain、GitHub Auditor）不建立。
需客戶裁示時：提出 A／B／C 三方案比較（正確性、風險、速度、Token）、推薦方案、最小變更範圍後停手。靜默自主巡航：只在真正阻塞、客戶 Decision Gate、重大里程碑或整批完成時回報；累積約三批或長篇 QA／CI 時依 PROJECT_RULES 第 33 節主動安排安全交接（先存 GitHub、驗證、再換對話）。FACT／INFERENCE／NOT VERIFIED 分開寫；CI 綠不等於 Cloud／資料來源已驗證。
時點快照警語：本段與提示語內的 SHA／PR head 皆為 2026-11-13 時點快照，一律以最新 GitHub 為準；未合併 PR head（#1164 6fddc582、#1124 3cd3f525、#1125 cf4739c5、#1126 1654ae60）cron 會推進，全部不碰。
Model／Mode／Effort：Sonnet 5.5（不可用則選目前高可靠程式模型）／Mode：靜默自主巡航／Effort：High（客戶訊息指定，經轉錄；現行值只以 HANDOFF 檔尾最新 Resume Checkpoint 為準）。
沒有新指派時：停手，只做被動觀察，並回報目前狀態與待客戶裁示清單。
```

- **仍 NOT VERIFIED**：DEC-178 fence 與客戶原訊息逐字一致性；三個 Agent 的實際載入與路由效果；Bash 唯讀 settings 層是否強制；#1177 的非作者 QA／CI 細節與 #1177 合併後 main push CI；Agent frontmatter 格式官方文件（單組轉述）。本段單組撰寫，未經第二組驗證。
