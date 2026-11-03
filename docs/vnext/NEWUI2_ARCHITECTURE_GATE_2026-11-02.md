# New UI2 Architecture Gate（New UI2 Greenfield Presentation Layer 架構閘門）

> ⛔ **SUPERSEDED / HISTORICAL — NOT ACTIVE（部分；DEC-128，客戶 2026-11-03）**：本檔下列範圍**已不是現行規則**——§4.3 P9 Digest Viewer 的「L2 raw structured snapshot」位置（MIGRATE→👤 資料健康度 Level 3，S28）。**本檔其餘條文（§1.5 invariant、§4 View Model 邊界、§5 Migration、§7 Preview strategy、§9 守衛）全部仍有效**，DEC-128 對本檔只**補**兩條（見 §1.5 與 §7 的 📌 補註）。**現行唯一有效讀法**＝`docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md` 與 `docs/DECISIONS.md` DEC-128；與本檔衝突時以該文件為準。**本檔其餘條文仍有效**；舊文一字未刪（歷史證據）；⛔ 不得依本檔被取代的範圍施工。（有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-128）。）

- **狀態**：**客戶核准（Q1=A／Q2=A〔修正分類〕／Q3 四頁線框核准／Q4=A，2026-11-02；逐字見 DEC-123「客戶裁示 Q1～Q4」）；~~待 #997 獨立稽核＋合併後凍結~~ #997 獨立稽核兩輪完成（第一輪 PASS with fixes → 第二輪 PASS）；**#997 合併即凍結**（merge SHA 由下一位補記）**（2026-11-02 #997 獨立稽核第二輪 PASS 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕；原文刪除線保留）。凍結後**下一個唯一安全工作**＝發 🟡 Model／Effort Change Gate，**客戶切換 Model×Effort 至 Sonnet 5.5＋Medium** 後，經 **implementation Gate** 開第一個 New UI2 批次（建議先 `NUI2-GUARD-REGISTRATION`／View Model boundary（`NUI2-VM-BOUNDARY`）／Preview 入口骨架（`NUI2-PREVIEW`），≤3 項，fake／snapshot 資料）；**未經客戶切換與 Gate 不得開始 implementation**；System Action Aggregator 實作另需 implementation Gate（`NUI2-AGGREGATOR-IMPL`）。#996 已合併（main＝`acd1648c`）；本 Gate 已落盤為 commit `6d30dcea`、Draft PR #997（分支 `ccr-a0b4e085-ijdaio`）。⛔ production coding（含 System Action Aggregator runtime）：Architecture 凍結並發 Model／Effort Change Gate 前一律不得施工；Aggregator 另須 implementation Gate（§4.6）。（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）<br>原文：~~**Architecture Gate 草案，待客戶裁示**（§11 送客戶四題：**G1 預覽、G3′ System Action Aggregator（系統動作彙整層）、四頁線框核准、G2 cutover＋#996 合併確認**，皆 **PENDING**）。⚠️ **本 Gate 目前只存在於工作樹**（受「只能推指定分支」權限限制；#996 合併後才以新 PR 落盤，見 §11 G2 第 2 小題）；依 DEC-122「沒寫入 GitHub 的新規格，不視為正式完成」，落盤前**不是正式文件**。獨立稽核（2026-11-02）判 **PASS with fixes**，本版已依修正項 F2～F7、m1～m6 改寫（單組稽核）。本檔**不是 Approved 規格**；客戶裁示前，本檔所有「目標架構／目錄／守衛」一律只是提案，⛔ 據以寫任何 production code（客戶 (5)-5「本批禁止 production coding」）。~~
- **日期**：2026-11-02　**基準（裁示整合批）**：`origin/main`＝`acd1648c`（#996 合併點；總管實查）；本檔所在分支 `ccr-a0b4e085-ijdaio`（#997）。以當下 `git fetch` 為準。**基準（初稿，歷史）**：工作樹＝PR #996 head `139e315b`；撰寫組 2026-11-02 `git fetch origin main` 實查 `origin/main`＝`c1e10a62`（#995），HEAD 比 main 多 1 個 commit（#996 收斂批）。⚠️ cron 會推進 main，**一律以當下 `git fetch` 後的 `origin/main` 為準**（DEC-118），不得引用本欄當最新 main。
- **決策來源**：客戶 2026-11-02 裁示 **(5)「New UI2 Greenfield Presentation Layer」**（逐字收錄於 `docs/DECISIONS.md` **DEC-123** fence；本檔與原文有出入時以原文為準）。下文〔客戶 (5)-n〕＝該裁示第 n 節原文要求。
- **上位與輸入**：`CLAUDE.md`（§-2、§-1.5、§1、§8.2）> `PROCESS.md` > `PROJECT_RULES.md`＋`docs/governance/*` > DEC-123 > DEC-122 > 本檔。**`docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md`（下稱 Freeze）全部 semantic contracts 是本檔的 input**〔客戶 (5)-2「New UI2 必須以這些 semantic contracts 為 input。不要因為 New UI2 而重新發明投資語意」〕；本檔**不重新定義**任何四態、chip、Risk Cap、Single Action、freshness、估值、Digest、OneBrain 條文，只寫「New UI2 怎麼承接」。
- **配套文件**：Reuse Matrix＝`docs/vnext/NEWUI2_REUSE_MATRIX_2026-11-02.md`；四頁線框＝`docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md`。
- **標記**：**FACT**＝撰寫組或兩份調查（invC Reuse Matrix、invD 架構約束，皆 2026-11-02、單組、唯讀）讀碼／grep／實跑；**INFERENCE**＝推論；**DOC**＝轉述文件；**AI 總管暫定**＝內部技術自決（`CLAUDE.md` v3 §03-1），客戶可推翻；**PENDING**＝待客戶裁示。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：本檔由**單一撰寫組**依兩份**單組**調查（invC、invD）撰寫，**未經第二組獨立驗證**。文中「0 命中／只有／不存在／沒有」皆為 grep 結果、**非窮舉**。撰寫組另自行抽查 6 項事實（`src/ui2`／`app_ui2.py`／`pages/`／`shared/ui2_contract*` 不存在；c3 guard `_PATH_LAYERS` 僅具名登記 `src/ui/views/`、`src/ui_v2/`；`push_holdings_daily`／`push_weekly_report` cron 存在；`market_alert_banner` 的「建議持股降至」10%／20% 字串與 `holdings_digest_message`「請以警語為準」存在；`page_hold` 經 `app_ai_service.gemini_call` 注入 Gemini）——皆命中，但仍是單組。**三個承重判定**（§4 VM 邊界、§5 Migration 邊界、~~§4.5／§11 G3′「系統動作彙整層不算新增 runtime」界線~~ §4.6 System Action Aggregator 契約〔客戶 Q2 已裁示屬新 runtime component，原「不算新增 runtime」判定作廢〕（2026-11-02 #997 獨立稽核 PASS with fixes 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔稽核修正〕；原文刪除線保留））**只能當待驗事項**，Architecture 凍結前須另派一組獨立稽核（BACKLOG `NUI2-ARCH-SECOND-AUDIT`）。

---

## §0 怎麼讀（客戶 (5)-5 的 12 項 → 本檔落點）

| # | 客戶 (5)-5 要求 | 落點 | 狀態 |
|---|---|---|---|
| 1 | New UI2 Architecture Proposal | §1 | 草案 |
| 2 | Reuse Matrix | §2 → `NEWUI2_REUSE_MATRIX_2026-11-02.md` | 草案（88 列） |
| 3 | 四頁 textual wireframe | §3 → `NEWUI2_WIREFRAMES_2026-11-02.md` | ~~**待客戶核准**~~ **客戶核准（Q3）** |
| 4 | View Model boundary | §4 | 草案（承重，待第二組驗） |
| 5 | Migration boundary | §5 | 草案（承重，待第二組驗） |
| 6 | proposed directory structure | §6 | AI 總管暫定，客戶可推翻 |
| 7 | Preview strategy | §7 | ~~**PENDING G1**~~ **客戶核准（Q1=A；§7.3）** |
| 8 | Cutover strategy | §8 | ~~**PENDING G2**（含 #996 合併確認）~~ **客戶核准（Q4=A；§8.3、`NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md`）；#996 已合併** |
| 9 | Testing strategy | §9 | 草案 |
| 10 | UI／LINE／Decision Digest／OneBrain consumer boundary | §10 | 草案（LINE 只定 interface／ownership） |
| 11 | 真正需要客戶裁示的 Decision Gates | §11 | ~~**PENDING**：G1 預覽、G3′ System Action Aggregator（系統動作彙整層）、四頁線框核准（W-4、W-5、W-9、W-10、W-11）、G2 cutover＋#996 合併確認~~ **已裁示（Q1～Q4＋#996，2026-11-02）** |
| 12 | 必要 GitHub governance docs 同步 | §12 | 本批同步清單（裁示整合批見 §12.3） |
| — | Migration／Cutover Contract；Audit／Acceptance Checklist | `NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md`、`NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md` | 客戶 (6) 要求同步（裁示整合批新增） |
| — | System Action Aggregator 契約 | §4.6 | **客戶核准（Q2）；只凍結 contract，⛔ 實作** |
| — | 完成條件（客戶 (5)-13） | §13 | — |
| — | 未驗與限制 | §14 | — |

---

## §1 Architecture Proposal

### §1.1 定位（客戶原文）

〔客戶 (5)-3〕「**全新的 Presentation Layer，但沿用成熟的底層資料與投資邏輯。**」〔客戶 (5)-0〕「**這不是整套系統重寫。**」

- New UI2 重做的只有 Presentation Layer（〔客戶 (5)-6〕：shell、navigation、card system、layout、chart container、responsive、status presentation、source／freshness presentation、empty／stale／unavailable states、OneBrain summary container、audit presentation）。
- 底層一律優先保留（〔客戶 (5)-6〕：canonical data、services、source adapters、deterministic rules、valuation logic、Risk Cap logic、freshness／provenance、validated domain tests、pure helpers）；**本批及其後 UI2 施工 ⛔ 重寫既有 data／services／rules**〔客戶 (5)-1〕。

### §1.2 三代 UI 邊界〔客戶 (5)-4〕

| 代 | 程式位置（FACT） | 定位（客戶原文） | 現行入口（FACT，讀碼） | 本批與 UI2 施工期的處置 |
|---|---|---|---|---|
| **Old UI** | `src/ui/tabs/**`、`src/ui/etf/**`、`src/ui/pages/**`、`src/ui/render/**`、`app.py` 內嵌區塊（舊 7 頁籤） | 「只讀 Logic／Capability Reference。**禁止修改**。」 | `?legacy=1`（`app._nav4_resolve_legacy`；DEC-097 不放可見連結） | ⛔ 修改、⛔ 刪除〔客戶 (5)-1〕；UI2 ⛔ import（§6 G4）；需要的業務邏輯走 §5 PORT（新位置另建＋parity 測試，**Old UI 原檔一字不改**） |
| **現有 New UI → Legacy New UI／Reuse Candidate** | `src/ui/views/**`（四頁＋五頁 legacy 依賴樞紐）、`src/ui_v2/**`（共用元件與五頁版面契約） | 「改為 Legacy New UI／Reuse Candidate。**停止把持續 patch 當正式主線**。」 | 預設四頁（`shared/ia_nav4.PAGE4_TO_VIEW`） | ⛔ 刪除〔客戶 (5)-1〕；**不再當主線 patch**；只在 (a) 線上真 bug 觸發（`CLAUDE.md` §-1）或 (b) §5 PORT 需要把純函式搬出時才動，且以 byte-identical 守衛證明零行為變更 |
| **New UI2** | （尚不存在；§6 提案 `src/ui2/**` 等） | 「**未來唯一主要 Presentation Layer**。」 | （尚無；~~§7 Preview、§8 Cutover PENDING~~ §7 Preview＝Q1=A、§8 Cutover＝Q4=A（客戶已核准）） | 本批只做 Architecture Gate；⛔ production coding〔客戶 (5)-5〕 |

- **Cutover ≠ Removal**（INFERENCE，同 NAV-1 先例）：UI2 成為預設只是路由翻轉；Old UI 與 Legacy New UI 的刪除各自走 Removal Gate（Freeze §19 六條件∪DEC-083 第 11 點 E 段七步）。UI2 帶來第三代 → Capability Map 須擴成 **Old → Legacy New → UI2** 三欄（BACKLOG `NUI2-CAPMAP-3COL`）。

### §1.3 目標架構鏈與未來 Digest／OneBrain 鏈（客戶原文逐字）

**目標架構**〔客戶 (5)-3，逐字〕：

```
Canonical Data / Sources
↓
Normalization / Validation
↓
Deterministic Rules / Formulas
↓
Risk Cap / Hard Constraints
↓
System Action State
↓
View Model / Presentation Contract
↓
New UI2
```

**未來**〔客戶 (5)-3，逐字〕：

```
System Action State
↓
Decision Digest
↓
OneBrain
```

**LINE 邊界未來方向**〔客戶 (5)-10，逐字〕：

```
System Action State
↓
Decision Digest
↙        ↘
New UI2   LINE
↓
OneBrain summary
```

「**New UI2 與 LINE 都是 consumer。**」〔客戶 (5)-3〕

