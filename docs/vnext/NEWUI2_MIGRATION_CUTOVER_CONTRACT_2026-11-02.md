# New UI2 Migration／Cutover Contract

- **狀態**：**客戶核准（Q4=A，2026-11-02；逐字見 `docs/DECISIONS.md` DEC-123「客戶裁示 Q1～Q4」）；隨 #997 獨立稽核＋合併後凍結。** Cutover 鏈、rollback、不得先刪、Removal Gate 另進＝客戶原文；migration 細則（§3）＝Architecture Gate §5 的條文化，屬 AI 總管內部自決（客戶可推翻）。
- **日期**：2026-11-02　**基準**：`origin/main`＝`acd1648c`（#996 合併點）；分支 `ccr-a0b4e085-ijdaio`（PR #997）。以當下 `git fetch` 為準（DEC-118）。
- **上位**：`CLAUDE.md` > `PROCESS.md` > `PROJECT_RULES.md` > DEC-123 > DEC-122 > `docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md` > 本檔。語意一律取 `docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md`。
- **配套**：逐批驗收＝`docs/vnext/NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md`；可重用／不可碰清單＝`docs/vnext/NEWUI2_REUSE_MATRIX_2026-11-02.md`。
- **不授權施工**：本檔登記規則，**不構成**任何 production 動工授權（`CLAUDE.md` §-1）；UI2 實作待 Architecture 凍結並經 🟡 Model／Effort Change Gate；System Action Aggregator 另待 implementation Gate。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：單組撰寫；rollback 細節（`?ui=1`、OAuth 落點）為讀碼推論、**未實機驗**（invD C-OAUTH-1）。

---

## §1 Cutover 鏈（客戶原文，逐字）

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

- 「現有 New UI 與 Old UI 在 Cutover 後先保留 rollback path。」〔客戶 Q4〕
- 「不得先刪程式。」〔客戶 Q4〕
- 「正式切換後，再另進 Removal Gate。」〔客戶 Q4〕

### §1.1 各關卡的通過判準（AI 總管暫定；檢查表見 Audit／Acceptance Checklist）

| # | 關卡 | 通過判準 | 對應 BACKLOG |
|---|---|---|---|
| C1 | 獨立 Preview | 獨立 Streamlit Cloud Preview 可開、正式網站 0 diff；Preview 與 production 讀相同 canonical services／contracts（客戶 Q1）；需人工建 App／Secrets／OAuth 網址時才發 🟡 Manual Action Gate | `NUI2-PREVIEW`、`NUI2-PREVIEW-APP-MANUAL` |（依賴：`NUI2-PREVIEW`）
| C2 | 四頁逐頁驗收 | 每頁：線框（客戶核准版＋§9 條件）一致；第一屏四問；L1／L2／L3；Visual Fidelity（含 Decision Density／Text Reduction）；PR 驗收六問；**動作欄 `⬜ 尚未提供` 只允許在 Preview 期**——C2 通過前 💼／📊 的動作能力必須已改讀 System Action Aggregator（`NUI2-AGGREGATOR-IMPL`、M-A3）（#997 稽核 M2） | `FUI-STAGE-B`～`E`（落點改 UI2） |（依賴：`NUI2-VM-BOUNDARY`、`NUI2-AGGREGATOR-IMPL`）
| C3 | mobile／desktop | 390×844 與 1440×900 第一屏「不用滑」項目全部可見（各頁清單見線框 §1）；放不下 → Decision Gate，⛔ 自行移出 | `NUI2-ACC-MOBILE`、`NUI2-ACC-DESKTOP` |
| C4 | missing／stale／source failure | 四態字樣與色正確；missing ≠ 0／HOLD／neutral；unavailable ≠ safe；部分失敗真錯誤外露；冷啟動灰色 | `NUI2-ACC-MISSING-STALE-FAILURE` |
| C5 | real-data acceptance | 真資料（非夾具）四頁全通；Cold Start、Partial Data、Stale、API Failure、AI Failure 下仍安全顯示 deterministic output（Freeze／客戶 Stage I） | `NUI2-ACC-REAL-DATA`（＝`FUI-STAGE-I`） |
| C6 | cross-page consistency | 同一 market context；Risk Cap blocked／無法判定時任何頁 ⛔ unrestricted Add；術語統一；市場 ⚡ 與持股今日需處理同源（Aggregator 完成後；完成前依 W-10 並列揭露）；Aggregator 完成並經 M-A4 後，市場 ⚡ 與持股今日需處理**必須同源**（W-10 transitional 不得延續到 cutover）（#997 稽核 M2） | `NUI2-ACC-CROSS-PAGE`（＝`FUI-STAGE-H`） |
| C7 | 全部通過 → 一次切成正式 default | C1～C6 皆有 PR／報告證據＋獨立 QA；一次 PR 切換 `app.py` 預設；切換前 G11 路由毒化測試綠；**前置必含 `NUI2-AGGREGATOR-IMPL`＋M-A3＋M-A4 完成**（否則持股頁動作能力消失）（#997 稽核 M2） | `NUI2-CUTOVER` |

