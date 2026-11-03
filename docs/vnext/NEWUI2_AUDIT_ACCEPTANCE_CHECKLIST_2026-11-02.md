# New UI2 Audit／Acceptance Checklist

> ⛔ **SUPERSEDED / HISTORICAL — NOT ACTIVE（部分；DEC-128，客戶 2026-11-03）**：本檔下列範圍**已不是現行規則**——§15 C2「每頁 L1／L2／L3」口徑；§17「⛔ L2／L3 插隊」；§19 第 2 點「市場位階（📊 現在狀態＋L2 位階說明…）」中的 L2（S32）。新驗收項見本檔 §20（**未自勾**）。其餘驗收項仍有效。**現行唯一有效讀法**＝`docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md` 與 `docs/DECISIONS.md` DEC-128；與本檔衝突時以該文件為準。**本檔其餘條文仍有效**；舊文一字未刪（歷史證據）；⛔ 不得依本檔被取代的範圍施工。（有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）。）

- **狀態**：**正式清單（客戶 2026-11-02 裁示 (6) 要求同步「Audit / Acceptance checklist」；逐字見 `docs/DECISIONS.md` DEC-123）；隨 #997 獨立稽核＋合併後生效。** 條目來源逐項標註；未標客戶原文者＝AI 總管內部自決（客戶可推翻）。
- **日期**：2026-11-02　**基準**：`origin/main`＝`acd1648c`；分支 `ccr-a0b4e085-ijdaio`（PR #997）。
- **用法**：每一個 New UI2 相關 PR（含 docs、契約、PORT、頁面、Aggregator、cutover）在宣告完成前，由**非實作組**的獨立 QA 逐項勾選；不適用的項目寫「N/A＋理由」，⛔ 留白。結果寫進 PR 描述（`CLAUDE.md` §-1.5 回報落點補註：完整稽核證據留 PR）。
- **出處縮寫**：〔DEC-122 §n〕＝Freeze 主線指示第 n 節；〔Q1～Q4〕＝DEC-123 客戶裁示；〔Fz §n〕＝`FINAL_UI_CONTRACT_FREEZE_2026-11-02.md`；〔AG §n〕＝`NEWUI2_ARCHITECTURE_GATE_2026-11-02.md`；〔MC §n〕＝`NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md`；〔WF §n〕＝`NEWUI2_WIREFRAMES_2026-11-02.md`。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：單組撰寫；清單本身亦需隨 #997 稽核。

---

## §1 每批 PR 驗收六問〔DEC-122 §45〕

- [ ] **What changed?**
- [ ] **What did NOT change?**
- [ ] **Which contract?**（Freeze 條號／AG 條號／Aggregator 契約版本）
- [ ] **What tests?**（含 mutation：拔掉守衛必轉紅）
- [ ] **Any semantic change?**（只是 UI → 必須明示 **No investment semantic change**）
- [ ] **Any missing capability?**（對照 Capability Map；能力消失＝⛔，除非經客戶 Gate）

## §2 守衛 G1～G12〔AG §9.2〕（測試守衛編號，與 Decision Gate 無關）

- [ ] G1 層登記：`src/ui2/` 進 c3 `_PATH_LAYERS`／`_MODULE_LAYERS`；`app_ui2.py` 進 `_SCAN_FILES`（L6）；meta 測試「每檔層別非 None」
- [ ] G2 VM 純度：⛔ import `streamlit`／`src.ui*`／`src.data*`／`requests`；⛔ `session_state`；⛔ 聚合動作
- [ ] G3 Presentation Slice independence：Top5／Top10／collapsed／never-rendered 四情境 `context` 逐欄相等
- [ ] G4 UI2 獨立性：⛔ import Legacy New UI／Old UI／`app`；`src.ui_v2` 只走明列允許清單
- [ ] G5 四態：VM 欄位狀態 ∈ {ok, missing, stale, unavailable, not_evaluated}；⛔ 映射 0／中性／續抱／safe
- [ ] G5′ 三軸語意邊界〔DEC-124〕：資料語意**恰五態**（OK／Missing／Stale／Unavailable／Not Evaluated）；`⬜ 尚未提供`＝capability state（Preview-only、`state` 為 None、⛔ 第 6 資料態、只在允許清單檔出現）；Unable to Determine（`⬜ 無法判定`、`⬜ 未評估／資料不足`）≠ Not Evaluated（不同值、不同字樣、不同表）；三者皆 ⛔ 帶值（2026-11-02 Semantic Correction Gate 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-124）；原文刪除線保留）
- [ ] G6 Risk Cap 不得 unrestricted add（表格驅動）
- [ ] G7 Single Action Authority：動作字串 ⊆ deterministic 原名；⛔「減碼 1/2」「全出」
- [ ] G8 手機第一屏量測（390×844）
- [ ] G9 Producer 禁令：⛔ `*_apply`、`gemini_call`、`post_gemini`、`build_ai_summary`、`run_agent`；⛔ 寫非 `ui2_` 前綴 session key
- [ ] G10 入口 boot smoke＋floor 守衛涵蓋 `app_ui2.py`
- [ ] G11 路由毒化（cutover 批）：毒化 UI2 → `?ui=1`、`?legacy=1` 仍完整載入
- [ ] G12 術語：顯示字樣取 Fz §21 SSOT；⛔ 偏多／中性／偏空

## §3 四頁第一屏四問（mobile 390×844 先、desktop 1440×900 後）〔客戶 (5)-9；Fz §0.1.6；WF §1〕