- 與 Freeze §0.1.2 正式架構鏈（Canonical Data → Rules → Risk Cap → System Action State → Decision Digest → OneBrain → UI）**同向**（INFERENCE）：本鏈把「View Model／Presentation Contract」明確放在 System Action State 與 UI2 之間；Digest／OneBrain 成熟後，View Model 的輸入由「System Action State＋既有規則輸出」換成「Decision Digest」（§10.2）。
- **FACT（現況缺口，invC §9 N7／N11、invD §5.1）**：`System Action State` 層**不存在**（grep `system_action|SystemAction` 0 命中，非窮舉）；`decision_digest_builder.build_decision_digest` **0 production caller**；`st.session_state` 是事實上的狀態匯流排。⇒ UI2 第一版能讀到的「System Action」只能是既有正式分支（ETF `action_branch` 七分支、個股 `swap_level` 四級）與 Risk Cap 閘門輸出——這個過渡安排是 ~~§4.5／§11 G3′（系統動作彙整層）~~ **§4.6 System Action Aggregator**（客戶 Q2：只凍結契約、implementation Gate 後實作；cutover 前必須完成，§4.6.5）（2026-11-02 #997 獨立稽核 PASS with fixes 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔稽核修正〕；原文刪除線保留）。

### §1.4 四頁 IA（固定）〔客戶 (5)-7〕

只維持 **1. 📊 市場　2. 🎯 標的　3. 💼 持股　4. 👤 我的**；⛔ 新增第五個主要頁面〔客戶 (5)-7〕。SSOT 沿用 `shared/ia_nav4.PAGE4_LABELS`（FACT；KEEP AS-IS，Reuse Matrix L0-5）；🎯 標的頁「市場精選／即時查一檔」是**頁內模式切換**，⛔ 新 IA 層（Freeze §3.1 第 4 點）；👤 我的頁的 Audit 是**頁內區塊**，⛔ 第五頁。

### §1.5 永久 invariant（客戶原文；UI2 施工期全部適用）

> 📌 **DEC-128 補註（2026-11-03；補充、非取代）——Human UI ViewModel ≠ Decision Digest（OneBrain）Context 雙 projection**：Complete Evidence Layer 之後分成**兩個 projection**——Human UI ViewModel（簡化、Chart-first、關鍵 evidence、少量文字）與 Decision Digest／OneBrain Context（完整正式 evidence、Missing、provenance、source、as_of、freshness、deterministic results、Risk Cap、System Action、counter-evidence、limitations、cross-page context）。**UI 沒顯示的資料，不代表 OneBrain 不得讀；OneBrain 能讀的資料，也不代表 UI 必須全部呈現。** 本檔 §4.2-6（context／slice 兩層）的 `context` 是「Human UI 全量」，**不是** Decision Context。細節見 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md` §8。


〔客戶 (5)-8，逐字〕：
- UI 越簡潔，Decision Context 不能越少
- Presentation Slice ≠ Decision Context ≠ AI Output
- System Action State 是唯一正式動作權威
- OneBrain 只負責 reasoning / summary / explanation
- OneBrain 不得覆寫 deterministic action
- UI 不得自己創造正式投資規則

核心原則：「**簡化 UI，但不簡化 Decision Context。**」「UI 可以少顯示。底層資料不能因 UI 精簡而減少。」〔客戶 (5)-8〕
- 與 Freeze §0.1.3 六條、§1 三條**全部同向且並存**（Freeze 六條中的「OneBrain 不得創造第二套 portfolio action、不得繞過 Risk Cap」「OneBrain 應讀完整 Decision Digest」**繼續有效**，本節不取代）。

### §1.6 Mobile-first 第一屏四問〔客戶 (5)-9〕

每頁第一屏（手機 390×844 優先）**優先回答**：**1. 現在狀態　2. 是否需要行動　3. 下一步　4. 主 CTA**。「**禁止先做 desktop 再縮手機。**」〔客戶 (5)-9〕
- 與 Freeze §0.1.6（Q3=A 市場頁手機第一屏四必要項）、Freeze §16 各頁「不用滑」項目**疊加取嚴**（INFERENCE）：四問是**每頁的通用框架**；各頁的「不用滑」必要項（市場：市場目前狀態／Risk Cap／是否需要行動／主 Update CTA；標的：mode／search／查詢摘要；持股：portfolio status／Risk Cap／是否需要處理；我的：connection state／primary management actions）是**該頁對四問的具體答案**。對照與逐頁版面見線框檔 §1。
- 「是否需要行動」**只能讀 System Action State／既有正式分支**（invC N13）；⛔ 由市場位階或 UI 自行推導（推導＝新投資語意）。市場頁 ⚡ N 的過渡來源（System Action Aggregator（~~系統動作彙整層~~）建好前維持既有 `_market_blocks.render_alerts_block` 語意或 `⬜ 尚未提供`）＝線框 **W-10**，~~待客戶核准~~ 客戶已核准（Q3，transitional contract；線框 §9）。判不出 → `⬜ 尚未評估`，⛔ 寫「今日無需調整」（Freeze §0.1.5 第 4 點）。

---

## §2 Reuse Matrix（指向）

正式版＝**`docs/vnext/NEWUI2_REUSE_MATRIX_2026-11-02.md`**（88 列；六類 KEEP AS-IS／WRAP／PORT／REIMPLEMENT／RETIRE LATER／DO NOT TOUCH；tests 分類量級；Top 10 風險；限制）。

摘要（FACT，invC §10 機械計數；列數是矩陣粒度、**不是檔案數**）：KEEP AS-IS 26／WRAP 21／PORT 24／REIMPLEMENT 2（＋UI2 全新 shell 等非既有列）／RETIRE LATER 5／DO NOT TOUCH 10。tests：domain ≈298 KEEP；New-UI-bound ≈130「先 PORT 斷言再退場」；Old-UI-bound ≈148 DO NOT TOUCH；≈77 未判定（regex 啟發式量級）。

---

## §3 四頁 textual wireframe（指向）

正式版＝**`docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md`**（狀態：~~**待客戶核准**~~ **客戶核准 Q3**）。每頁**先手機 390×844、再桌機 1440×900**；每頁第一屏回答四問；落實 Freeze §0.1 Q1／Q2／Q3；標的雙模式；持股第一屏；我的（設定＋Audit 四入口）；L1／L2／L3；冷啟動／Missing／Stale／Unavailable／Not evaluated 態。線框核准是客戶 (5)-13「four-page wireframe approved」條件；**核准前 ⛔ 寫任何 UI2 頁面 code**（`CLAUDE.md` v3 §03-2 ① 草稿先行）。

---

## §4 View Model boundary（承重；待第二組驗）

### §4.1 定義

View Model（VM）＝**把既有正式輸出（L3 service 回傳值；未來＝Decision Digest）轉成 UI2 可直接渲染之結構的純函式層**。VM 是「Presentation Contract」的程式化落點（目標鏈中的「View Model／Presentation Contract」）。

### §4.2 硬規則（AI 總管暫定；對齊客戶 (5)-8「UI 不得自己創造正式投資規則」＋Freeze §13／§14）

> ⛔ SUPERSEDED / HISTORICAL — NOT ACTIVE（DEC-128 S38）：「VM `context`（將來＝Digest）」的讀法已更正：`PageVM.context` 是 **Human UI 全量**（presentation 前的完整 VM），**不是** Decision Context／Digest；Digest 由 canonical services headless 組裝，不由 UI2 VM 衍生（Freeze §14；Active Contract §8）。四情境等價測試（G3）的判準本身（輸出不受 top_n／收合影響）維持。現行見 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`。本節其餘仍有效。


1. **純函式**：VM builder 輸入＝已取好的 feed 結果（L3 回傳物件），輸出＝L0 VM 型別（frozen dataclass）；⛔ I/O、⛔ 網路、⛔ cache、⛔ 讀時鐘以外的外部狀態（時間由參數傳入）。
2. **只讀既有 L3 輸出**：VM ⛔ import `src.data.*`（L1）、⛔ import `src.ui*`（Old UI／Legacy New UI）、⛔ import `streamlit`。取數唯一入口＝`*_feed.py`（§6），feed 只**原樣帶出**既有 service 結果（同 `market_twii_view_service` 先例：薄 L3、帶 provenance／is_stale）。
3. **⛔ 新增任何寫入**：VM 與 feed ⛔ 寫 `st.session_state` 投資狀態 key、⛔ 寫檔、⛔ 寫 Sheet；feed 呼叫既有服務時**只觸發既有服務的既有副作用**（例：`allocation_service.get_allocation` 的 cache key、主 Update CTA 觸發的既有 `refresh_macro_now` 鏈），⛔ 新增任何副作用；UI2 L5 只可寫 `ui2_` 前綴的**純 UI 狀態**（目前頁、模式、展開）（invD C-SS-1／C-SS-3）。
4. **⛔ 聚合動作**：動作的彙整（合併 ETF 七分支與個股四級、加／留／換／減計數、「沒事 vs 判不出」、加碼列 Risk Cap 標註、跨頁 ⚡ N）**只屬System Action Aggregator（~~系統動作彙整層~~）（~~§4.5~~ §4.6）**；VM 只把彙整結果轉成呈現，⛔ 自己算。
5. **⛔ 創造投資規則**：VM ⛔ 新門檻、⛔ 新分支、⛔ 新比例、⛔ 新排序規則、⛔ 改既有分支觸發條件或優先序、⛔ 由 regime 推導「是否需要行動」、⛔ 為缺值補 0／中性／續抱／safe。
6. **VM 輸出分兩層**（Freeze §13 Presentation Slice ≠ Decision Context）：`context`（全量，與 UI 切片無關）＋`slice`（呈現切片：Top-N、收合、手機堆疊）；`slice` 只能由 `context` 截取，⛔ 反向影響 `context`；VM 函式簽名 ⛔ 讓 `top_n`／`expanded`／`tab` 影響 `context`（§9 G3 測試）。

### §4.3 允許的 presentation contract（✅ 不屬「創造投資規則」）

依 invC §9 N1～N6、N9、N10、N13、N14、N16（FACT：現況皆不存在或住在錯層），以下屬 **presentation contract，允許在 VM／L0 contract 實作**，但**一律只讀既有 SSOT**：

| # | 能力 | 允許的理由 | 約束 |
|---|---|---|---|
| P1 | **四態語意層**（Missing／Stale／Unavailable／Not evaluated）＋十態→四態 map | Freeze §5.2 已給完整對映表；四態是語意分類層，十態不改符號 | ⛔ 第 11 態（DEC-110 R8）；L1 字樣取 Freeze §5.1 |
| P2 | **Field-level freshness 物件**（value／state／as_of／source） | Freeze §9；原料在 `DatedValue`／`staleness`／`price_asof_label`／fetcher `source`、`fetched_at` | 補不到 → `⬜ 資料日未提供`；⛔ 共用全域更新時間；⛔ 補推估日期 |
| P3 | **Chip 語意色調**（Positive／Warning／Danger／Neutral-Info） | Freeze §4 四 tone | `guard_chip` 只限客戶逐字護欄句（§4.2）；Danger 文字 ≠ 取得失敗文字 |
| P4 | **「沒事 vs 判不出」的呈現**（「今日無需調整」vs `⬜ 尚未評估`） | 判定由**System Action Aggregator（~~系統動作彙整層~~）（~~§4.5~~ §4.6；Q2 核准契約、implementation Gate 後才有）**產出（沿用既有 `station_cards.cruise_or_gap`＋L0 `holdings_data_short` 規則，Freeze §0.1.5 第 3、4 點）；VM 只把結果轉成字樣 | VM ⛔ 自行判定；~~彙整層不存在時（G3′=B 期間）顯示 `⬜ 尚未提供`~~ Aggregator 實作前顯示 `⬜ 尚未提供（待 System Action Aggregator）` |
| P5 | **加／留／換／減分組的呈現** | 分組與計數由**System Action Aggregator（~~系統動作彙整層~~）**產出（Freeze §0.1.5 第 2 點「只是排版」）；VM 只排版 | 分支名原名照寫；分組外觀與「哪幾組計入今日需處理」屬線框 **W-5** ~~待客戶核准~~ 客戶已核准（Q3：W-5=A）；⛔ 讀成新規則 |
| P6 | **中立 VM 卡片型別**（取代 Old UI `tab_today.Card`） | 純型別 | — |
| P7 | **Risk Cap 閘門呈現**（`⬜ 無法判定`／`🔴 Risk Cap 超限 · 禁止新增曝險`） | Freeze §0.1.4；字串 PORT 自既有 `risk_cap_gate`（逐字不改，下沉 L0）；**加碼列的「Risk Cap 無法判定」標註由System Action Aggregator（~~系統動作彙整層~~）產出**，VM 只呈現 | Q1=A：數值未啟用前恆 `⬜ 無法判定`；⛔ 曝險分母／現金／總資產替代值 |
| P8 | **Rule Registry 讀取模型**（只讀 `RULE_ID_ALLOWLIST` 6 id＋版本常數） | Freeze §12.1 | ⛔ 編造 rule id；version／effective_from 不可得 → `⬜ 資料未備` |
| P9 | **Digest Viewer 模型**（L1 human-readable／L2 raw，過 `scrub_secrets`） | Freeze §12.2 | 真資料依賴 Stage F；之前 `⬜ 尚未提供（待 Headless Digest）` |
| P10 | **OneBrain summary container** | 槽位 | 值域詞彙 → `FUI-ONEBRAIN-VOCAB-GATE`；Stage G 前 `🤖 ⬜ 尚未提供` |
| P11 | **單檔估值 VM**（Current／Historical 槽；Forward／Scenario 槽） | Freeze §10 | Forward／Scenario 恆 `⬜ 資料未備`／`⬜ 尚未核准` |

### §4.4 禁止，需 Decision Gate（照 invC §9 列為不得做；UI2 ⛔ 自行實作）

