# New UI2 Audit／Acceptance Checklist

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
- [ ] 冷啟動＝灰色說明（⛔ 紅）；紅色兩義文字不同（真錯誤 vs `🔴 Risk Cap 超限 · 禁止新增曝險`）
- [ ] 每卡 value／state／as_of／source；⛔ 共用全域更新時間；缺 as_of → `⬜ 資料日未提供`

## §5 Risk Cap〔Fz §0.1.4；Q1=A of DEC-122〕

- [ ] 目前曝險或有效上限任一不足 → `⬜ 無法判定`
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