| 頁 | ① 現在狀態 | ② 是否需要行動 | ③ 下一步 | ④ 主 CTA | 「不用滑」必要項 |
|---|---|---|---|---|---|
| 📊 市場 | [ ] | [ ] | [ ] | [ ] | [ ] 市場目前狀態、Risk Cap、是否需要行動、主 Update CTA；今日結論仍在第一屏；今日主要風險緊接其後（L1） |
| 🎯 標的 | [ ] | [ ] | [ ] | [ ] | [ ] mode、search、查詢摘要；W-4 context 只是輕量 row／chip |
| 💼 持股 | [ ] | [ ] | [ ] | [ ] | [ ] portfolio status、Risk Cap、是否需要處理 |
| 👤 我的 | [ ] | [ ] | [ ] | [ ] | [ ] connection state、primary management actions |

- [ ] **禁止先做 desktop 再縮手機**〔客戶 (5)-9〕：PR 附手機截圖在前
- [ ] Visual Fidelity：既有 A1～A11、V1～V11＋**Decision Density**（⛔ 第一屏 20 張 cards、大表、工程文字、raw JSON）＋**Text Reduction**（結論 → 圖 → 細節）〔DEC-122 §41〕
- [ ] 線框核准條件（WF §9）：W-4 不搶查一檔／基本面／valuation、市場技術訊號不成單股主要判斷；W-5 計入加／換／減／暫停加碼、🟡 留意不升格；W-9「可判定覆蓋度」；W-10 transitional 四條；W-11 建議持股區間 ≠ Portfolio Risk Cap

## §4 四態〔Fz §5；WF §0.2〕

- [ ] Missing＝`⬜ 資料未取得`／`⬜ 資料未備`（灰）；Stale＝`⚠ 過期 N 天`（琥珀）；Unavailable＝`🔴 來源目前不可用`＋原因（紅）；Not evaluated＝`⬜ 尚未評估`（灰）——四者不混用
- [ ] missing ≠ 0；missing ≠ HOLD；missing ≠ neutral；unavailable ≠ safe；not evaluated ≠ safe
- [ ] 〔DEC-124〕Not Evaluated（規則／計算尚未執行或不在本次評估範圍）與 Unable to Determine（已進入判定、必要輸入 Missing／Unavailable／Invalid／insufficient）**分開呈現、⛔ 合併**；無法判定 ≠ safe／neutral／no action／無需調整／可加碼
- [ ] 〔DEC-124〕`⬜ 尚未提供` 只表示功能尚未實作／接線（capability），⛔ 寫成資料品質態或「第 6 個資料語意態」
- [ ] 冷啟動＝灰色說明（⛔ 紅）；紅色兩義文字不同（真錯誤 vs `🔴 Risk Cap 超限 · 禁止新增曝險`）
- [ ] 每卡 value／state／as_of／source；⛔ 共用全域更新時間；缺 as_of → `⬜ 資料日未提供`

## §5 Risk Cap〔Fz §0.1.4；Q1=A of DEC-122〕

- [ ] 目前曝險或有效上限任一不足 → `⬜ 無法判定`
- [ ] 〔DEC-124〕Risk Cap `⬜ 無法判定`＝Unable to Determine：⛔ 等同 NOT_EVALUATED；⛔ 渲染成 OK／綠／safe／「今日無需調整」；⛔ 帶值；⛔ 新增 Risk Cap 規則或數值
- [ ] 無法判定時加碼類 ⛔ 以無上限呈現；加碼列標「Risk Cap 無法判定」
- [ ] ⛔ 自行發明曝險分母／現金／總資產／替代值
- [ ] ⛔ 新增 Risk Cap 百分比顯示面；市場頁維持隱藏；持股頁已核准建議持股區間維持
- [ ] 建議持股區間 ⛔ 寫成已啟用 Portfolio Risk Cap（W-11）

## §6 Single Action Authority〔Fz §0.1.5、§6；客戶 (5)-8〕

- [ ] 動作只來自 System Action State（Aggregator 實作前：既有正式分支原名，或 `⬜ 尚未提供`）
- [ ] 分支原名照寫；「加／留／換／減」只是排版
- [ ] 「今日無需調整」只在計入組皆 0 且 0 未評估、0 不可得
- [ ] ⛔「減碼 1/2」「全出」；⛔ UI 自己創造正式投資規則；⛔ OneBrain／AI 產生 action
- [ ] W-10：Aggregator 完成前，市場頁舊警示標 source／scope、⛔ 冒充 System Action State、⛔ 第二套 Action Authority、與持股頁衝突時並列揭露（⛔ 自行選一邊）

## §7 System Action Aggregator 禁止清單〔Q2；AG §4.6.4，客戶原文逐字〕

- [ ] 新增投資規則
- [ ] 新門檻
- [ ] 新比例
- [ ] AI action
- [ ] 改寫既有 deterministic result
- [ ] 覆寫 Risk Cap
- [ ] 自行決定減碼 1/2／全出
- [ ] portfolio write
- [ ] Sheet write

（每項須勾「未發生」並附證據；任一發生 ⛔ 合併。）另：
- [ ] 屬新 runtime component：**implementation Gate 已由客戶核准**才可有實作 PR〔Q2〕
- [ ] Aggregator 測試 A-T1～A-T10 全綠（AG §4.6.8）

## §8 Preview 成本控制〔Q1，客戶原文〕

- [ ] 架構／UI 驗收優先使用 fake／snapshot／view-model scenario
- [ ] 真實外部資料只在 real-data acceptance 或必要人工驗收時使用
- [ ] ⛔ 為 Preview 建第二套 data／service／source pipeline
- [ ] Preview 與 production 讀相同 canonical services／contracts
- [ ] 人工建 Preview App／Secrets／OAuth 網址：需要時才發 🟡 Manual Action Gate，⛔ 提前要求