| # | 項目 | 為何不得做 | 承接 |
|---|---|---|---|
| X1 | **Risk Cap 閘門的數值判定**（Exposure vs Cap → 真的亮 `🔴 超限`） | 需曝險分母／現金／總資產（新投資語意＋新資料源）；Freeze §0.1.4 第 5、6 點 | `FUI-RC-NUMERIC-GATE` |
| X2 | **為 16 燈等既有門檻新造 rule id 並對客戶外露** | 新規格（命名、版本、effective_from） | `FUI-RULE-ID-SPEC` |
| X3 | **Forward 估值**（Forward EPS） | 新資料源 | `FUI-FORWARD-EPS-SOURCE-GATE` |
| X4 | **Scenario 估值**（357 倍數帶等） | HI-3 未核准 | HI-3 |
| X5 | **收編 LINE 極端警語「持股降至 10%／20%」進 System Action** | 新動作語意 | `NUI2-LINE-SECOND-BRAIN`（登記；屆時送題） |
| X6 | **OneBrain `outlook`／`signal_consistency` 值域** | 撞 DEC-092 Q2、DEC-105 2A、G8 | `FUI-ONEBRAIN-VOCAB-GATE` |
| X7 | **`macro_core.recession_probability`**（未校準 logit） | Freeze §7 | `FUI-RECESSION-LOGIT-GUARD` |
| X8 | **比例 Action（減碼 1/2／全出）** | Freeze §0.1.5 第 5、6 點 | `FUI-PROPORTIONAL-ACTION-RULES` |
| X9 | **大盤 EPS×PE productionize** | Freeze §11 Research Gate | `DEC092-EPSPE-HIGH-GATE` |
| X10 | **個股買賣語意**（停利停損、目標價、部位大小、三維出場「建議減碼／強烈出場」） | Capability Map T21 critical、HI-3 | `FUI-OLD-UI-ACTION-SEMANTICS` |
| X11 | **市場層「是否需要行動」由 regime 推導** | 推導＝新投資語意（invC N13） | 只讀 System Action State；未就緒 `⬜ 尚未提供` |
| X12 | **在 VM／UI2 內做任何動作聚合**；以及 System Action State **完整版**（Canonical Snapshot、Digest 組裝、新規則） | 聚合屬 L3 deterministic 組裝，**不是** UI2 presentation 工作（invC N7）；最小彙整切片的提前與否＝**G3′**（~~§4.5~~ §4.6；Q2 核准契約、implementation Gate 後才有），完整版屬 Stage F | `FUI-SYSTEM-ACTION-LAYER`；`NUI2-G3-SYSTEM-ACTION-SUMMARY`；UI2 只消費 |

⚠️ 承重提醒：P4／P5／P7 的**判定**都在System Action Aggregator（~~系統動作彙整層~~），這是「呈現既有規則」與「新規則」的分界最細處；彙整層實作批須由 Opus 5.5＋High 撰寫＋獨立 QA，並以 Freeze §0.1.4／§0.1.5 表格驅動測試（§9 G6／G7）。

### §4.5 System Action Aggregator（~~系統動作彙整層~~）~~（**G3′ 提案，PENDING**；＝Freeze §6 第 6 點／Stage F System Action 彙整的最小切片提前做）~~ 裁示前提案（歷史；**正式契約見 §4.6**）

> 📌 **本節為裁示前提案文字，原文保留；客戶 Q2 裁示後以 §4.6 為準**（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）。客戶修正一點分類：**它仍屬「新的 runtime component」**——本節末「總管讀法為『不算新增 runtime』」**被客戶推翻**；本 Gate 只凍結 interface／ownership／input-output contract／tests／migration plan，**本批不得實作 production runtime**。本節的暫定模組名 `system_action_state.py` 由 §4.6 的名稱取代。

- **是什麼**：單一 **headless L3 純函式模組**（AI 總管暫定名 `src/services/system_action_state.py`＋L0 型別 `shared/system_action_state.py`；同 `decision_digest_builder` 先例：不 import streamlit、不讀 session，輸入由 feed 把既有服務結果以參數傳入；任何頁面都不必 render 就能跑）。**不屬於** `src/ui2/`——UI2、日後 LINE、日後 Decision Digest **共用同一份**，避免三處各自聚合。
- **只彙整既有正式輸出**：(1) 合併 ETF `action_branch` 七分支與個股 `swap_level` 四級（原名照用）；(2) 加／留／換／減分組計數（分組依 W-5 客戶核准結果）；(3)「沒事 vs 判不出」gate（沿用 `cruise_or_gap`＋`holdings_data_short` 既有規則）；(4) 加碼列的 Risk Cap 狀態標註（Q1=A：數值未啟用前恆「Risk Cap 無法判定」）；(5) 跨頁 ⚡ N（市場頁「是否需要行動」、持股頁「今日需處理」同源，計入範圍依 W-5／W-10）。
- **⛔**：新門檻、新分支、新比例（含「減碼 1/2」「全出」）、改既有分支觸發條件或優先序、由市場位階推導動作、Risk Cap 數值判定（`FUI-RC-NUMERIC-GATE`）、新增任何寫入（只觸發既有服務的既有副作用）。
- **與 Stage F 的關係**：Stage F 的完整版（Canonical Snapshot、Digest 組裝、`allocation_service` session-free 化）**不在**本切片；本切片的輸出型別日後直接成為 Digest 的 System Action 段來源（INFERENCE）。
- ~~**為什麼要客戶確認**：客戶 (5)-1 禁止「新增 Risk Cap runtime／OneBrain runtime」，未明列 System Action；本層**不新增任何規則、不新增任何寫入**，總管讀法為「不算新增 runtime」（**客戶 Q2 裁示：屬新的 runtime component**；（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）），但這是新模組，**請客戶確認**（G3′）。若客戶選 B（等 Stage F 完整 Headless Digest），UI2 的動作相關欄位在那之前一律 `⬜ 尚未提供`，VM ⛔ 自行聚合補位。~~ 📌 **已被客戶 Q2 推翻：屬新的 runtime component**（見 §4.6）（2026-11-02 #997 獨立稽核 PASS with fixes 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔稽核修正〕；原文刪除線保留）

---

### §4.6 System Action Aggregator 正式契約（**客戶核准 Q2=A〔修正分類〕，2026-11-02**；**只凍結 contract，⛔ 實作**）

> 出處：客戶 2026-11-02 裁示 Q2（逐字見 DEC-123「客戶裁示 Q1～Q4」）。〔客戶 Q2〕＝客戶原文；其餘欄位名、模組名、測試編號＝AI 總管暫定（客戶可推翻）。

**§4.6.1 正式名稱**：**System Action Aggregator**（客戶核准用語：「共用 System Action Aggregation Layer」）。舊稱「~~系統動作彙整層~~」停用。

**§4.6.2 定位（客戶原文，逐字）**：

```
Existing Formal Rules + Risk Cap
→ System Action Aggregator
→ System Action State / action-facing canonical contract
→ Decision Digest / New UI2 / LINE
```

「**不是第二套規則引擎。**」〔客戶 Q2〕

**§4.6.3 允許責任（客戶原文，逐字；只允許這 7 項）**：
1. 收集既有 deterministic rules 的正式結果
2. 收集既有 Risk Cap state
3. 區分 actionable / non-actionable / unavailable / not evaluated
4. 加／留／換／減 presentation grouping
5. 統一計數
6. 區分「今日無需調整」與「無法判定」
7. 提供 New UI2 / 未來 LINE / Decision Digest 共用的 canonical action-facing view

**§4.6.4 禁止（客戶原文，逐字；9 項）**：
1. 新增投資規則
2. 新門檻
3. 新比例
4. AI action
5. 改寫既有 deterministic result
6. 覆寫 Risk Cap
7. 自行決定減碼 1/2／全出
8. portfolio write
9. Sheet write

**§4.6.5 分類與施工限制（客戶原文要點）**：「它仍屬『新的 runtime component』。」本 Architecture Gate「只允許凍結 interface / ownership / input-output contract / tests / migration plan」；「**本批不得實作 production runtime**」；「請把它正式登錄為 New UI2 後續 prerequisite backlog，再經 implementation Gate 才施工」（BACKLOG `NUI2-AGGREGATOR-IMPL`）。
- **Aggregator 實作前的 UI2 讀法（AI 總管暫定，依客戶 Q2／W-10）**：UI2 動作相關欄位（💼 今日需處理、計數、「今日無需調整 vs 無法判定」）一律 `⬜ 尚未提供（待 System Action Aggregator）`；VM ⛔ 自行聚合補位（§4.2 第 4 點）；📊 市場頁「是否需要行動」依 **W-10 transitional contract** 沿用舊警示並標 source／scope（線框 §9）。
- 📌 **`⬜ 尚未提供` 的語意（DEC-124）**：Capability／Implementation Availability State（Preview-only），與資料語意正交；⛔ 稱第 6 個資料語意態；⛔ 讀成「今日無需調整」或「無法判定」。New UI2 契約以 `CapabilityState.NOT_PROVIDED` 建模（2026-11-02 Semantic Correction Gate 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-124）＋AI 總管〔語意修正〕；原文刪除線保留）。
- **`⬜ 尚未提供` 只允許在 Preview 期**（#997 獨立稽核 M2；AI 總管）：動作欄的 `⬜ 尚未提供（待 System Action Aggregator）` **只允許出現在 Preview 期**；**cutover 前必須完成 `NUI2-AGGREGATOR-IMPL` 與 M-A3（UI2 VM 改讀 Aggregator）、M-A4（📊 市場 ⚡ 切到 Aggregator）**——否則正式版 💼 持股頁的「今日需處理」動作能力消失（違客戶 §42「新 UI 看起來簡潔，不代表功能消失」與 Capability Map 能力守恆）。Migration／Cutover Contract C2、C6、C7 同步（2026-11-02 #997 獨立稽核 PASS with fixes 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔稽核修正〕；原文刪除線保留）。

**§4.6.6 Interface／Input-Output contract（AI 總管暫定欄位名）**

- **形態**：L3 純函式（暫定 `src/services/system_action_aggregator.py::aggregate_system_actions(...)`）＋L0 型別（暫定 `shared/system_action_contract.py`）；**不 import streamlit、不讀 session、不做 I/O、不寫任何東西**；輸入一律以參數傳入（由 caller／feed 取既有服務結果），任何頁面都不必 render 就能跑（headless）。同一輸入 → 同一輸出（deterministic）。
- **輸入（只收既有正式規則輸出＋Risk Cap state）**：

| # | 輸入 | 既有來源（FACT，讀碼） | 備註 |
|---|---|---|---|
| I1 | ETF 持股的正式分支 | `dividend_station_service.get_station_rows` → `dividend_station.action_branch` 七分支（`cut`／`take_profit_force`／`take_profit_partial`／`pause_add`／`add`／`premium`／`cruise`）＋原名字樣 | 原名照帶，⛔ 改寫 |
| I2 | 個股的正式換股等級 | `StockAssessment.swap_level`（🔴 換出／🟡 留意／🟢 續抱／⚪ 資料不足） | 同上 |
| I3 | 資料不足判定 | L0 `shared/holdings_data_short` | 與 LINE 共用的既有判定 |
| I4 | Risk Cap state | `allocation_service.get_allocation(require_valid_risk_cap=True)` 結果＋（PORT 至 L0 後的）`risk_cap_gate.has_system_risk_cap` | Q1=A：曝險分母不存在 → 閘門恆「無法判定」；⛔ 自行計算曝險 |
| I5 | 每項輸入的 as_of／source | 各 service 回傳的 provenance | 缺 → 照實標缺 |
| I6 | 逐燈判定格（每列每盞燈的 state＋level） | 既有 `station_cards` 燈格 → `judged_count`（分子＝分母內 state ∈ {live, degraded} 且 level 非空；分母依 `_in_judged_denominator`）／`is_fully_judged`／`aggregate_judged`／`tally_states`（`src/ui/render/station_cards.py`，Old UI；PORT 為新建＋parity） | 「沒事 vs 判不出」gate 的原料；⛔ 重訂分母或分子（#997 稽核 M3 補） |
| I7 | 資料不足原因與整批失敗 | `shared/holdings_data_short`：`row_short_kind`（`unjudged`／`price_missing`／`fx_unconfirmed`）、`row_data_short`、`total_judged(total)`、`digest_data_short(digest)`；station digest 的 `errors`、`total`、`data_short` | 判不出的原因來源（#997 稽核 M3 補） |

- **`holdings_data_short` 原因 → `action_class` 對映（#997 稽核 M3 補；FACT＝讀碼 `shared/holdings_data_short.py`；對映＝AI 總管暫定，客戶可推翻）**：