---

### §1.2 Cutover 前置清單（#997 獨立稽核 M1／M2；對映 BACKLOG §5.1.19 編號）

| 類 | 項目 | 是否 cutover 前置 | 依據 |
|---|---|---|---|
| Q4 鏈各關 | #1 New UI2 Preview（`NUI2-PREVIEW`）、#2 View Model boundary（`NUI2-VM-BOUNDARY`）、#9 mobile（`NUI2-ACC-MOBILE`）、#10 desktop（`NUI2-ACC-DESKTOP`）、#11 missing／stale／failure（`NUI2-ACC-MISSING-STALE-FAILURE`）、#12 real-data（`FUI-STAGE-I`）、#13 cross-page（`FUI-STAGE-H`） | **是** | 客戶 Q4 Cutover 鏈逐字 |
| 動作能力 | #3 System Action Aggregator implementation（`NUI2-AGGREGATOR-IMPL`，含 M-A3、M-A4） | **是** | `⬜ 尚未提供` 只允許在 Preview 期，否則持股頁動作能力消失（M2；Architecture Gate §4.6.5） |
| 非前置 | #4 Risk Cap Numeric Gate（`FUI-RC-NUMERIC-GATE`）、#5 proportional action rules（`FUI-PROPORTIONAL-ACTION-RULES`）、#8 LINE／UI canonical action convergence（`NUI2-LINE-UI-ACTION-CONVERGENCE`） | **否** | 數值未啟用時 Risk Cap 恆 `⬜ 無法判定`（Q1=A）；比例 Action 未核准即不顯示（Q2=A of DEC-122）；LINE 改動另批另 Gate（客戶 (5)-10） |
| 讀法待定 | #6 Headless Decision Digest（`FUI-STAGE-F`）、#7 OneBrain runtime（`FUI-STAGE-G`） | **AI 總管讀法：是**——DEC-122 保留的 Stage 順序 F → G → H → I，而 Q4 鏈含 cross-page consistency（H）與 real-data acceptance（I），故 F、G 在其前；**客戶可推翻**；接近 cutover 時若欲讓 F／G 不再是前置（提前 cutover），**另送客戶裁示** | DEC-122 原文 §2 順序；DEC-123 Stage F～J 保留 |

## §2 Rollback（Cutover 後保留）

| 路徑 | 機制（AI 總管暫定） | 規則 |
|---|---|---|
| **Legacy New UI**（現有 New UI） | 隱藏參數 `?ui=1` | 不放可見連結（比照 DEC-097；若客戶要可見連結需裁示）；程式**不刪** |
| **Old UI** | 維持 `?legacy=1` | DEC-097／DEC-019／020 照舊；程式**不刪** |
| **整體回滾** | `app.py` 預設值一行切回 | UI2 不寫投資狀態 → 回滾不留資料殘留；UI2 session key 一律 `ui2_` 前綴，⛔ 與 `_nav4_page` 等共用 |
| **毒化守衛**（G11） | 毒化 UI2 套件 → `?ui=1` 與 `?legacy=1` 仍完整載入 | 比照 `tests/test_nav1_app_routing.py`；cutover PR 必備 |