## §9 Real-data／Missing／Stale／Failure〔DEC-122 Stage I；MC §1.1 C4／C5〕

- [ ] Desktop 真資料、Mobile 真機／正式 viewport（非只夾具）
- [ ] Cold Start（無 cache）
- [ ] Partial Data（某來源 missing）
- [ ] Stale（某來源過期）
- [ ] API Failure（來源失敗）
- [ ] AI Failure（provider fail）
- [ ] 以上皆安全顯示 deterministic output；部分失敗真錯誤外露；截圖 ⛔ 含真實持股／Sheet ID／金鑰

## §10 Cross-page consistency〔DEC-122 Stage H §38、§39；MC §1.1 C6〕

- [ ] 市場／標的／持股使用同一份 market context（不同結論須有明確不同 as_of）
- [ ] Risk Cap blocked／無法判定 → 任何頁、OneBrain ⛔ unrestricted Add
- [ ] 術語統一（Regime、Risk Cap、Missing、Freshness、System Action、OneBrain、Strategy、Valuation）
- [ ] Aggregator 完成後：市場 ⚡ 與持股今日需處理同一 canonical action source（A-T11）
- [ ] LINE 與 UI 收斂（另批、另 Gate；未收斂前登記差異，⛔ 宣稱一致）

## §11 Cutover／Rollback〔Q4；MC §1、§2〕

- [ ] Cutover 鏈九步皆有證據（獨立 Preview → 四頁逐頁 → mobile／desktop → missing／stale／source failure → real-data → cross-page → 全部通過 → 一次切成 default）
- [ ] 一次切換（⛔ 逐頁切 production）
- [ ] Legacy New UI（`?ui=1`）與 Old UI（`?legacy=1`）rollback path 保留且可載入（G11）
- [ ] ⛔ 先刪程式
- [ ] 回滾一行可行；UI2 無投資狀態殘留
- [ ] 〔DEC-124〕production 預設 VM 中 capability marker（`⬜ 尚未提供`）**0 個**（Preview-only implementation state；BACKLOG `NUI2-CAPABILITY-MARKER-CUTOVER-ZERO`）

## §12 Removal Gate 條件〔Fz §19 ∪ DEC-083 第 11 點 E 段；MC §4〕

- [ ] 對象分開：Old UI、Legacy New UI 各自送 Gate
- [ ] 四頁能力 coverage、mobile acceptance、real data acceptance、audit coverage、user final acceptance、capability map（三欄）無 critical gap
- [ ] capability inventory → mapping → implementation → interaction coverage → regression → customer verification → Removal Decision Gate
- [ ] New UI 語意測試已 PORT 到 UI2（`NUI2-NEWUI-SEMANTIC-TEST-PORT`）
- [ ] 客戶 Removal Decision Gate 裁示

## §13 永久收尾 Gate〔客戶 2026-11-02 原文；`PROJECT_RULES.md` 第 27 節〕

- [ ] 「每一批完成前，必須檢查是否出現新的 Rule / Decision / Audit finding / Limitation / Backlog / Migration debt；若有，必須同步 GitHub 正式文件後才能宣告該批完成。」
- [ ] 逐類回答（有／無；有則寫落點）：Rule → `PROJECT_RULES.md`／正式 spec；Decision → `docs/DECISIONS.md`；Audit finding → 正式 spec／`docs/BACKLOG.md`；Limitation → 正式 spec「未驗與限制」＋`docs/PROJECT_STATE.md`；Backlog → `docs/BACKLOG.md`；Migration debt → `docs/BACKLOG.md`＋Migration／Cutover Contract
- [ ] `docs/PROJECT_STATE.md`、`docs/HANDOFF.md`（session 紀錄落點：Safe Handoff 區塊）已同步
- [ ] 「沒有寫進 GitHub的項目，不視為可靠專案狀態。」——scratchpad、聊天、PR 描述、HANDOFF 一句話、Claude memory **不算**落盤〔客戶 (6)〕

---

## §14 Batch 1 驗收證據索引（2026-11-02；append-only）

- G1：`tests/test_ui2_registration_and_boot.py`（meta＋teeth）；G2／G3／G4／G5／G9／chip 語意：`tests/test_ui2_guards.py`；G10：同上（floor 掃 `app_ui2.py`、AppTest、乾淨行程冷啟動）。
- 未做（屬後續批）：G6／G7（Aggregator＋持股 VM）、G8 y 座標量測、G11 路由毒化、G12 逐頁術語驗收（見 BACKLOG `NUI2-G6-G7-G8-G11-G12-PENDING`）。
- 截圖：`docs/vnext/newui2_batch1/`（FAKE；只存證據，**不是** Visual Fidelity Gate 判定；§3 手機第一屏四問**未量測**）。
- §13 收尾 Gate 檢查：新 Rule＝無（本批未新增規則；G2 允許清單與 `ui2_` key 前綴為 Gate §4.2／§9 既有條文的落地）；新 Decision＝無；Audit finding／Limitation／Backlog／Migration debt＝已寫入 BACKLOG §5.1.20、PROJECT_STATE §52、Migration Contract §6。

## §15 Semantic Correction Gate 驗收證據索引（DEC-124，2026-11-02；append-only）