| 原因（`row_short_kind`／組合層） | 既有條件（FACT） | `action_class` | `counts_toward_today` | 對 `day_status` 的影響 |
|---|---|---|---|---|
| `unjudged` | `KEY_INSUFFICIENT`（建議動作已換成「⬜ 資料不足／無法判定」）／`KEY_INVALID_INPUTS`／`KEY_INVALID_LIGHTS`／個股汰換燈 ⚪ 且契約漂移；持有列與觀察清單列皆算 | ~~`not_evaluated`~~ **`undeterminable`**（DEC-124：已進入判定、必要輸入不足／無效＝Unable to Determine，⛔ 併入 Not Evaluated）（2026-11-02 Semantic Correction Gate 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-124）＋AI 總管〔語意修正〕；原文刪除線保留） | False | ⛔ `no_adjustment_today` |
| `price_missing` | 持有列缺現價、但結論可證明（`KEY_PRICE_MISSING_KEPT`；結論保留、停利等判不了） | **原分支的 class 照帶**（結論保留），另帶 `data_short_kind=price_missing` | 依原分支 | ⛔ `no_adjustment_today`（組合層資料不足） |
| `fx_unconfirmed` | 持有列外幣／幣別未確認（`KEY_FX_UNCONFIRMED`；不進總額、損益% 判不了） | 同上（原分支 class 照帶）＋`data_short_kind=fx_unconfirmed` | 依原分支 | ⛔ `no_adjustment_today` |
| 整批抓取失敗列（`_detail.error`；`row_short_kind` 回 None、由 `errors` 管） | digest `errors` 非空 | `unavailable` | False | ⛔ `no_adjustment_today` |
| 組合層：`total_judged(total)` 為 False（沒有任何一檔完成評估） | `digest_data_short` 為 True | — | — | ⛔ `no_adjustment_today` |


- **輸出（System Action State／action-facing canonical contract）**：

| # | 欄位 | 內容 | 對應允許責任 |
|---|---|---|---|
| O1 | `items[]` | 每檔：`ticker`、`name`、`source_rule`（`action_branch.v1` 碼或 `swap_level`）、`formal_label`（原名，逐字）、`action_class` ∈ {actionable, non_actionable, unavailable, not_evaluated}（📌 DEC-124 增 **`undeterminable`**：`not_evaluated`＝規則／計算尚未執行或不在本次評估範圍；`undeterminable`＝已進入判定但必要輸入 Missing／Unavailable／Invalid／insufficient；兩者禁止合併；客戶 Q2 原文四類一字未改，第五類為 AI 總管暫定、客戶可推翻）（2026-11-02 Semantic Correction Gate 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-124）＋AI 總管〔語意修正〕；原文刪除線保留）、`group` ∈ {加, 留, 換, 減}、`counts_toward_today`（bool）、`risk_cap_tag`、`rule_id`（只限 `RULE_ID_ALLOWLIST`；無則空）、`as_of`、`source`；（#997 稽核 M3 補）`data_short_kind`（`row_short_kind` 原樣：`unjudged`／`price_missing`／`fx_unconfirmed`／空） | 1～4 |
| O2 | `counts` | `today_n`（計入「今日需處理」檔數）、`by_group`（加／留／換／減）、`not_evaluated_n`、`unavailable_n`、📌 `undeterminable_n`（DEC-124）（2026-11-02 Semantic Correction Gate 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-124）＋AI 總管〔語意修正〕；原文刪除線保留）；（#997 複驗 N1 補）`incomplete_rows_n`＝現行 `page_hold` 的 `_unjudged` 口徑：`row_data_short(row)` 為真**或**該列燈未全判出（`not is_fully_judged(cells)`）的列數（與既有 `unjudged_rows` 同口徑；⛔ 另訂） | 5 |
| O3 | `day_status` | ~~`needs_action`（`today_n`>0）／`no_adjustment_today`（`today_n`=0 且 `not_evaluated_n`=0 且 `unavailable_n`=0）／`undeterminable`（`today_n`=0 且有任一未評估或不可得 →「無法判定」）~~ **既有 gate 的組合結果，⛔ 自行重新判定**（#997 稽核 M3）：`needs_action`＝`today_n`>0（同時揭露判不出檔數）；`no_adjustment_today`＝`today_n`=0 **且** `cruise_or_gap(judged, total, all_rows_judged=…)` 回巡航（`is_fully_judged` 全列成立、`judged==total>0`）**且** `digest_data_short(digest)` 為 False；其餘 `today_n`=0 的情形＝`undeterminable`（「無法判定」）。分子分母與資料不足判定**只沿用 I6／I7 既有函式**，⛔ 另訂門檻、分母或例外 | 6（Freeze §0.1.5 第 3、4 點） |
| ~~O4~~ | ~~`risk_cap`~~ | ~~原樣帶出 Risk Cap state；Q1 數值 Gate 前恆 `undeterminable`；加碼類 item 的 `risk_cap_tag`＝「Risk Cap 無法判定」；`🔴 Risk Cap 超限 · 禁止新增曝險` 只在 `FUI-RC-NUMERIC-GATE` 啟用後才可能出現~~ | ~~2（禁止 6）~~（#997 稽核 m6 拆欄（2026-11-02 #997 獨立稽核 PASS with fixes 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔稽核修正〕；原文刪除線保留）） |
| O4a | `risk_cap_state` | Risk Cap state **原樣傳遞**（＝輸入 I4，⛔ 改寫、⛔ 補值） | 2（禁止 6） |
| O4b | `exposure_gate` | **超限判定：數值未啟用，恆 `undeterminable`**；加碼類 item 的 `risk_cap_tag`＝「Risk Cap 無法判定」；`🔴 Risk Cap 超限 · 禁止新增曝險` 只在 `FUI-RC-NUMERIC-GATE` 啟用後才可能出現；⛔ 自行計算曝險、分母、現金、總資產 | Q1=A；禁止 6 |
| O5 | `provenance` | 輸入 as_of／source 彙總、`contract_version` | 7（Freeze §9） |

- **計入規則（客戶 W-5=A）**：「今日需處理」包含**加、換、減、暫停加碼**（暫停加碼是正式 action code `pause_add`，⛔ 顯示成「今日無需調整」）；巡航／🟢 續抱／高溢價只做分布；**🟡 留意若只是資訊狀態、沒有正式 action code，⛔ 自行升格成 portfolio action**（`counts_toward_today`=False）。
- **分組（W-5 客戶核准）**：加＝加碼；留＝巡航、🟢 續抱、暫停加碼、高溢價、🟡 留意；換＝🔴 換出；減＝強制停利（>+3σ）、分批停利（>+2σ）、汰弱；⚪ 資料不足＝`not_evaluated`。分組只是排版（Freeze §0.1.5-2），⛔ 改任何分支觸發條件、優先序或比例。

**§4.6.7 Ownership**
- **Owner**：System Action contract（L0 型別＋L3 Aggregator），**不屬** `src/ui2/`、不屬任何 consumer。修改契約欄位＝契約變更（PR 必附 What changed／NOT changed／contract／tests／semantic change 驗收，且經獨立 QA）；**新增任何規則＝禁止**（§4.6.4），只能走既有規則本身的 Decision Gate。
- **Consumers**：New UI2 VM（只讀，⛔ 再聚合）；Decision Digest builder（Stage F，取 System Action 段）；LINE formatter（**未來另批、另 Gate**；本批 ⛔ 改 LINE production）。三者 ⛔ 各自重算分組／計數。

**§4.6.8 測試清單（實作批必備；皆附 mutation：拔掉守衛邏輯必轉紅）**
- A-T1 純度 AST：⛔ import `streamlit`／`src.ui*`／`src.data*`／`requests`；⛔ `session_state`；⛔ 呼叫任何寫入（Sheet 寫入、檔案寫入、`*_apply`）。
- A-T2 表格驅動：七分支 × 四級 × Risk Cap state {valid, invalid, missing} → `action_class`／`group`／`risk_cap_tag` 全組合。
- A-T3 W-5 計入：暫停加碼計入；🟡 留意（無正式 action code）不計入；巡航／續抱／高溢價不計入。
- A-T4 `day_status`：「今日無需調整」只在 `today_n`=0 且 0 未評估、0 不可得；任一判不出 → `undeterminable`。（📌 DEC-124：「判不出」含 `not_evaluated` 與 `undeterminable` 兩類，計數分列、⛔ 合併；A-T2 表格驅動同樣分列）（2026-11-02 Semantic Correction Gate 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-124）＋AI 總管〔語意修正〕；原文刪除線保留）
- A-T5 禁用字樣：輸出 ⛔ 含「減碼 1/2」「全出」或任何比例字樣；⛔ 新 action code。
- A-T6 `rule_id` ⊆ `RULE_ID_ALLOWLIST`。
- A-T7 原名逐字：`formal_label` 與來源字樣 byte-identical。
- A-T8 parity：與既有 `cruise_or_gap`／`aggregate_judged`／`tally_states`／`holdings_data_short` 在 golden 夾具上一致（不一致須說明並送 Gate，⛔ 擅自改哪一邊）。（#997 稽核 M3：parity 範圍明列 I6／I7 的 `judged_count`／`is_fully_judged`／`aggregate_judged`／`tally_states`／`cruise_or_gap`／`row_short_kind`／`total_judged`／`digest_data_short`；保留）（#997 複驗 N1：parity 另含 `incomplete_rows_n` 對 `page_hold` 的 `_unjudged`／`unjudged_rows`）
- A-T9 Presentation Slice independence：輸出不受 consumer 的 top_n／收合影響。
- ~~A-T10 Risk Cap 不覆寫：輸入 Risk Cap state 與輸出 `risk_cap` 相等；⛔ 自行產生數值或分母。~~
- A-T10（#997 稽核 m6 改寫，與 O4a／O4b 一致）Risk Cap：O4a `risk_cap_state` 與輸入 I4 逐欄相等（原樣傳遞）；O4b `exposure_gate` 在數值 Gate 前恆 `undeterminable`；⛔ 自行產生數值、分母、現金或總資產
- A-T11（Stage H）跨 consumer 一致：UI2 與 LINE 讀同一份輸出時計數相同。

**§4.6.9 Migration plan**

| 步 | 內容 | Gate |
|---|---|---|
| M-A0 | 本 Gate 凍結契約（§4.6） | #997 獨立稽核＋合併 |
| M-A1 | **Implementation Gate**（客戶）：核准實作 Aggregator runtime | 客戶（`NUI2-AGGREGATOR-IMPL`） |
| M-A2 | 實作 L0 契約＋L3 Aggregator＋A-T1～A-T10；**不接任何 consumer** | Opus 5.5＋High；獨立 QA |
| M-A3 | UI2 VM 改讀 Aggregator（取代 `⬜ 尚未提供`） | 各頁 UI2 批 |
| M-A4 | 📊 市場頁 ⚡ 由 W-10 transitional 切到 Aggregator（與 💼 同一 canonical action source） | 市場頁 UI2 批 |
| M-A5 | Decision Digest（Stage F）以 Aggregator 輸出作 System Action 段 | Stage F |
| M-A6 | LINE 改讀同一 canonical action source（收斂第二套權威） | **另批、另客戶 Gate**（改 LINE production；`NUI2-LINE-UI-ACTION-CONVERGENCE`） |

- Legacy New UI／Old UI 的既有判定（`cruise_or_gap` 等）**不改**，只以 A-T8 parity 對照，退場隨 Removal Gate。

## §5 Migration boundary（承重；待第二組驗）

### §5.1 原則

> 📌 客戶 Q4=A 後，Migration／Cutover 規則正式條文另見 `docs/vnext/NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md`（本節原文保留）（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）。

1. **PORT 的定義**（invC §0）：邏輯須**搬家或解耦**才能給 UI2 用（UI 層 → L0／L3／presentation contract；或 session 隱性輸入 → 顯式參數）。屬 UI2 頁面施工的**前置**。
2. **Old UI 一字不改**〔客戶 (5)-4「禁止修改」〕：PORT 自 Old UI 的純函式＝**新位置另建**（UI2 的 SSOT），Old UI 原檔保留至 Removal Gate；兩處以 **parity／golden 測試**釘同輸出（AI 總管暫定；理由：去重須改 Old UI import，客戶已禁止；暫時雙份是較小的惡，且有機械守衛）。
3. **Legacy New UI（預設＝新建＋parity，原處不改）**：PORT 自 `src/ui/views/**`、`src/ui_v2/**` 的純函式＝在新位置另建（UI2 的 SSOT），以 parity／golden 測試釘住與原處同輸出；**Legacy New UI 原檔不改**（它目前是 production 預設四頁）。**備選（未採用）**：把 legacy 原處改為 re-export 薄別名以免雙份——**會動 production UI 檔**，須客戶同意＋byte-identical 守衛，才可改用（AI 總管暫定，客戶可推翻）。
4. **規則／公式類 change-frozen**：PORT 只搬「呈現既有規則所需的純函式」；⛔ 改既有 L2 規則（`dividend_station.action_branch`／`suggest_action`、`scoring/*`、`shared/*_thresholds`、`risk_cap_policy`…）。
5. **字串逐字不改**：客戶核准字樣（例 `risk_cap_gate` 的 PQ-C6-3 字串、DEC-081 Q2-1 今日結論、`⬜ 未評估／資料不足`）PORT 時逐字搬，以字面守衛釘住。

### §5.2 先 PORT（UI2 頁面施工前置；AI 總管暫定順序，開工時以當時 main 重判）