- **OAuth 降級揭露**：cutover 後登入回呼落地即 UI2；`?ui=1`／`?legacy=1` 使用者登入後會回到 UI2（可接受降級，交付須揭露；未實機驗）。
- **Rollback path 保留期限**：直到 Removal Gate 通過（§4）；⛔ 以「已切換」為由刪除任何 rollback 入口。

---

## §3 Migration 規則

1. **Old UI 只讀**〔客戶 (5)-4「禁止修改」〕：需要的業務邏輯 **新位置另建＋parity／golden 測試**，Old UI 原檔一字不改；保留至 Removal Gate。
2. **Legacy New UI 不改（預設）**：同樣**新建＋parity**；把 legacy 原處改成 re-export 薄別名＝**備選**，會動 production UI 檔，**需客戶同意**＋byte-identical 守衛才可採用（Architecture Gate §5.1-3）。
3. **規則／公式 change-frozen**：⛔ 改既有 L2 規則、`shared/*_thresholds`、`risk_cap_policy`；PORT 只搬呈現既有規則所需的純函式；客戶核准字樣逐字搬。
4. **不得整包搬**（逐函式挑選；Architecture Gate §5.4）：
   - `_target_blocks` 以 `guard_chip` 承載判型／計數／估值口徑（違 Freeze §4.2）；
   - `page_hold` ⑦ Gemini 直呼（`build_ai_summary(digest, gemini_call)`）；
   - `page_why` AI QA（`ai_qa_service.run_agent`）；
   - 「訊號可信度」「信心度」標籤（改「可判定覆蓋度」「資料齊備度」，W-9）；
   - builder 回傳 Old UI `tab_today.Card` 型別；
   - `compact` 對五頁版面契約的傳遞依賴；
   - `build_macro_stage_card` 的 ④ `posture_range`（未套天花板）。
5. **語意測試先 PORT 再退場**：New-UI-bound 測試中的語意守衛（missing≠hold、FX 不加總、as-of、silent-fail、secret scrub、breadth gate、nonfinite gray 等）先改寫成 UI2 presentation-contract 測試並轉綠，原測試才可隨 Legacy New UI 退場（`NUI2-NEWUI-SEMANTIC-TEST-PORT`）。
6. **⛔ 第二套 pipeline**〔客戶 Q1〕：Preview 與 production 讀相同 canonical services／contracts；⛔ 為 UI2／Preview 新增 fetcher、cache、資料分支。
7. **會改既有 service 者須客戶 Gate**：`allocation_service` session-free 簽名（S23）、移除 Old UI `section_mid` render 期 `register_conflict`（OLD-7）——未經客戶 Gate 不得做。
8. **System Action Aggregator**：契約凍結於 Architecture Gate §4.6；實作待 implementation Gate（`NUI2-AGGREGATOR-IMPL`）；實作前 UI2 動作欄位 `⬜ 尚未提供`，VM ⛔ 自行聚合。

---

## §4 Removal Gate（正式切換後另進）

- **對象兩個，各自走 Gate**：Old UI、Legacy New UI（`NUI2-REMOVAL-GATE`；承 `FUI-STAGE-J`）。
- **條件（取聯集）**：Freeze §19 六條件（四頁能力 coverage、mobile acceptance、real data acceptance、audit coverage、user final acceptance、capability map 無 critical gap）∪ DEC-083 第 11 點 E 段七步（capability inventory → Old→New mapping → implementation → interaction coverage → regression → customer verification → Removal Decision Gate）；另加：Capability Map 擴為 Old → Legacy New → UI2 三欄（`NUI2-CAPMAP-3COL`）且無 critical gap、§3-5 語意測試已 PORT。
- **Cutover ≠ Removal**：切換預設只是路由翻轉；刪除任何程式都必須另送客戶 Removal Decision Gate。

---

## §5 未驗與限制

- 單組撰寫；未實機驗 OAuth 轉跳與 `?ui=1` 行為；Preview Cloud app 尚不存在。
- §1.1 判準與 §2 機制為 AI 總管暫定；與客戶原文有出入時以 DEC-123 逐字為準。