- 契約：`shared/ui2_contract/models.py`（`FieldState` 恰五態／`JudgementState.UNDETERMINABLE`／`CapabilityState.NOT_PROVIDED`＋`FieldVM.capability`）、`text.py`（三張互斥字樣表）；VM：`src/services/ui2/{vm_common,scenarios}.py`；渲染：`src/ui2/components/html.py`（`STATE_TONE`＋`CAPABILITY_TONE`）。
- 守衛：`tests/test_ui2_guards.py`「DEC-124」段（資料語意恰五態、三軸型別互斥、UTD≠NE 不同值不同字樣、字樣跨軸禁用、客戶字樣逐字、Risk Cap 無法判定 ⛔ safe 讀法、capability marker Preview-only 允許清單、未知 state 提示 raise），各附 teeth；既有斷言改寫處皆標「DEC-124 語意修正」且未放寬。
- §13 收尾 Gate：新 Rule＝有（永久語意，`PROJECT_RULES.md` §19.8 加註）；新 Decision＝有（DEC-124）；Audit finding／Limitation／Backlog／Migration debt＝BACKLOG §5.1.21、PROJECT_STATE §53、Migration Contract §7。

## §16 Batch 2 驗收項與量測證據（2026-11-03；append-only；實作組單組，**待總管複驗／獨立 QA／客戶驗收**——下列 `[ ]` 為驗收者勾選，實作組不自勾）

- **新增驗收項**：
  - [ ] **W-1 導覽**：手機＝底部固定四格（top＝844−53＝791、貼底、全寬、四格同列）；桌機＝左側四項（left＝0、垂直）；恰四頁、⛔ 第五頁；當前頁除顏色外有 `● ` 符號＋粗體＋色條＋原生 radio `checked`（Freeze §4.1）；內容底部／左側讓位、不被導覽遮住〔Wireframes §0.4／§7 W-1；BACKLOG `NUI2-NAV-W1-FIDELITY`〕。⚠️ 無螢幕閱讀器驗證（`NUI2-NAV-A11Y-AUDIT`）。
  - [ ] **三軸呈現**：資料五態／判定結果（無法判定）／capability（尚未提供）各有**文字＋樣式**（實線／雙線／虛線＋`data-axis`），互不混用；每個非 OK 態都有可見文字；⛔ 只靠顏色〔DEC-124；Freeze §4.1〕。
  - [ ] **field-level source／as_of**；⛔ 全域假更新時間（含整頁 AppTest markdown 掃描）〔Freeze §9〕。
  - [ ] **CTA**：Preview 期 disabled 示意（`aria-disabled="true"`、無互動標籤）；動作欄維持 capability `⬜ 尚未提供（待 System Action Aggregator）`；Risk Cap 維持 `⬜ 無法判定`（判定結果）。
  - [ ] **§3 第一屏四問（量測）**：四頁 × 六場景 × 兩 viewport 共 48 態，①～④（與 Risk Cap 列）底緣 ≤ 可用高（手機 791／桌機 900）、不被導覽遮住、無水平捲動、標題不重疊；**Preview（FAKE）範圍**，真資料需 Stage I 重量（`NUI2-VIEWPORT-FAKE-ONLY`）。
  - [ ] **兩個 Streamlit 版本**：floor 1.56.0 與現行 1.59.2 的 UI2 測試皆綠、量測皆 48/48。
- **量測證據**：`docs/vnext/newui2_batch2/viewport_measurements.json`（Streamlit 1.59.2）、`viewport_measurements_streamlit156.json`（1.56.0）；截圖 `*.png`（手機全部場景＋桌機 cold／loaded）；重跑 `python -m tests.ui2_viewport.measure_viewport --out <dir>`；判定器與門檻出處 `tests/ui2_viewport/measure_viewport.py::THRESHOLDS`。手機各元素底緣 y 範圍見 `docs/PROJECT_STATE.md` §54（④ 主 CTA 底緣最大 636px，可用高 791px）。
- **測試**：`tests/test_ui2_batch2.py`（靜態 W-1 契約、三軸元件、全頁 AppTest 掃描、`evaluate()` 判定器 teeth、slow 真瀏覽器）。
- **不得誤讀**：§3 表格的各格（「今日結論」「mode 切換＋搜尋」「今日主要風險緊接」等頁別必要項）**未全部落地**（`NUI2-WIREFRAME-FIRST-SCREEN-EXTRAS`）；本批只證明「四問」在第一屏內，**不是** Visual Fidelity Gate 判定（`NUI2-VF-HARNESS` 仍 open）。
- §13 收尾 Gate：新 Rule＝無；新 Decision＝無；其餘見 BACKLOG §5.1.22、Migration Contract §8。

## §17 Batch 3 驗收項與量測證據（2026-11-03；append-only；實作組單組，**待總管複驗／獨立 QA／客戶驗收**——下列 `[ ]` 為驗收者勾選，實作組不自勾）