| 批 | 項目 | 來源（FACT，檔＋符號） | 去向（INFERENCE） | Reuse 列 |
|---|---|---|---|---|
| M1 | **Old UI 業務邏輯 11 列前置**（OLD-1～OLD-11 中屬 UI2 需要者）：`tab_today.Card`／`Note`／`MAX_COLS`／`scrub_state_glyphs`／`classify_macro_contract`…；`tab_macro_v2.build_rows`／`bucket_summary`／`summary_coverage`／`overall_verdict`；`station_cards.judged_count`／`is_fully_judged`／`aggregate_judged`／`tally_states`／`cruise_or_gap`；`macro_v2_cards.band_meta`／`threshold_text`；`tab_stock_picker.summarize_factor_hits`；`section_357_valuation` 歷史河流純計算（只搬歷史實際值）；`app.py` 選股網 regime 濾網解析規則 | Old UI（一字不改） | L0 contract（型別、字樣）／L2-L3 純函式（判態、彙整）＋parity 測試 | OLD-1～OLD-6、OLD-8 |
| M1 | **`risk_cap_gate`**（`has_system_risk_cap`、`SYSTEM_RISK_CAP_NAME`、`RISK_CAP_UNAVAILABLE_NOW`…；零 st） | `src/ui/views/risk_cap_gate.py`（L5） | L0 `shared/`（VM 依 R5 ⛔ import L5，故須下沉 L0） | V10 |
| M1 | **`cruise_or_gap`**（「沒事 vs 判不出」gate；docstring 明寫刻意不進 L2 因同時餵 LINE） | `src/ui/render/station_cards.py`（L4，Old UI，原處不改） | System Action Aggregator（~~系統動作彙整層~~）~~（§4.5；G3′=A′ 才建）；G3′=B 則延到 Stage F~~（§4.6；Q2 核准契約、implementation Gate 後才建）（⛔ 改 `suggest_action`） | OLD-3 |
| M2 | **私有符號 public 化**：`data_loader._fm_raw_headers`（V-PICKER-PRIV-1）、`yield_pe_fetcher._twse_official_pbratio`、`src.data.etf._fetch_news_for`／`_fetch_sector_returns`／`_fetch_holdings_yahoo_tw` | L1 private | public L3 介面（thin） | L1-9 |
| M2 | **New UI 可重用純函式**（`page_market`／`_market_blocks`／`_target_blocks`／`page_hold`／`page_me`／`page_today`／`page_find`／`page_inspect`／`page_why` 的 pure builder，逐函式挑選） | Legacy New UI | L0 contract／L3 `*_vm` | V1～V2、V4～V8 |
| M2 | **`src/ui_v2/compact`／`markup` 解耦**（切斷 `compact → markup → blocks → page_*` 對五頁版面契約的傳遞依賴；`unavailable`→`unwired` 改名、新增 Danger／Positive／Neutral tone 只加不改） | Legacy New UI | UI2 components（WRAP `tokens`／`components`） | U1～U3 |
| M3 | **New UI ~130 支測試中的語意守衛先 PORT**（見 §5.4） | `tests/**` | UI2 presentation-contract 測試 | tests §7 |
| 延到 Stage F | `allocation_service` session-free 簽名（S23）、`*_apply` 寫 session 鏈（S17～S21）→ Canonical Snapshot；Old UI `section_mid` render 期 `register_conflict` 揭露文字（OLD-7） | L3／Old UI | Stage F additive adapter。⚠️ **S23 session-free 簽名與 OLD-7「由 L3 吸收使寫入成為 no-op」都會改既有 service（或 Old UI），未經客戶 Gate 不得做** | S17～S23、OLD-7 |

### §5.3 不得碰（UI2 施工期）

- **DO NOT TOUCH**（Reuse Matrix）：Old UI 其餘全部；`shared/app_cache`、`cache_layer`；`src/config/persona`；LINE production 鏈（`src/data/notify/*`、`src/compute/notify/*`、`weekly_review_service`、`scripts/push_*`、`.github/workflows/push_*`）〔客戶 (5)-10「不要修改 LINE production」〕；個股買賣語意 L2（T21）；`risk_radar`（V-RADAR-1）；`ai_qa_service`；`ai_structured_summary`。
- **⛔ 新增 Risk Cap runtime、⛔ 新增 OneBrain runtime、⛔ 重寫既有 data／services／rules**〔客戶 (5)-1〕。
- **⛔ 刪除 Old UI／現有 New UI**〔客戶 (5)-1〕。

### §5.4 不得整包搬 builder（逐函式挑選；FACT＝invC §11 風險 10）

| 不得帶入 UI2 的東西 | 位置（FACT） | 原因 |
|---|---|---|
| `guard_chip` 承載判型／計數／估值口徑（`kind_chip_text`、`HIT_CHIP_FMT`／`MISS_CHIP_FMT`／`PARTIAL_NOT_EVALUATED_FMT`、`PE_BASIS_CHIP`） | `src/ui/views/_target_blocks.py` | 違 Freeze §4.2；UI2 改 Neutral／Info |
| Gemini 直呼（⑦ `load_ai_summary`／`build_ai_summary_card` → `build_ai_summary(digest, gemini_call)`） | `src/ui/views/page_hold.py` | 違 Freeze §15.1／§15.4（`FUI-HOLD-GEMINI-DIRECT`）；UI2 OneBrain 槽 Stage G 前 `🤖 ⬜ 尚未提供` |
| AI QA（`load_qa`／`compose_qa_message` → `ai_qa_service.run_agent`） | `src/ui/views/page_why.py` | 非 Digest 輸入；Stage G 取代 |
| ④ 總經階段卡的 `posture_range`（`build_macro_stage_card`；來源 `dividend_station_service.get_station_macro()` → `compute_position_throttle()`，**未套任何天花板**） | `src/ui/views/page_hold.py` | 與 ⑤ 建議持股區間（已套天花板）同頁口徑不同；⛔ 整包搬，若承接必須同時帶「未套天花板」標示或只呈現 ⑤（`tests/test_p04_hold_allocation_ssot_claim.py` 已登記此自我矛盾） |
| 「訊號可信度」標籤（`build_confidence_card`）、「信心度」標籤 | `page_hold`、`page_market` | 易讀成機率（Freeze §7；`FUI-CONFIDENCE-LABEL-RENAME`）；UI2 直接用改名後字樣（建議「資料齊備度」／「可判定覆蓋度」，客戶可推翻） |
| builder 回傳 Old UI `tab_today.Card` 型別 | `page_hold` 等 | UI2 改用中立 VM 型別（P6） |
| `compact` 對五頁版面契約的傳遞依賴 | `src/ui_v2/compact → markup → blocks → page_*` | 先解耦再用（U1） |

### §5.5 New UI 語意測試：先 PORT 再退場

FACT（invC §7，regex 啟發式量級）：New-UI-bound 測試 ≈130 支，其中大量是**語意 invariant 而非版面**：`test_xv_h1ext_missing_not_hold`、`test_xv_h3_fx_not_summed`、`test_xv_asof`、`test_v2_silent_fail_b*`（13 檔）、`test_sec_*` scrub、`test_dec074_breadth_gate`、`test_nfa_nonfinite_gray`、`ui_v2/test_compact`／`test_markup`／`test_tokens`。
- **規則（AI 總管暫定）**：這些斷言**先改寫成 UI2 presentation-contract 測試並在 UI2 上轉綠**，原測試才可隨 Legacy New UI 進 RETIRE；⛔ 隨版面一起刪。逐檔清單在 M3 批產出（BACKLOG `NUI2-NEWUI-SEMANTIC-TEST-PORT`）。

---

## §6 目錄結構（AI 總管內部自決，客戶可推翻）

### §6.1 推薦：三段式（invD §6 D-A）

> ⛔ SUPERSEDED / HISTORICAL — NOT ACTIVE（DEC-128 S41）：目錄註解中的「expander 層級」元件（L1／L2／L3 摺疊層級規範）不再是 New UI2 元件需求；資料健康度 Level 3 的收合除外。現行見 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`。本節其餘仍有效。


```
shared/ui2_contract/            L0  VM 型別（frozen dataclass）、四態對映、chip tone、L1 字樣常數、術語 SSOT 引用
                                    零 I/O、零 streamlit；⛔ 依賴 L1+（R3）
src/services/ui2/               L3
    <page>_feed.py                  唯一呼叫既有 services 之處；原樣帶出結果（含 provenance／is_stale）
    <page>_vm.py                    純函式 VM builder（輸入＝feed 結果；輸出＝L0 VM 型別）
src/ui2/                        L5  只吃 VM 渲染；⛔ 取數、⛔ 判態、⛔ cache
    shell/                          殼、四頁導覽、`ui2_` session 前綴、`ui2-` CSS 前綴
    components/                     card／chip／metric card／freshness tag／chart container／mobile stack／expander 層級
    views/                          market／target／hold／me 四頁
app_ui2.py                      L6  preview 期獨立入口（repo 根）；cutover 後由 app.py 分派（~~PENDING G1／G2~~ Q1=A／Q4=A 已核准）