- **新增驗收項**：
  - [ ] **📊 今日結論**：第一屏首列、位於 ① 市場目前狀態之上、底緣 ≤ 可用高（手機 791／桌機 900）；句型＝各判斷獨立並列（「；」）、缺值／Stale／Unavailable／未評估明寫、⛔「但／因此」、⛔ 方向（多頭／空頭／偏多／偏空…）與動作字樣；VM 原樣帶出、⛔ 由位階／指標推導；FAKE 示意句明標 `FAKE 示意結論：`；冷啟動＝灰色 `⬜ 尚未載入`〔DEC-081 Q2-1；Freeze §0.1.6-5；Wireframes §2.1／§9〕。⚠️ 句子是**FAKE 示意**，非逐字結論句（Q2-1 只有規則）。
  - [ ] **📊 今日主要風險**：L1、緊接第一屏四問之後（同一 `.ui2-m-l1` 容器；其後第一個內容區塊＝卡片，⛔ L2／L3 插隊）；桌機與 ①、Risk Cap 同列三 tile；退化／護欄句與 Legacy 原始碼**逐字**一致（`未評估不等於安全`／`無法判定`／`尚未載入`／真錯誤）；冷啟動灰（⛔ 紅）、真錯誤才紅；⛔ 風險項／「無風險」「安全」字樣〔Freeze §0.1.6-3；DEC-117 Q6〕。⚠️ 冷啟動「不出列」＝單組解讀（`NUI2-COLD-MAIN-RISK-READING`）。
  - ⛔ SUPERSEDED / HISTORICAL — NOT ACTIVE（DEC-128 S32）：本項的「⛔ L2／L3 插隊」讀法已改為「📊🎯💼 整頁 0 個完整 evidence expander（👤 稽核面入口為明列例外）」；其餘（L1、緊接、同列三 tile）維持。現行見 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md` §3。
  - [ ] **🎯 雙模式**：頂部恰兩項（市場精選／即時查一檔）、恰一項當前（● 符號＋粗體＋邊框，⛔ 只靠顏色）；**不同時完整展開**（DOM 只有一個 `data-ui2-mode-content`）；兩模式內容都在 `PageVM.context`、切換只改 slice〔Freeze §3.1-2；客戶 (10)-B-2；Presentation Slice ≠ Decision Context〕。
  - [ ] **🎯 搜尋與查一檔 FAKE**：搜尋框＋搜尋 CTA 在模式切換之下、查詢摘要之上、底緣 ≤ 可用高；disabled 示意（⛔ 真查詢／`<input>`／`<form>`）；fake ticker 標 FAKE 且無真實代號樣式；加入觀察 CTA 恆 disabled；**session-only**：只寫 `ui2_` 前綴 key（AppTest＋AST 守衛）、⛔ 持股／觀察／候選池／strategy／Sheet；⛔ 買賣判斷字樣；動作權威不在本頁〔Freeze §3.2／§3.3；DEC-083〕。
  - [ ] **🎯 W-4 context row**：市場位階＋Risk Cap 一行輕量 chip、在查詢摘要之下、字級小於摘要；6 維 Snapshot『市場環境』不排第一格、Neutral；位階與市場頁同一份 FAKE market context〔Wireframes §9 W-4；客戶 Q3〕。~~⚠️ `unavailable` 場景紅色呈現屬單組讀法（`NUI2-TARGET-W4-RED-ON-UNAVAILABLE`）。~~ 📌 **2026-11-03（DEC-127）客戶接受 Neutral／Info 方向、不再待覆核；改查 §18 第 2 項**（有意識的更新，不是漏刪；決策者 客戶〔DEC-127〕）。
  - [ ] **👤 三態**：signed-out／signed-in／unavailable 各有狀態標示、動作列（全 disabled）與依狀態的主 CTA（Google 登入／切換 Sheet／重新讀取）；連線事實全在資料語意軸（三軸不混層）；**無 OAuth／Sheet／secrets／`src.data`**（AST／import 守衛含注入）〔Wireframes §1／§5.1；Freeze §16.4〕。⚠️ 「尚未登入」歸類為單組判讀（`NUI2-ME-SIGNEDOUT-CLASSIFICATION-REVIEW`）。
  - [ ] **三軸不混層（Batch 3 新欄位）**：今日主要風險／結論／查一檔 Snapshot／帳戶卡的 `layer` 與字樣表一致；Unable to Determine ≠ Not Evaluated；capability 不帶 state〔DEC-124〕。
  - [ ] **無人名字樣**：`src/ui2`、`src/services/ui2`、`shared/ui2_contract`、`app_ui2.py` 原始碼與渲染 VM 無人名（PROJECT_RULES §28）。
  - [ ] **兩個 Streamlit 版本**：1.59.2 與 1.56.0 的 UI2 測試皆綠、量測皆 64/64。
- **量測證據**：`docs/vnext/newui2_batch3/viewport_measurements.json`（Streamlit 1.59.2；64 態）、`viewport_measurements_streamlit156.json`（1.56.0；64 態）；截圖 `*.png`（手機全部態＋桌機 cold／loaded；`*_lookup`＝即時查一檔、`*_signed_out`／`*_unavailable`＝我的帳戶態）。重跑 `python -m tests.ui2_viewport.measure_viewport --out <dir>`（floor：`--python /tmp/v156/bin/python --json-name viewport_measurements_streamlit156.json --shots none`）；判定器與門檻出處 `tests/ui2_viewport/measure_viewport.py::THRESHOLDS`（新增 6 條，皆引既有條文）。
- **測試**：`tests/test_ui2_batch3.py`（今日結論無方向推導、主要風險不被插隊〔靜態＋AppTest 整頁順序〕、模式互斥、session 隔離、我的頁 AST 守衛、三軸、無人名、判定器 teeth）；既有 `tests/test_ui2_guards.py`／`test_ui2_batch2.py` 的 `_all_fields`／預期態數只增不減。
- **不得誤讀**：本批全為 FAKE；「第一屏放得下」**不是** Visual Fidelity Gate 判定（`NUI2-VF-HARNESS` 仍 open）；搜尋為 disabled 示意、今日結論為 FAKE 示意句、帳戶為 FAKE skeleton。
- §13 收尾 Gate：新 Rule＝無；新 Decision＝無；其餘見 BACKLOG §5.1.24、Migration Contract §9、PROJECT_STATE §56。

- 📌 **§17 補（獨立 QA 修正後；append）**：
  - [ ] **🎯 查一檔 cold**：只有搜尋框＋灰色說明（⛔ FAKE-0001 頭／Snapshot／加入觀察）〔Wireframes §6〕。
  - [ ] **W-4 色調**：context 行與『市場環境』格 Neutral＋文字狀態；其他欄位 Unavailable 仍紅、Stale 仍琥珀〔W-4；Freeze §4.1；~~單組判讀待覆核~~〕。 📌 **2026-11-03（DEC-127）客戶接受 Neutral／Info 方向，已收斂為 accepted／implemented，不再待覆核**；驗收改查 §18 第 2 項（有意識的更新，不是漏刪；決策者 客戶〔DEC-127〕）。
  - [ ] **市場 L1 之前無 L2／L3／expander**（預設道 AppTest）。
  - ⛔ SUPERSEDED / HISTORICAL — NOT ACTIVE（DEC-128 S32，部分）：擴大為「📊🎯💼**整頁**無完整 evidence expander（👤 稽核面入口為明列例外，仍不得有 evidence 類 expander）」（見 §20 T-new-1）；「L1 之前無 expander」維持。
  - [ ] **更新 CTA 順序（`NUI2-MARKET-REFRESH-CTA-ORDER`）**：凍結線框／DEC-117 Q5＝頁首→更新 CTA→今日結論→3 tile；實作＝CTA 在第一屏最後（q4）。~~**偏離未裁示**，驗收時須判定修正或裁示。~~ 📌 **2026-11-03（DEC-127）已依 frozen contract 修正，驗收改查見 §18 第 1 項**（客戶裁示：implementation deviation、不開 Decision Gate；有意識的更新，不是漏刪；決策者 客戶〔DEC-127〕）。
  - [ ] 觀察項：signed-out『Google 登入』重複（`NUI2-ME-DUP-LOGIN-BUTTON`）；Risk Cap 缺值明寫範圍（`NUI2-Q21-RISKCAP-MISSING-WORDING`）；手機主要風險後餘裕 2.5px（`NUI2-MAIN-RISK-NAV-MARGIN`）。

## §18 DEC-127 小型 presentation correction 驗收項（2026-11-03；append-only；實作組單組，**待總管複驗／獨立 QA／客戶驗收**——下列 `[ ]` 為驗收者勾選，實作組不自勾）

- [ ] **1. 📊 市場更新 CTA 順序**：手機與桌機皆為 頁首→🚀 更新今日戰情 CTA→今日結論→（手機：①／Risk Cap／②／③；桌機：3 tile→②→③），今日主要風險仍緊接其後；四問內容、VM 語意、System Action／Risk Cap 欄位**未變**；持股／我的頁 CTA 位置未動。證據：判定器 `market_cta_before_conclusion`（70 態全過）、`tests/test_ui2_batch3.py` §9 `test_cta_order_*`；截圖 `docs/vnext/newui2_batch3b/mobile_p4_market_*.png`（**請逐張目視**）。⚠️ 桌機 CTA 為結論之上獨立緊湊列，與線框『頁首列右側』非逐像素等同（`NUI2-MARKET-CTA-DESKTOP-PLACEMENT`）。
- [ ] **2. W-4 context row（客戶已接受；不再待覆核）**：輕量一行 chip、Neutral／Info、字級 < 查詢摘要與 6 維格、在搜尋與查詢摘要之下、『市場環境』不排第一格、無方向／買賣字樣、與市場頁位階同源。逐點鎖定測試見 `test_w4_contract_points_are_each_locked_by_a_test`。⚠️ 『不搶過 基本面／valuation／company-first research』目前只能對現有區塊驗，區塊落地後須重驗（`NUI2-W4-RECHECK-WHEN-RESEARCH-BLOCKS-LAND`）。
- [ ] **3. 手機底部導覽餘裕**：FAKE 六場景『今日主要風險之後第一區塊距導覽上緣』≥ 1 行行高（stale／unavailable 2.5px→42px）；壓力態（L1 文字 1.5×）六場景捲到底後內容不被導覽遮住（餘裕 26.5–27.2px）、無水平捲動；不縮字、不刪資訊。證據 `docs/vnext/newui2_batch3b/viewport_measurements.json`（1.59.2）與 `viewport_measurements_streamlit156.json`（1.56.0）各 70/70；`test_nav_margin_*`。⚠️ 『≥1 行行高』為 AI 總管內部判準（`NUI2-NAV-MARGIN-CRITERION-INTERNAL`）。
- [ ] **4. 仍未驗（誠實保留，⛔ 不得宣稱已驗）**：iOS safe-area（`env(safe-area-inset-bottom)`；Chromium 為 0，`NUI2-NAV-SAFEAREA-IOS-UNVERIFIED`）、Safari／Firefox／真機／螢幕閱讀器（`NUI2-VIEWPORT-NON-CHROMIUM-UNVERIFIED`）、真資料字串長度（`NUI2-VIEWPORT-FAKE-ONLY`）。

## §19 NUI2-REAL-FEED A 批驗收項（A1 mapping／A2 read-only adapter／A3 real-data shadow acceptance；2026-11-03；append-only；實作組單組，**待總管複驗／獨立 QA／客戶驗收**——下列 `[ ]` 為驗收者勾選，實作組不自勾）

- [ ] **1. A1 mapping 落盤**：`docs/vnext/NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` 四頁逐欄（UI2 Field → VM → canonical → provenance → freshness／missing → 分類）、兩組盤點差異裁定（§1）、SG 清單（§6）、跨頁 fact（§7）、OAuth／Sheet（§8）、Fake→Real 邊界（§2）。⚠️ 單組整合；計數非 AST 窮舉。
- [ ] **2. 只接 2 個事實**：台股加權指數（📊 卡）、市場位階（📊 現在狀態＋L2 位階說明、🎯 W-4、🎯 市場環境，**同一次呼叫**）。其餘欄位 Real 模式＝`⬜ 尚未提供`＋原因（⛔ FAKE 值／補 0／中性）；Risk Cap 恆 `⬜ 無法判定`；動作欄恆待 Aggregator；💼／👤 不呼叫 `get_holdings`／`get_account`／`build_login_url`。證據：`tests/test_ui2_real_feed.py` §2～§5。
  - ⛔ SUPERSEDED / HISTORICAL — NOT ACTIVE（DEC-128 S32／S33，部分）：「市場位階＋L2 位階說明」中的 **L2 位階說明**落點改為 👤 資料健康度·市場位階項 Level 2；「只接 2 個事實」維持。
- [ ] **3. 語意映射**：台股 例外／failed→Unavailable、`ok=False`→Missing、stale→`⚠ 過期 N 天`、`is_stale=None`→`⚠ 可能已過期`（**AI 總管內部判準，可推翻**）；位階 unloaded→`⬜ 尚未載入`＋L0 說明、缺真實廣度→`⬜ 未評估／資料不足`（Unable to Determine）、讀壞→Unavailable（strict，端到端以壞 `macro_state.json` 實測）、未知 source／契約矛盾→raise；位階 as_of＝`⬜ 資料日未提供`（⛔ `cl_ts`）；source＝「規則分支 id：…（非資料來源）」。
- [ ] **4. Real／Fake 可區分**：banner「Real-data Preview（非正式 production default）」；`scenario_id="real"` 不在 `SCENARIO_IDS`；real 任何字串 ⛔ `FAKE`、fake source 必 `FAKE`（雙向）；預設 feed 仍 FAKE；FAKE 六場景 regression 全綠。
- [ ] **5. 守衛（加性）**：G2 規則一字未改（範圍扣除具名 `FEED_FILES`）；G2F（24 項注入）；G9 補洞（整包 session_state 傳遞／別名，5 項注入）；capability allowlist 明確加 `real_canonical.py`。
- [ ] **6. no-write proof**：(1) AST G2F＋mutation；(2) AppTest runtime 紀錄器：Real 模式四頁＋查一檔期間 session 寫入 0 次（首跑只寫明列 `ui2_page／ui2_scenario／ui2_account／ui2_feed`）；(3) 工作樹全檔（含 git 忽略檔；純 Python）mtime＋size，及 `data_cache/**`、`macro_state.json`、`risk_cap_state.json` sha256＋mtime 前後相同（另人工 `git status --porcelain` 前後比對相同）；(4) socket connect guard＝0 次連線（且真讀本地檔仍成功）。
- [ ] **7. mutation ≥6 實測轉紅後還原**：見 `docs/PROJECT_STATE.md` §58（13 項）。
- [ ] **8. viewport（real 模式）**：390×844／1440×900，四頁＋🎯 查一檔＋手機市場壓力態＝11 態；Streamlit 1.59.2 與 1.56.0 各 11/11；新判定 `real_feed_banner_on_top`。證據 `docs/vnext/newui2_realfeed/`（**手機五張請逐張目視**）。⚠️ 手機市場頁主要風險後餘裕僅 27.8px（`NUI2-REALFEED-REGIME-L1-BRIEF`）。
- [ ] **9. ⛔ 不得勾選為 C5 通過**：本批是 shadow（Migration Contract §10）；§9 各項（真機、Cloud、AI Failure、四頁真資料全通）**仍未驗**（`NUI2-REALFEED-ACCEPTANCE-OPEN`）。
- [ ] **10. QA 修正批（兩組獨立 QA 後；2026-11-03 append）**：(a) 白名單不變量：只有 5 個已接落點＋明列契約固定欄可帶資料，跑在 42 種注入組合（`tests/test_ui2_real_feed.py` §9）；(b) 錯誤原文不上畫面／不進 snapshot、只進 log（§10）；(c) G2F 精確 import 白名單＋反射禁令、G2／G2F／G9 相對 import 違規、G9 `session_state` 用法白名單（`tests/test_ui2_guards.py`）；(d) 契約違反＝讀取期隔離（該欄紅色 Unavailable＋log、另一事實照常；**實作組判斷、可推翻**）；(e) mapping 更正「零網路」→「呼叫期 0 連線；import 期 eager 鏈可連 proxy」。mutation 13 項見 PROJECT_STATE §58 補。
- [ ] **11. 複驗最後一輪（2026-11-03 append）**：**AST 守衛為 defense-in-depth、非窮舉；主要 no-write 證明＝runtime session 紀錄器＋socket guard＋檔案指紋**（`tests/test_ui2_real_feed.py` §6）。已知靜態限制登記 BACKLOG `NUI2-GUARD-STATIC-LIMITS`。本輪：`is_stale` 身分比較＋`ok`／`failed` 矛盾、通用禁令（dunder／動態 import／exec／eval；G2 時鐘與 pandas 讀寫；G9 `streamlit.runtime`）、白名單不變量改位置判斷＋原因句數字樣式、錯誤代碼降級（`RealFeedSnapshot.of()`）。mutation 9 項見 PROJECT_STATE §58 補。

## §20 DEC-128 Presentation Compression／Active Rule Supersede Cleanup 驗收項（2026-11-03；append-only；實作組單組，**待總管／獨立 QA 勾選——本節未自勾**）

> 依客戶 2026-11-03 (13)。每項由**非實作組**獨立 QA 勾選（`CLAUDE.md` §-1.5 第一條 3）。docs 批的項目 1～10；UI correction 批（BACKLOG §5.1.26）另以 T-new-1～6 為驗收依據。

1. [ ] DEC-128 存在，客戶原文 fence 與客戶 (13) 原訊息逐字一致（fence 為總管轉交全文）；取代範圍表 S21～S35 逐列可在原文位置查到（獨立抽驗）。
2. [ ] 舊 DEC（072／076／081／091／105／109／111／112／117／122）原文一字未改（`git diff` 只有新增行；`DECISIONS.md` 僅新增 📌 行與 DEC-128 本體）。
3. [ ] `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md` 存在，頂端寫明「現行唯一有效 presentation contract；與其他文件衝突時以本文件與 DEC-128 為準」。
4. [ ] 被取代文件（Freeze、Wireframes、Presentation Contract、Capability Map、Architecture Gate、Migration／Cutover、Audit Checklist、Real Feed Mapping、Visual Fidelity Gate、ME Page Draft）含 `SUPERSEDED / HISTORICAL — NOT ACTIVE` 橫幅且指向 DEC-128 與 Active Contract；**未誤標**：DEC-127 的 CTA 順序、W-4、Wireframes §1／§6／§9、DEC-124 三軸、Single Action Authority 仍有效。
5. [ ] `PROJECT_RULES.md` 第 30 節 8 點與客戶原文一致；§24.2 三層判準已加刪除線＋📌（原文仍在）。
6. [ ] **獨立**第二組全 repo 掃描（含反向掃描：免／不必／例外／直接做／摺疊／expander／下沉）未找到仍把 L2／L3 頁內摺疊描述為**現行**規格的殘留（`NUI2-ACTIVE-CONTRACT-INDEPENDENT-AUDIT`）；結論前 ⛔ 宣稱「已無牴觸」。
7. [ ] `tests/test_ui2_active_contract_docs.py` 綠；mutation（拿掉橫幅／刪 DEC-128 關鍵句）實測轉紅；`PENDING_UI_CORRECTION_TESTS` 清單與 BACKLOG §5.1.26 測試改動清單一致。
8. [ ] 本批 `git diff --name-only origin/main` 只含 `docs/`、`PROJECT_RULES.md`、`tests/test_ui2_active_contract_docs.py`；0 條既有測試斷言變更；無 xfail／skip 新增。
9. [ ] PROVISIONAL 項（DEC-128 §四 (a)～(d)）在所有文件中**皆標 PROVISIONAL**，沒有被寫成「客戶已核准」。📌 **2026-11-03 更新（DEC-130）**：(a)(b)(c) 已由客戶 (15) 升為正式 Active（(a) 有條件同意），本項改驗「各文件不再把 (a)(b)(c) 標 PROVISIONAL、且 (a) 以兩軸分離語意書寫」（見 §21）；非 (a)(b)(c) 的撰寫組暫定項仍須標明未經客戶覆核。
10. [ ] 未碰 Decision Digest schema／Risk Cap／System Action／新資料 contract／公式／門檻／source。
11. [ ] DEC-129：fence 與客戶 (14) 原文逐字一致；Active Contract 開頭 11 點 Active interpretation；§2.5 Account Area（不算第五頁、手機四格、不由 URL／query 猜登入、`ui2_account`≠auth contract）。
12. [ ] 舊斷言改寫（BACKLOG §5.1.26「已改／移除的舊測試」5 項）逐一確認屬「保護已失效 presentation」而非資料／語意安全；DEC-124 三軸、G2／G2F／G4／G9、no-write、白名單、禁用字樣守衛 `git diff` 無放寬。
13. [ ] `tests/test_ui2_contract_teeth_pending.py`：7 個（📌 DEC-130 後為 9 個，新增 T_new_8／T_new_9）strict xfail 皆為新 UI 行為斷言（非現有安全測試）；UI 批修好時必須轉為一般測試。
14. [ ] 獨立稽核增補：DEC-128 §七 S38～S44 逐列在原文位置可查；Gate A8／V11、Architecture Gate G3、Presentation Contract §12.2／§12.3 橫幅到位；Active Contract 的 PROVISIONAL 擴充處（Level 預設／Level 3 嚴格化）標明；`tests/test_ui2_active_contract_docs.py` 的 sha256 pin、逐節橫幅配對、逐 decorator strict 檢查綠且 mutation 轉紅。

## §21 DEC-130（客戶 (15) 覆核 PROVISIONAL (a)(b)(c) 升 Active）驗收項（2026-11-03；append-only；實作組單組，**待總管／獨立 QA 勾選——本節未自勾**）

1. [ ] DEC-130 fence 與客戶 (15) 原文逐字一致（sha256 釘住）；DEC-128 §四 有 📌 指向 DEC-130，(a)(b)(c) 原文未改。
2. [ ] Active Contract §5.1：Data State 五態與 Capability 兩軸分離；四對映（✅→OK、◷→Stale、◇→Missing、⛔→Unavailable）；`⬜ 尚未接線` 明寫「不是 Data State」；Not Evaluated 不併入 `⬜`；表格每列兩個分離欄位。
3. [ ] (b)：稽核面預設收合；🎯 選股條件精簡、完整 rule detail 不上主頁、全部候選／CSV 次層、不做成資料牆。(c)：`?ui2_dev=1`、不顯示給一般使用者、不放 sidebar、不增導航、不曝光 secret、**`ui2_dev` 不得當登入證據**。
4. [ ] 各文件（BACKLOG／PROJECT_STATE／HANDOFF／PROJECT_RULES §30／橫幅）不再把 (a)(b)(c) 當 PROVISIONAL；舊字僅以刪除線＋📌 保留。
5. [ ] 新守衛 `check_axis_separation`／`check_ui2_dev_not_auth` 對真檔 0 違規、對注入違規轉紅；`T_new_8`／`T_new_9` 為 strict xfail（reason 含 DEC-130）。
6. [ ] `git diff --name-only origin/main` 只含 `docs/`、`PROJECT_RULES.md`、`tests/`；src／shared／app.py 零變更；`NUI2-ACTIVE-CONTRACT-INDEPENDENT-AUDIT` 未被宣稱完成。