（~~G3′=A′ 時另建~~ 客戶 Q2 核准契約、implementation Gate 後才建；不屬 ui2、UI2／LINE／Digest 共用）
~~shared/system_action_state.py   L0  系統動作彙整型別~~
~~src/services/system_action_state.py  L3  系統動作彙整層（純函式、headless；§4.5）~~
shared/system_action_contract.py           L0  System Action Aggregator 契約型別（§4.6；Q2 核准後改名）
src/services/system_action_aggregator.py   L3  System Action Aggregator（純函式、headless；§4.6；⛔ 實作直到 implementation Gate）
```

- **c3 guard 同 PR 登記**（invD §6.2；FACT：`_layer_of_file()` 對未登記前綴回 `None`，五條規則對該檔**靜默失效**；`src/ui_v2/` 2026-09-21 曾發生）：`_PATH_LAYERS` 加 `("src/ui2/", L5)`、`_MODULE_LAYERS` 加 `("src.ui2", L5)`（`"src.ui2"` 與 `"src.ui."` 不相交，必須具名）；`app_ui2.py` 加入 `_SCAN_FILES` 視為 L6；`src/services/ui2/`、`shared/ui2_contract*` 已被既有前綴（L3／L0）涵蓋。**同 PR 新增 meta 測試**：掃到的每個 `.py`（含入口）`_layer_of_file` 皆非 None（§9 G1）。
- **R4 零白名單**：UI2 L5 ⛔ 直呼 L1、⛔ 新增 EX-PASSTHRU-1 條目（FACT：現有 `src/ui/views/**`、`src/ui_v2/**` 已是 0 個 `src.data` import）。
- **⛔ 根目錄 `pages/`**（Streamlit MPA 會自動把其中檔案變側欄頁；invD C-APP-2，INFERENCE）。

### §6.2 `src/ui2` 與 `src/ui_v2` 命名區分

- **FACT**：既有 `src/ui_v2/`＝2026-09 的「戰情室 v2 UI」共用元件層（tokens／components／compact／markup／render＋五頁版面契約），現屬 **Legacy New UI**；客戶的「**New UI2**」是全新 Presentation Layer。兩者一字之差，極易混淆。
- **處置（AI 總管暫定）**：(a) 目錄用 `src/ui2/`（貼合客戶用語）；(b) 套件 docstring 第一行寫明「New UI2（`src/ui2/`）≠ Legacy New UI 的 `src/ui_v2/`」；(c) UI2 對 `src.ui_v2` 的 reuse 只走 G4 明列允許清單（`tokens`／`components` WRAP；`compact`／`markup` 解耦後才可）；(d) 文件一律寫「New UI2（`src/ui2/`）」與「Legacy New UI（`src/ui/views/`＋`src/ui_v2/`）」。替代名 `src/ui_next/`（客戶可推翻）。
- `CLAUDE.md` §8.2 七層表「L5 UI Tabs 代表檔」需補 `src/ui2/`、L6 補 `app_ui2.py`——**於 UI2 首個實作 PR 同步**（本批不動 `CLAUDE.md`；BACKLOG `NUI2-GUARD-REGISTRATION`）。

### §6.3 不推薦（理由）

- **D-B：VM 放 L5（`src/ui2/viewmodels/`）**：可直接 import Legacy views builder（L5→L5 不被 R5 擋）→ 違 G4 獨立性、Legacy 退場時被拖住；VM 與 render 同層難以強制純度。
- **D-C：新頂層 `src/presentation_contract/`**：現行 `_PATH_LAYERS` 接不到，須新增層定義；語意上是 L0／L3 混合，徒增第八層。

---

## §7 Preview strategy（~~**PENDING G1**~~ **客戶核准 Q1=A**）

> 📌 **DEC-128 補註（2026-11-03；補充、非取代）——Preview 控制的位置規則**：本節 Q1=A（Preview 策略）**不變**；新增位置規則：「Preview 控制（資料來源／fake 場景／帳戶）」屬**開發／測試專用控制**，不得畫成四頁產品內容（⚠ PROVISIONAL：僅 `?ui2_dev=1` 之類開發旗標時顯示、明顯標示「非產品內容」、不用 sidebar、不開第五導覽項；預設道 0 個）。FAKE／Real 切換保留供測試，**不屬 production presentation contract**。現行殼（`src/ui2/shell/app.py` 把它畫成頁面 expander）是 implementation deviation，由 `docs/BACKLOG.md` §5.1.26 P1 修正。見 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md` §6。


### §7.1 候選比較（FACT＋INFERENCE，invD §2）

| # | 機制 | production 入口 | 手機真機＋真登入 | 人工操作 | 外部 API 負載 | 可逆性 |
|---|---|---|---|---|---|---|
| **P3→P4（推薦）** | 開發期 repo 根獨立入口 `app_ui2.py`（本機／沙箱 `streamlit run`）；要真機試用時，**另建一個 Streamlit Cloud 預覽 app**（同 repo、同 main、Main file＝`app_ui2.py`） | **`app.py` 0 diff** | ✅（預覽 app 有自己的固定 `redirect_uri`，登入回到 UI2） | **需客戶**：建 Cloud app、複製 secrets、GCP OAuth client 加第二個 redirect URI、設定 viewer 權限 | **約加倍**（獨立 process＝cache 不共用；FinMind quota、NAS proxy 負載） | 高（刪 Cloud app／刪檔） |
| P1 `?ui=2` | 現行 `app.py` 於 `set_page_config` 前解析旗標、UI2 分支 `st.stop()` | **改 production 入口**（82 個測試檔以 `read_text` 讀 `app.py` 原始碼，爆炸半徑大） | ⚠️ 登入／靜默恢復後旗標遺失（Google 轉跳＝新 session；invD C-OAUTH-1，未實機驗）→ 💼／👤 預覽體驗破 | 無 | 共用 cache | 高 |
| P3 only | 只本機／沙箱 Playwright 390×844 模擬 | 0 diff | ❌ 不給真機 | 無 | 不影響正式 | 極高 |
| P2 secrets 旗標 | 全部使用者一起切 | 改 production | — | 改 Cloud secrets | — | 只適合 cutover，**不適合 preview** |
| P5 `st.navigation` | 入口改 navigation 模型 | 大改 `app.py` | 未驗 | — | — | 低～中 |
| P6 長命 branch＋獨立 app | 0 diff | ✅ | 同 P4 | 同 P4 | 中；違「每批 PR→main」慣例、`data_cache/` 落後 |

### §7.2 推薦與理由（INFERENCE）

**推薦 P3→P4（＝G1 選項 A）**：唯一同時滿足「production 入口 0 diff」＋「手機真機＋真登入＋真資料預覽」。P3 是 P4 的前置（同一入口檔），開發期即可用，P4 只是把 P3 部署出去 → 平滑遞進。代價：**Manual Action**（客戶在 Streamlit Cloud／GCP 操作）、外部 API 呼叫約加倍、預覽 app 與正式 app 登入狀態不共用。
- 既有先例（FACT）：`src/ui_v2/app_today.py` 已是「`streamlit run` 的零邏輯入口」——但檔頭自陳不在任何測試射程內；UI2 入口必須納入 c3 guard、boot smoke、floor 守衛（§9 G1／G10）。
- 入口放 repo 根（不放 `src/<pkg>/`）以避開 `sys.path` 未驗問題（invD §2 INFERENCE）。
- 預覽 app secrets 只寫變數名進文件（`FINMIND_TOKEN`、`PROXY_URL`、`GEMINI_API_KEY`〔選填，UI2 Stage G 前不使用〕、`[google_oauth]` 的 `client_id`／`client_secret`／`redirect_uri`）；⛔ 寫實值。

---

### §7.3 客戶裁示 Q1=A（2026-11-02；逐字見 DEC-123）

- **採獨立 Streamlit Cloud New UI2 Preview；正式網站維持不動。**〔客戶 Q1〕
- **Preview-first 成本控制（客戶原文四點，逐字）**：
  1. 架構／UI 驗收優先使用 fake / snapshot / view-model scenario。
  2. 真實外部資料只在 real-data acceptance 階段或必要人工驗收時使用。
  3. 不得為了 Preview 建第二套 data/service/source pipeline。
  4. Preview 與 production 最終必須讀相同 canonical services / contracts。
- **Manual Action**：「需要我人工建立 Preview App、複製 Secrets、Google OAuth 新增網址時，再以 🟡 Manual Action Gate 通知我；不要提前要求。」〔客戶 Q1〕→ BACKLOG `NUI2-PREVIEW-APP-MANUAL` 維持 blocked，**直到 `app_ui2.py` 實際可部署**才發 🟡 Manual Action Gate。
- **落實（AI 總管暫定）**：§7.1 表「外部 API 約加倍」由成本控制第 1、2 點壓低——Preview 日常以夾具／snapshot／VM 情境跑；真資料只在 Stage I（real-data acceptance）或客戶指定的人工驗收時開；Preview 與正式同一套 `src/services`／L0 contract（第 3、4 點），⛔ 為 Preview 新增 fetcher、cache 或資料分支。

---

## §8 Cutover strategy（~~**PENDING G2**~~ **客戶核准 Q4=A**）

### §8.1 候選比較（invD §3）

| # | 方式 | 優點 | 風險 |
|---|---|---|---|
| **C3／C1（推薦）** | 四頁**逐頁在 preview 驗收**，**全數通過後一次**把 `app.py` 預設切到 UI2；現行 New UI 改隱藏 `?ui=1`、Old UI 維持 `?legacy=1`；不刪程式 | production 只動一次；跨頁一致性（Stage H）可一次驗；回滾一行 | 單次變更面大 → fallback 必須立即可用（G11 毒化測試） |
| C2 | 逐頁切換 production（UI2 shell 未完成頁委派 Legacy renderer） | 早交付 | 兩套視覺／CSS／session 前綴同屏；UI2 shell 須 import Legacy views（破 G4）；production 變更 4 次 |
| C4 | Cloud secrets 旗標切 | 回滾不需 deploy | 人工操作；仍需 P1 分支邏輯 |

### §8.2 推薦細節（INFERENCE，AI 總管暫定）

- **Fallback**：Old UI 維持 `?legacy=1`（DEC-097：入口不得出現在一般導覽；DEC-019／020 凍結）；Legacy New UI 以 `?ui=1` 保留，同樣不放可見連結（若客戶要可見連結需裁示）。UI2 分支比照 `_nav4_resolve_legacy`「零新模組依賴」。
- **回滾**：預設值一行切回；因 UI2 不寫投資狀態（§4.2 第 3 點），回滾不留資料殘留。UI2 session key 一律 `ui2_` 前綴，避免與 `_nav4_page` 等互相污染。
- **OAuth**：cutover 後 UI2 為預設 → 登入回呼落地即 UI2；`?ui=1`／`?legacy=1` 在登入後會掉回 UI2，屬可接受降級，須在交付揭露（invD C-OAUTH-1，未實機驗）。
- **Cutover ≠ Removal**：Stage J 對象擴為兩個——Old UI、Legacy New UI，各自走 Removal Gate（Freeze §19 六條件∪DEC-083 第 11 點 E 段七步）；⛔ 本批與 cutover 批刪任何舊碼〔客戶 (5)-1〕。

---

### §8.3 客戶裁示 Q4=A（2026-11-02；逐字見 DEC-123）

- **Cutover 鏈（客戶原文，逐字）**：

```
New UI2
→ 獨立 Preview
→ 四頁逐頁驗收
→ mobile / desktop
→ missing / stale / source failure
→ real-data acceptance
→ cross-page consistency
→ 全部通過
→ 一次切成正式 default
```

- 「現有 New UI 與 Old UI 在 Cutover 後先保留 rollback path。」「不得先刪程式。」「正式切換後，再另進 Removal Gate。」〔客戶 Q4〕
- 正式條文、rollback 路徑與 migration 規則：`docs/vnext/NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md`；逐批驗收清單：`docs/vnext/NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md`。

---

## §9 Testing strategy

### §9.1 既有（KEEP）

- **Domain tests ≈298 KEEP AS-IS**（只 import shared／services／compute／data／config）＝UI2 的回歸底座（FACT，invC §7 量級）。
- CI（FACT，invD §4.1）：Fast lane blocking（Py 3.11，`pytest -v`）；Slow lane（`-m slow`，AppTest e2e）`continue-on-error: true` informational（DEC-078）。量測日 2026-11-02 collect 36,177、fast 35,992（invD 實跑，會漂移）。

### §9.2 UI2 新增守衛 G1～G12（invD §4.2；皆附 mutation：拔掉守衛邏輯必轉紅）

> ⛔ SUPERSEDED / HISTORICAL — NOT ACTIVE（DEC-128 S38）：「VM `context`（將來＝Digest）」的讀法已更正：`PageVM.context` 是 **Human UI 全量**（presentation 前的完整 VM），**不是** Decision Context／Digest；Digest 由 canonical services headless 組裝，不由 UI2 VM 衍生（Freeze §14；Active Contract §8）。四情境等價測試（G3）的判準本身（輸出不受 top_n／收合影響）維持。現行見 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`。本節其餘仍有效。


> 守衛編號 G1～G12 是**測試守衛**，與 §11 送客戶的 Decision Gate（G1、G2、G3′）**無關**，只是沿用 invD 編號。

| # | 守衛 | 判準 | 首次落地批 |
|---|---|---|---|
| G1 | **層登記** | c3 `_PATH_LAYERS`／`_MODULE_LAYERS` 登記 `src/ui2/`；`_SCAN_FILES` 納入 `app_ui2.py`（L6）；**meta 測試：每個掃到的檔 `_layer_of_file` 非 None** | UI2 首個實作 PR |
| G2 | **VM 純度** | `src/services/ui2/*_vm.py` AST：⛔ import `streamlit`／`src.ui*`／`src.data*`／`requests`；⛔ `session_state`；⛔ `top_n`／`expanded`／`tab` 類參數影響 `context` | 首個 VM PR |
| G3 | **Presentation Slice independence** | 同一份 canonical 輸入 → VM `context`（將來＝Digest）在 Top5／Top10／collapsed／never-rendered 四情境**逐欄相等**（Freeze §13-2 判準）；mutation：讓 VM 讀 UI top_n → 紅 | 首個 VM PR |
| G4 | **UI2 獨立性** | `src/ui2`／`src/services/ui2`／`shared/ui2_contract` ⛔ import `src.ui.views`／`src.ui.tabs`／`src.ui.etf`／`src.ui.pages`／`src.ui.render`／`app`；`src.ui_v2` 只走明列允許清單 | UI2 首個實作 PR |
| G5 | **四態** | 每個 VM 欄位狀態 ∈ {ok, missing, stale, unavailable, not_evaluated}（📌 DEC-124：此為**資料語意**軸，恰五個；另有**判定結果** `undeterminable`（⛔ 併入 not_evaluated）與**capability** `not_provided`（Preview-only、與資料語意正交、⛔ 算第 6 資料態），三軸型別互斥）（2026-11-02 Semantic Correction Gate 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-124）＋AI 總管〔語意修正〕；原文刪除線保留）；四態 ⛔ 映射 0／中性／續抱／safe；L1 字樣取 Freeze §5.1 常數；property-based：任一輸入缺 → 該欄非 ok | 首個 VM PR |
| G6 | **Risk Cap 不得 unrestricted add** | 表格驅動：cap ∈ {valid, invalid, missing, exceeded} × action ∈ 七分支＋四級：`⬜ 無法判定`／`🔴 超限` 時 ⛔ 任何「加碼」可執行 CTA 或無標註文字；加碼列必帶「Risk Cap 無法判定」；⛔ 出現曝險分母／現金／總資產替代值 | System Action Aggregator（~~系統動作彙整層~~） PR（~~G3′=A′~~ Q2 核准、implementation Gate 後）＋💼 持股 VM PR（Opus 5.5＋High） |
| G7 | **Single Action Authority** | VM 動作字串集合 ⊆ deterministic 原名；⛔「減碼 1/2」「全出」；「今日無需調整」只在「W-5 計入組 0 個正式動作且 0 個未評估」；計入範圍以 W-5 核准結果為準；VM ⛔ 自行聚合（AST：VM ⛔ import `src.compute.etf.dividend_station` 規則函式） | System Action Aggregator（~~系統動作彙整層~~） PR＋💼 持股 VM PR |
| G8 | **手機第一屏量測** | UI2 harness＋measure：390×844 第一屏內可見各頁「不用滑」項目（線框檔 §1）；市場頁「今日主要風險」緊接第一屏後；DOM 順序 AppTest 粗守衛進 CI，Playwright 量測進 VF Gate 附件 | 各頁 PR |
| G9 | **Producer 禁令** | UI2 AST：⛔ 呼叫 `*_apply`、`refresh_macro_now`（主 Update CTA 例外：只經登記的單一 L3 入口）、`gemini_call`、`post_gemini`、`build_ai_summary`、`run_agent`；⛔ 寫非 `ui2_` 前綴 session key | UI2 首個實作 PR |
| G10 | **入口 boot smoke＋floor** | `app_ui2.py` 納入 `tests/test_boot_import_smoke.py` 與 `tests/test_macro_v2_tab.py::TestStreamlitFloorCompatibility` 掃描目標（FACT：floor 守衛現只掃 `src/**`＋`app.py`） | UI2 首個實作 PR |
| G11 | **路由毒化** | 毒化 UI2 套件 → `?legacy=1` 與 `?ui=1` 仍完整載入（比照 `tests/test_nav1_app_routing.py`） | cutover 批 |
| G12 | **術語** | VM 顯示字樣取 Freeze §21 SSOT 常數；⛔ 偏多／中性／偏空映射 | 各頁 PR；Stage H 驗收 |

### §9.3 視覺與手機

- **Visual Fidelity**：保留既有 A1～A11、V1～V11＋Freeze §18-3 新增 Decision Density／Text Reduction；**UI2 需自己的 harness**（FACT：`tools/visual_fidelity/harness_app.py` 以 `runpy.run_path(app.py)` 跑真 `app.py`、只支援 `?p=market|target|hold`，**不支援 👤 我的**）→ 新 harness 支援 UI2 **四頁（含我的）**、`cold`／`partial`／`stale`／`failed` 夾具；1440×900 與 390×844 第一屏＋tall 截圖＋JSON 量測（BACKLOG `NUI2-VF-HARNESS`；吸收 `FUI-ME-HARNESS`）。
- **手機第一屏量測**：每頁依線框檔 §1 的「不用滑」清單逐項量 y 座標；放不下 → Freeze §16.5（縮字句→合併成一行→仍不行停在 Decision Gate，⛔ 自行移出必要項）。
- **截圖 ⛔ 含真實持股、Sheet ID、金鑰**（VF Gate §3）。

### §9.4 Presentation Slice 四情境

> ⛔ SUPERSEDED / HISTORICAL — NOT ACTIVE（DEC-128 S38）：「VM `context`（將來＝Digest）」的讀法已更正：`PageVM.context` 是 **Human UI 全量**（presentation 前的完整 VM），**不是** Decision Context／Digest；Digest 由 canonical services headless 組裝，不由 UI2 VM 衍生（Freeze §14；Active Contract §8）。四情境等價測試（G3）的判準本身（輸出不受 top_n／收合影響）維持。現行見 `docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`。本節其餘仍有效。


Freeze §13-2 四情境（Top 5／Top 10／collapsed／never rendered）→ 在 UI2 期以 **VM `context`** 驗（G3）；Stage F 後同一組測試改驗 **Decision Digest**（`to_dict()` 去除 `generated_at` 類時間戳後逐欄相等）。

### §9.5 Floor 驗證

`requirements.txt` floor（現場讀，憲法不釘版本號；`CLAUDE.md` §8.2.A.0 規則 4）由 AST 守衛（CI）＋手動 `tools/phase3_verify/appttest_floor156.py`（非 CI）驗；UI2 用到的新 API 須先查 floor 是否存在（invD C-ENV-2）；`st.html` 在 floor 會剝行內 `<svg>`（DOC）→ sparkline 沿用 `src/ui_v2/compact.sparkline_svg` 既有解法。

### §9.6 真資料／真機驗收

**在 Stage I**（Freeze §18、客戶 Stage I 原文）：Desktop 真資料、Mobile 真機／正式 viewport、Cold Start、Partial Data、Stale、API Failure、AI Failure；系統仍須安全顯示 deterministic output。UI2 期的 fixture 測試**不等於**驗收；真機驗收依賴 G1 Preview 方式（G1=A 才有真機＋真登入）。

---

## §10 Consumer boundary（UI2／LINE／Decision Digest／OneBrain）

### §10.1 原則（客戶原文）

「New UI2 與 LINE 都是 consumer。」〔(5)-3〕「LINE 不得形成第二套投資大腦。」〔(5)-10〕「本批只定 interface／ownership。不要修改 LINE production。」〔(5)-10〕

### §10.2 Interface 與 ownership（AI 總管暫定；客戶可推翻）

| 層 | Owner（模組位置） | 對外 interface | 過渡期（Stage F 前） | 目標（Stage F／G 後） |
|---|---|---|---|---|
| Deterministic Rules／Risk Cap | L0 `shared/*`、L2 `src/compute/**`、L3 `macro_state_locker`／`risk_cap_apply`／`allocation_service`／`dividend_station_service` | 既有函式（change-frozen） | 同左 | 同左 |
| **System Action State** | L3 新組裝層（Stage F；`FUI-SYSTEM-ACTION-LAYER`）——**只彙整**既有分支＋Risk Cap 封鎖紀錄，⛔ 新規則 | 單一唯讀物件（含 rule result、Risk Cap 封鎖、未評估清單、加／留／換／減計數、跨頁 ⚡ N） | **不存在**；~~G3′=A′：先建最小彙整切片（§4.5）；G3′=B：UI2 動作欄位 `⬜ 尚未提供`~~ Q2：System Action Aggregator 契約凍結（§4.6）、implementation Gate 後實作；實作前 UI2 動作欄位 `⬜ 尚未提供` | UI2 VM、Digest、LINE 皆從此讀 |
| **Decision Digest** | L0 `shared/decision_digest*`（契約）＋L3 `decision_digest_builder` | `DecisionDigest`（`SCHEMA_VERSION`） | 0 production caller；UI2 Viewer `⬜ 尚未提供` | Headless 組裝；UI2 VM／LINE formatter／OneBrain 共同唯一輸入 |
| **View Model** | L3 `src/services/ui2/*_vm.py`＋L0 `shared/ui2_contract` | VM 型別 | 輸入＝feed（既有規則輸出）＋System Action Aggregator（~~系統動作彙整層~~）（~~G3′=A′~~ Q2 核准、implementation Gate 後） | 輸入＝Digest（只換 feed 來源，VM／畫面不重做） |
| **New UI2** | L5 `src/ui2/**`＋L6 `app_ui2.py` | — | consumer | consumer |
| **LINE formatter** | L2 `src/compute/notify/*`＋`scripts/push_*`（**DO NOT TOUCH**） | `dispatch.send_notification` | **維持現狀**（station digest＋自建定調＋各自 Gemini） | 改讀 Digest（另批、另 Gate） |
| **OneBrain** | Stage G（provider-neutral） | 結構化輸出（Freeze §15.2） | ⛔（Stage F 合格前不得開始） | 只讀完整 Digest；grounding；deterministic fallback |

- **Ownership 規則**：動作權威只屬 System Action State（Freeze §0.1.3-3）；UI2 VM、LINE formatter、OneBrain 都只能**引用**（`system_action_ref`），⛔ 各自決定動作或改寫分支名。

### §10.3 現況違反（登記事項；本批不改 LINE production、不改 UI production）

| # | 現況（FACT，讀碼；單組） | 違反哪條 | 登記 |
|---|---|---|---|
| L1 | **LINE 第二套動作權威**：`market_alert_banner.format_extreme_banner`「🚨 極端風險：建議持股降至 10%」（`signal_thresholds.EXTREME_TARGET_POSITION_PCT=10`）、`format_broad_selloff_banner`「建議持股降至 20%」（`global_lead_markets.LEAD_TARGET_POSITION_PCT=20`）；`holdings_digest_message` 個股無動作時寫「請以警語為準」＝把裁決權交給警語。不在 `RULE_ID_ALLOWLIST`、不經 Risk Cap／`allocation_decision`、UI 四頁不顯示 | invariant「System Action State 是唯一正式動作權威」；Q2-5（比例 Action 不得自行產生）同類 | `NUI2-LINE-SECOND-BRAIN`（收編或退場屬客戶 Gate；INFERENCE：屬 2026-08-23 已核准既有功能，⛔ 擅自移除） |
| L2 | **週報自建市場定調**：`weekly_review_service._macro_lite_lines`（加權 vs 年線＋近 20 日）＋Gemini 逐檔建議 | 第二套市場判讀；AI 非 Digest 輸入 | `NUI2-LINE-REGIME-SOURCE` |
| L3 | **cron regime 來源不同**：`dividend_station_service.get_station_macro` 有 session → `allocation_service.get_macro_regime()`；無 session（cron）→ `macro_state_locker.get_macro_state()`（只讀 `macro_state.json`，未進 git） | 同一天 App 與 LINE 位階可能不同（INFERENCE，未實跑 cron 驗） | `NUI2-LINE-REGIME-SOURCE` |
| L4 | **LINE 看不到 Risk Cap**：`push_holdings_daily.py`、`holdings_digest_message.py` grep `risk_cap|exposure` 0 命中 | Q1=A 落地後「⬜ 無法判定時加碼不得當允許」跨 consumer 違規（INFERENCE） | `FUI-PUSH-ACTION-CONSISTENCY`（Stage H） |
| L5 | **持股頁 Gemini 直呼**：`page_hold` ⑦ → `dividend_station_service.build_ai_summary(digest, app_ai_service.gemini_call)` | Freeze §15.1／§15.4 | `FUI-HOLD-GEMINI-DIRECT`（Stage G）；UI2 ⛔ 搬此路徑（G9） |
| L6 | LINE 三支推播的 Gemini prompt 皆非 `DecisionDigest`、無 grounding | Freeze §15 方向 | Stage G |
| L7 | **其他持股比例輸出（第二權威候選，App 端）**：(a) `v4_strategy_engine.check_macro_veto()` 回傳 `max_position`（docstring 自稱「強制持股水位上限」；固定 20／50）；(b) `market_strategy` 的 `exposure_pct`（← `risk_control.portfolio_exposure(regime)`）；(c) 💼 ④ `posture_range`（`get_station_macro()` → `compute_position_throttle()`，未套天花板）。均不經 `allocation_service.get_allocation` 的天花板仲裁（FACT：`page_hold` docstring 自列此清單，`tests/test_p04_hold_allocation_ssot_claim.py` 反向驗其仍存在；consumer 多在 Old UI，未逐一查證） | invariant「System Action State 是唯一正式動作權威」；Single Action Authority | `NUI2-LINE-SECOND-BRAIN`（擴充為「第二權威登記」）；UI2 ⛔ 承接 (a)(b)，(c) 見 §5.4 |

### §10.4 Digest／OneBrain 介面（承 Freeze，不重定）

- Digest 至少保存（Freeze §14 第 4 點）；Presentation Slice 四情境等價（§13）；OneBrain 只讀完整 Digest（Freeze §0.1.3-6、§15.1）；grounding 失敗 → `decision_digest_summary.build_rule_summary` deterministic fallback（§15.4）。
- **UI2 的 OneBrain summary container**＝P10：只顯示 OneBrain 結構化輸出（summary／outlook／signal_consistency／reasons／counter_evidence／limitations／evidence_refs／system_action_ref），⛔ 顯示獨立動作；Stage G 前 `🤖 ⬜ 尚未提供`。

---

## §11 Decision Gates（~~**PENDING**~~ **已裁示 2026-11-02**；送客戶四題；客戶 (5)-5 第 11 項）

> 📌 **裁示結果（逐字見 DEC-123「客戶裁示 Q1～Q4」；下列題文為送題當時版本，保留作歷史）**（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）：**G1→Q1=A**（獨立 Streamlit Cloud Preview＋成本控制四點，§7.3）；**G3′→Q2=A，但修正分類**（System Action Aggregator 屬新的 runtime component，只凍結契約、⛔ 實作，§4.6）；**四頁線框→Q3 核准**（W-4 限輕量 context、W-5=A、W-9「可判定覆蓋度」、W-10 transitional contract、W-11 依 Freeze；線框 §9）；**G2→Q4=A**（Cutover 鏈，§8.3）；**#996→可以現在合併**（已合併，main＝`acd1648c`）。

> 判題原則（AI 總管）：只問「需要客戶人工操作」「何時／如何碰 production」「使用者可見的版面與回退」「投資語意流向」；目錄名、層別、守衛、session／CSS 前綴、feed／VM 拆法、測試設計＝內部自決（v3 §03-1），⛔ 送題。**LINE 維持現狀、不改 LINE production 為客戶已明說〔(5)-10〕，不送題。**
> 📌 2026-11-02 獨立稽核（PASS with fixes）後改版：原 G3「唯讀轉接層」改為 **G3′ System Action Aggregator（~~系統動作彙整層~~）**；原 G4「落盤順序 A／B／C」改為一句是／否，併入 G2；新增「四頁線框核准」為獨立一題。

### G1｜你要在哪裡預覽 New UI2？（涉及你的人工操作與正式網站是否被碰）

- **A（總管推薦）**：開發期先用獨立入口在沙箱看；要給你**手機真機**試用時，**另建一個 Streamlit Cloud 預覽網站**（同一份程式、同一條 main），正式網站入口一行不動。需要你操作一次：在 Streamlit Cloud 建預覽網站、複製金鑰設定、在 Google 登入設定加一個預覽網址。代價：預覽與正式兩個網站各自抓資料，外部資料呼叫約加倍；兩邊登入狀態不共用。
- **B**：在正式網址加 `?ui=2` 切換。你不用設定任何東西，但要改正式網站入口；而且**登入後或重新整理時會掉回現行版面**，持股／我的頁很難預覽。
- **C**：只在沙箱模擬手機尺寸截圖給你看，不提供真機試用。
- **理由**：A 是唯一「正式網站完全不動＋真手機＋真登入＋真資料」的方案。

### G3′｜要不要先建一個「系統動作彙整層」，讓 New UI2 第一版就能用真資料？（投資語意流向）

> 📌 本小節題文為**送題當時逐字**（#997 稽核 m5 還原；先前整合批在題文內改名／加刪除線屬不當改寫，已撤回）。正式名稱改為 **System Action Aggregator**（共用 System Action Aggregation Layer，客戶 Q2）；題文中「總管認為不算新增 runtime」**已被客戶推翻**，見本小節末 📌 與 §4.6（2026-11-02 #997 獨立稽核 PASS with fixes 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔稽核修正〕；原文刪除線保留）。

- **背景**：你要的鏈是 規則 → Risk Cap → **System Action State** → View Model → New UI2；目前**沒有**獨立的 System Action State，各頁的「今日需處理」「是否需要行動」各自在畫面裡算。
- **A′（總管推薦）**：先建**單一個**「系統動作彙整層」（後台、不需要任何頁面打開就能跑），**只把現有正式規則的結果彙整在一起**：合併 ETF 七種分支與個股換股四級（原名照用）、算出加／留／換／減各幾檔、分清「今天沒事」與「判不出來」、在加碼列標上 Risk Cap 狀態、算出各頁共用的「⚡ 需處理 N 項」。**不新增任何規則、不新增任何寫入**（只會觸發既有服務原本就有的動作，例如既有的快取與既有的「更新」流程）。New UI2、日後的 LINE 與 Decision Digest **共用這一份**，畫面本身不再自己算。這等於把原本 Stage F 裡「系統動作彙整」那一小塊提前做。
- **B**：等原 Stage F 的完整 Headless Decision Digest 做完才開始；在那之前 New UI2 的動作相關欄位一律顯示「⬜ 尚未提供」。
- **理由**：A′ 讓動作只在一個地方彙整（New UI2、LINE、Digest 不會各算各的），又能讓 New UI2 用真資料逐頁驗收；B 時程最長。
- **請你確認**：你曾禁止「新增 Risk Cap runtime／OneBrain runtime」；這個彙整層**不新增規則、不新增寫入**，總管認為**不算**你禁止的「新增 runtime」——若你認為算，請選 B。
- 📌 **客戶裁示：A，但修正分類——「它仍屬『新的 runtime component』」；只凍結 interface／ownership／input-output contract／tests／migration plan，本批不得實作 production runtime**（§4.6）（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）。

### 四頁線框核准（`docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md`）

請核准線框，特別是這幾點（其餘 W 點見線框 §7）：
- **W-4**：🎯 標的頁第一屏加一行「市場位階＋Risk Cap 狀態」（推薦：加；理由：Risk Cap 封鎖時任何頁都不得出現無限制加碼，標的頁要看得到）。
- **W-5**：💼「今日需處理」**計入哪幾組**——「留」組＝巡航、🟢 續抱、**暫停加碼**、高溢價、🟡 留意。**A（推薦）**：「加／換／減」＋**暫停加碼**計入「今日需處理」（理由：暫停加碼是 `RULE_ID_ALLOWLIST` 的正式行動 id `pause_add`〔`dividend_station.ACTION_PAUSE_ADD`〕）；巡航／續抱／高溢價／🟡 留意只做分布。**B**：只計「加／換／減」（則只有暫停加碼或 🟡 留意的日子，會顯示「今日無需調整」）。兩者皆：「今日無需調整」只在計入組皆 0 且 0 個未評估時出現。
- **W-9**：「信心度」→「資料齊備度」、「訊號可信度」→「可判定覆蓋度」（只改名，數字與意思不變）。
- **W-10**：📊 市場頁「⚡ 需處理 N 項」的來源——推薦：彙整層建好前**維持現行 ⚡ 的意思**（關鍵警示＋配置衝突，文字照舊）；建好後改用彙整層的同一個 N（與 💼 今日需處理同源）。備選：建好前顯示「⬜ 尚未提供」。
- **W-11**：💼 桌機第一屏——推薦**對齊已拍板的 Freeze 線框**（第一屏：Risk Cap／目前曝險／組合狀態＋今日需處理＋主圖與已核准的建議持股區間，持股表在下方）；備選：持股表優先放第一屏。

### G2｜正式切換怎麼切？以及 #996 可否現在合併？

1. **切換方式**：
   - **A（總管推薦）**：四頁在預覽網站**逐頁驗收**，**四頁都過後一次**把預設切到 New UI2；現行新版改成隱藏入口（`?ui=1`）、舊版維持 `?legacy=1`，兩者**不放可見連結、不刪程式**；出問題時**一行切回**。
   - **B**：逐頁切換正式網站（會有一段時間兩種外觀並存，正式網站要改 4 次）。
   - **C**：其他（請說明）。
2. **#996 合併確認（是／否）**：「#996（Freeze 已兩輪驗收 PASS、CI 綠）可否現在合併？」**推薦：可。** 合併後，本 Architecture Gate 以**新 PR** 落盤（同一指定分支，重設到新 main）。
   - ~~**在此之前，本 Gate 只存在工作樹**（受「只能推指定分支」權限限制，無法另開分支；疊進 #996 又會擴大 #996 範圍，你已禁止）——因此依 DEC-122「沒寫入 GitHub 的新規格，不視為正式完成」，本 Gate 在落盤前**尚非正式文件**。~~
   - 📌 **已解除**：客戶裁示「#996 可以現在合併」；#996 已合併（main＝`acd1648c`），本 Gate 已落盤為 commit `6d30dcea`／Draft PR #997（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）。
- **理由**：切換只動正式網站一次、可立即回滾；先合併已驗收的 Freeze，讓它成為 main 上的正式 input，本 Gate 再以獨立 PR 送審，範圍乾淨。

~~**裁示前暫行（較嚴讀法）**：⛔ 任何 UI2 production code；⛔ 建System Action Aggregator（系統動作彙整層）；⛔ 動 `app.py`；⛔ 建 preview app；⛔ 開始原 Stage A；#996 維持現狀。~~

**裁示後（現行）**：⛔ 任何 UI2 production code（直到 Architecture 凍結並發 🟡 Model／Effort Change Gate、客戶修改後）；⛔ 實作 System Action Aggregator（直到 implementation Gate）；⛔ 動 `app.py`；⛔ 提前要求客戶建 Preview app（Q1：需要時才發 🟡 Manual Action Gate）；⛔ 開始原 Stage A；⛔ 刪 Legacy New UI／Old UI。

---

## §12 Governance 同步清單

### §12.1 本批（docs-only）

| 檔 | 動作 | 慣例 |
|---|---|---|
| `docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md` | 新增（本檔） | — |
| `docs/vnext/NEWUI2_REUSE_MATRIX_2026-11-02.md` | 新增 | — |
| `docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md` | 新增 | — |
| `docs/DECISIONS.md` | 新增 **DEC-123**（客戶 (5) 全文 fence 逐字、裁示要點、與 DEC-122 關係、送客戶四題 G1／G3′／線框／G2＋#996 合併確認 ~~PENDING~~（後於 Q1～Q4 裁示））；DEC-122 條頭加 📌 指向 DEC-123；§5 取代鏈總表加列 | append-only；舊條不刪；📌「有意識的政策變更，不是漏刪」 |
| `docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md` | §17.4 Stage A 段加 📌（暫停；施工路線由 New UI2 Architecture Gate 取代；semantic contracts 不變） | 原文不改 |
| `docs/BACKLOG.md` | §1 新增 DR-2026-11-02-3；§1.1 新增 `NUI2-G1-PREVIEW`、`NUI2-G3-SYSTEM-ACTION-SUMMARY`、`NUI2-WIREFRAME-APPROVAL`、`NUI2-G2-CUTOVER`、`NUI2-G4-MERGE-996`；`FUI-STAGE-A` 改 paused／superseded（刪除線保留）；§5.1.17 加 📌；新增 §5.1.18 `NUI2-*` 主線列 | 0.3 更新規則 |
| `docs/PROJECT_STATE.md` | 新增 §50 | append-only |
| `docs/HANDOFF.md` | 頂端接手點 📌 改指新段；前一 Safe Handoff 標已過期；新增「Safe Handoff（2026-11-02 New UI2）」 | SESSION_CONTINUITY C1；session 紀錄落點同 DEC-122 F6 |

### §12.2 後續批（登記，不在本批做）

- `CLAUDE.md` §8.2 七層表補 `src/ui2/`（L5）、`app_ui2.py`（L6）——UI2 首個實作 PR 同步（`NUI2-GUARD-REGISTRATION`）。
- `tests/test_c3_layering_guard.py` 登記＋meta 測試（G1）——同上。
- `docs/vnext/FINAL_UI_CAPABILITY_MAP_2026-11-02.md` 擴 Old → Legacy New → UI2 三欄（`NUI2-CAPMAP-3COL`）。
- `docs/governance/UI_VISUAL_FIDELITY_GATE.md` 加 UI2 harness 與四頁（含我的）量測（`NUI2-VF-HARNESS`）。
- Presentation Contract §6 表新增 Neutral／Danger tone、`unwired` 改名（原 `FUI-CHIP-NEUTRAL-INFO`／`FUI-UNAVAILABLE-KIND-RENAME`，改由 UI2 components 承接）。

### §12.3 裁示整合批（2026-11-02，客戶 Q1～Q4＋#996 裁示後；docs-only；分支 `ccr-a0b4e085-ijdaio`／#997）

| 檔 | 動作 |
|---|---|
| `docs/DECISIONS.md` | DEC-123 新增「客戶裁示 Q1～Q4」逐字段＋裁示要點；Gate 各點 PENDING → 已裁示（刪除線保留）；#996 合併、#997 落盤 |
| 本檔 | §4.6 System Action Aggregator 契約；§7.3 Q1；§8.3 Q4；§11 裁示結果；§13 完成條件更新 |
| `docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md` | 狀態改「客戶核准」；§9 Q3 裁示落點（W-4／W-5／W-9／W-10／W-11 條件） |
| `docs/vnext/NEWUI2_REUSE_MATRIX_2026-11-02.md` | 狀態更新 |
| `docs/vnext/NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md` | **新增** |
| `docs/vnext/NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md` | **新增** |
| `PROJECT_RULES.md` | 新增第 27 節「永久收尾 Gate」（客戶 2026-11-02，DEC-123） |
| `docs/BACKLOG.md` | DR-2026-11-02-4；§1.1 五題結案；§5.1.18 狀態更新；新增 §5.1.19（客戶點名 16 項獨立列＋衍生待辦） |
| `docs/PROJECT_STATE.md` | 新增 §51 |
| `docs/HANDOFF.md` | 新 Safe Handoff（Architecture 客戶已核准，待 #997 獨立稽核＋合併後凍結） |

---

## §13 完成條件〔客戶 (5)-13〕

只有以下**全部**完成，才通知「🟡 Model / Effort Change Gate：New UI2 architecture 已凍結，後續 presentation implementation 可切 Claude Sonnet 5.5 + Medium。」然後**立即停手、⛔ 自行開始 production**：

| 條件（客戶原文） | 現況（2026-11-02；客戶裁示 Q1～Q4 後更新，舊值刪除線保留） |
|---|---|
| architecture frozen | ~~⬜ 本檔為草案（僅在工作樹）；待 G1、G3′、G2 裁示＋落盤＋`NUI2-ARCH-SECOND-AUDIT`~~ ⬜ 客戶已核准（Q1～Q4）；**待 #997 獨立稽核＋合併**後凍結 📌 #997 獨立稽核兩輪完成（第一輪 PASS with fixes → 第二輪 PASS）；**#997 合併即凍結**（merge SHA 由下一位補記）（2026-11-02 #997 獨立稽核第二輪 PASS 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕；原文刪除線保留） |
| reuse matrix frozen | ~~⬜ 草案（單組）~~ ⬜ 隨 #997 獨立稽核＋合併凍結（客戶未逐列裁示；隨 Q1～Q4 整體核准，INFERENCE） 📌 #997 獨立稽核兩輪完成（第一輪 PASS with fixes → 第二輪 PASS）；**#997 合併即凍結**（merge SHA 由下一位補記）（2026-11-02 #997 獨立稽核第二輪 PASS 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕；原文刪除線保留） |
| four-page wireframe approved | ~~⬜ 待客戶核准（W-1～W-11）~~ ✅ 客戶核准（Q3，附 W-4／W-5／W-9／W-10／W-11 條件） |
| migration boundary approved | ~~⬜ 草案 ✅ 客戶核准 Q4（Cutover 鏈＋rollback＋不得先刪）；migration 規則條文化於 Migration／Cutover Contract，隨 #997 稽核凍結~~ **cutover＝✅ 客戶 Q4 核准**（Cutover 鏈＋rollback＋不得先刪）；**migration 規則**（新建＋parity、Old UI 只讀、Legacy New UI 不改、不得整包搬、語意測試先 PORT）＝**AI 總管內部自決**（Migration／Cutover Contract §3，客戶可推翻），隨 #997 稽核凍結（2026-11-02 #997 獨立稽核 PASS with fixes 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔稽核修正〕；原文刪除線保留） |
| preview strategy approved | ~~⬜ PENDING G1~~ ✅ 客戶核准 Q1=A（含成本控制四點） |
| cutover strategy approved | ~~⬜ PENDING G2~~ ✅ 客戶核准 Q4=A |
| no unresolved architecture blocker | ~~⬜ G3′ 未裁示；#996 未合併、本 Gate 未落盤~~ ⬜ 待 #997 獨立稽核＋合併；Aggregator 實作另走 implementation Gate（不阻塞凍結，屬後續 prerequisite） 📌 #997 獨立稽核兩輪完成（第一輪 PASS with fixes → 第二輪 PASS）；**#997 合併即凍結**（merge SHA 由下一位補記）（2026-11-02 #997 獨立稽核第二輪 PASS 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕；原文刪除線保留） |

⚠️ 提醒（INFERENCE）：Sonnet 5.5＋Medium 適用「純 presentation」批；M1 的 `risk_cap_gate` PORT、System Action Aggregator（~~系統動作彙整層（G3′=A′）~~ implementation Gate 後）、💼 持股 VM（G6／G7）、Stage F／G 屬語意／架構批，依客戶 §0 表仍需 **Opus 5.5＋High**——屆時依 DEC-084／DEC-106 比對實際設定，不符即停下通知客戶。

---

## §14 未驗與限制

- 全文單組撰寫；invC／invD 皆單組；「0 命中／只有」皆 grep、**非窮舉**；未跑任何 runtime、未在 Streamlit Cloud／手機實機／Python 3.14 驗。
- OAuth 轉跳後旗標遺失（C-OAUTH-1）為讀碼推論、**未實機驗**；`streamlit run src/<pkg>/entry.py` 的 `sys.path` 行為未驗；`st.navigation` 與現行路由互動未驗。
- cron 中 regime＝`unknown`（§10.3 L3）未實跑 cron 驗證。
- tests 分類（≈298／≈130／≈148／≈77）為 regex 啟發式量級。
- 撰寫組未見客戶原訊息本身，只見總管轉交逐字檔（`customer_directive_2026-11-02.md` 第 (5) 段）；若有出入以原訊息為準。
- 待第二組獨立驗證（`NUI2-ARCH-SECOND-AUDIT`）後，本註保留作 provenance。
- 📌 DEC-124（2026-11-02，append-only）：§4.6.6 O1／O2／`unjudged` 列與 §9.2 G5 的語意修正為實作組單組產出（Aggregator 仍未實作；實作批 A-T2／A-T4 須以 `undeterminable` 與 `not_evaluated` 分列的表格驅動測試落地），待總管複驗與獨立 QA。
