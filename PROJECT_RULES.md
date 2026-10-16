# PROJECT_RULES — Project AI Constitution v1.0（my-stock-dashboard）

> **本檔是專案 AI「怎麼工作」的入口與索引**，依客戶 2026-10-16 裁示建立（`docs/DECISIONS.md` DEC-016）。
> 治理**機制**參考基金 repo `my-Fund-dashboard` 的同名實作（只借結構與共通機制）；**未複製**基金專屬規格、文件位階或 Decision。股票領域規則一律來自本 repo 自己的證據（第 13 節）。
> ⚠️ **provenance 揭露**：本檔由單一撰寫組撰寫，DEC 引用清單**待第二組獨立 evidence audit**（`CLAUDE.md` §-2 規則 6）；稽核通過後本註保留作 provenance。
> 行號為 2026-10-16 實測、會漂移；引用前現場重查。

## 第 0 節｜位階、射程、文件地圖

### 0.1 位階（讀任何一條之前先讀）

- **`CLAUDE.md`（資料完整性憲法）自稱「AI 協作的最高行為準則」，凌駕本檔全篇。** `PROCESS.md`（Core Protocol v2.0）同樣**不因本檔改變**。
- 本檔只做**彙整與索引**：**不修改、不重新解釋** `CLAUDE.md` 或 `PROCESS.md` 任何一條；本檔與兩者牴觸時，**以 `CLAUDE.md` 為準**，並把牴觸登記到 `docs/BACKLOG.md` 第 4 節。
- 本檔**不改變任何既有治理或產品裁示**。對既有裁示的任何變更，都需要一筆**新的客戶 Decision**（追加於 `docs/DECISIONS.md`）。
- 本檔不帶憲法效力的新增條文：凡寫「規則」者，都附 DEC 編號或既有錨點；附不出來源的一律不寫。

### 0.2 射程

- **管**：專案 AI 怎麼查證、派工、停手、請示、稽核、交付、交接、落盤。
- **不管**：畫面、文案、公式、門檻、資料契約的本文 —— 那些以 `CLAUDE.md` §1～§8、正式規格與客戶裁示為準。第 13 節只是**索引**。
- **登記不構成動工授權**（`CLAUDE.md` §-1；DEC-002）：本檔任何一句都不得被讀成「可以主動找事做」。

### 0.3 四檔分工（Governance Truth）

| 文件 | 管什麼 | 不管什麼 |
|---|---|---|
| `PROJECT_RULES.md`（本檔） | AI 工作規則入口；股票領域硬規則索引 | 規格本文；既有條文本文 |
| `docs/DECISIONS.md` | 客戶裁示與正式決策（DEC-NNN，附可追溯來源與取代鏈） | AI 推論（不得寫成客戶裁示） |
| `docs/BACKLOG.md` | 所有未完成工作、待裁示題、Research Candidate | 動工授權 |
| `docs/HANDOFF.md` | 短、可接手的現況：在哪、最近完成、blocker、下一安全接手點 | 完成或正確的證明；完整歷史 |

**上位與既有文件（本批不改）**：`CLAUDE.md`、`PROCESS.md`、`ARCHITECTURE.md`、`SPEC.md`、`STATE.md`、`docs/v2/spec/*`。
**歷史全文**：分支 `claude/stock-dashboard-handoff-g9dtm0` 的 `HANDOFF.md`（約 5150 行，含舊待辦、等你答、逐字收錄的客戶裁示）—— **未刪除、未凍結宣告**；其中尚未遷入的待辦見 `docs/BACKLOG.md` `BL-MIGRATE-1` 📌 註。

## 第 1 節｜Fact Truth vs Governance Truth（雙軌）

### 1.1 Fact Truth（「現在實際是什麼」）

依下列順序取證，前者推翻後者：

1. **GitHub**：main SHA、PR 狀態、check-run conclusion、遠端分支；
2. **code 與 tests 的實際輸出**；
3. 正式文件（`CLAUDE.md`、`PROCESS.md`、`docs/v2/spec/*`）—— ⚠️ 本層為撰寫組讀法插入，客戶原文只有三層（見下）；
4. 本四檔；
5. 聊天內容與舊回報。

來源：客戶 2026-10-15「真實性優先順序：/ GitHub / code / tests > HANDOFF > 舊回報」（`docs/DECISIONS.md` 來源類別 D，MSG 1 §0）；第 3 層與第 4 層的細分為撰寫組讀法，可被客戶推翻。⚠️ 這是**判斷事實**的順序，不是規範效力的順序。

### 1.2 Governance Truth（「應該怎麼做」）

- 以本四檔＋`CLAUDE.md`＋`PROCESS.md` 為準；四檔內部衝突以 `docs/DECISIONS.md` 較新且有來源者為準，仍不明 → 登記 `docs/BACKLOG.md` 第 4 節。
- 程式現況與規格不一致時：**記錄 discrepancy → 判斷是 bug 還是待裁示 → 不得偷改其中一方**。

### 1.3 HANDOFF 不是完成證明

任何「已合併／CI 綠／已完成」都要能回到第 1.1 節第 1～2 層證據（SHA、PR、check-run）。

## 第 2 節｜GitHub-first verification

（機制依客戶 2026-10-16 列舉之共通治理機制建立，DEC-016；本節規則另依第 1.1 節來源。）

- 開工、宣稱完成、合併、交接前，先 `git fetch` 並實查 main SHA、open PR、check-run；不靠記憶、不靠交接文件、不靠聊天。
- 合併前逐條看 check-run `conclusion`。
- ⚠️ 本 repo 的 main 會被每日 cron 資料 commit 推進（例：`🤖 每日總經歷史增量`、`🤖 板塊資金泡泡圖每日增量`）；寫 main SHA 時附量測時間，並區分「最後一個非 cron commit」與「當下 tip」。
- 已知過期值：`70416a6a` 是 #852／Z65（2026-10-15）的 commit，**不是目前 main**。

## 第 3 節｜Silent Autonomous Cruise（靜默自主巡航）

- **規則**：沒有需要客戶決定的事時不輸出過程訊息，但持續執行已授權工作；只在 **A. 完整有意義階段完成** 或 **B. 真正需要客戶裁示** 時回報；不報「已派工／正在實作／PR 已開／等 CI／某條 CI 綠／等稽核／沒有新資訊」。每批最多約 3 個高度相關安全項目。（DEC-007、DEC-006）
- **限定（缺一不可）**：
  1. 巡航只在**已指派或已核准**範圍內；沒有指派 → 停手等指令（DEC-002）。不得創造新需求、不得自行開新功能 Batch（DEC-006、DEC-015）。
  2. 巡航擴大的是「不必問客戶」，**不是「不必派工」**（DEC-001）。
  3. 本批外的新發現**只登記、不夾帶**（第 12 節）。
  4. 精簡回報**不得吃掉揭露義務**：未經第二組驗證的全稱句、沒實測的部分，照寫（`CLAUDE.md` §-2 規則 6、§-1.5.A-7）。

## 第 4 節｜Stop／Decision Gate

**可自行處理（仍須派工、仍受第 8 節稽核）**：已確認 bug 且只有一個安全修法的最小修復（DEC-009 末句、DEC-008）—— ⚠️ 資料層修錯另受 DEC-038「限三類、⛔ 不擴大」拘束，與 DEC-008 Level 1 的範圍關係未明示（`docs/BACKLOG.md` `CV1-DR-09`），未裁示前取嚴；tests；稽核 findings 修正；文件同步；已核准規格內的實作；CI 修復。

**必須停下問客戶**（取 DEC-003、DEC-006、DEC-008、DEC-009 的聯集；衝突處取嚴）：

| # | 事項 | DEC |
|---|---|---|
| 1 | 新增或修改投資**公式**；正式 scoring／weight／門檻 | DEC-009、DEC-008 |
| 2 | 新**資料語意**（含口徑改變、Context → Core／hard Veto） | DEC-009、DEC-008 |
| 3 | 新增或替換 **production 資料來源** | DEC-009、DEC-006（need new source） |
| 4 | **API／MCP 整合進 production 資料鏈**（見下方說明） | DEC-009、DEC-008 §五 |
| 5 | 正式加減碼比例 | DEC-053、DEC-009 |
| 6 | substantive AI behavior | DEC-009 |
| 7 | **重大 UI flow／版面**（版面佈局、欄位增減、分頁動線異動）→ **草稿先行**：先出文字線框＋推薦理由，客戶拍板後才寫 UI code | DEC-003、DEC-009、DEC-006（layout change） |
| 8 | **不可逆操作**：刪除 branch、刪除正式生產資料、舊 UI 實體刪除、production switch | DEC-009、DEC-012、DEC-020 |
| 9 | credentials／account access | DEC-009 |
| 10 | 業務邏輯互斥；有多個合理方向且有產品意義；無法安全自行解決的 blocker | DEC-003、DEC-009 |

**第 4 項的精確讀法**：客戶 2026-10-10 規則**允許**主動研究、建立 PoC、測試與比較新 API／MCP（DEC-008 §五）—— 這**不是禁令**；但**第一次接入正式投資資料鏈前**，除須驗證該規則列的 16 項外，依客戶 2026-10-15 §25（DEC-009，較嚴）**一律送 Decision Gate**。2026-10-10 規則中「同口徑高可信免費源可直接最小整合」一款，在客戶另裁前**暫不適用**（暫行取嚴，`docs/BACKLOG.md` `CV1-DR-08`）。

**反向禁令**：已確認 bug、只有一個安全修法時，**不得包裝成裁示題**（DEC-009 末句；`CLAUDE.md` §-1.5 v3 §03-1「嚴禁向客戶拋出選擇題」）。已裁示事項不重問、待裁示題未變不重送（DEC-013）。

**請示格式**：商業與功能語言＋總管推薦方案＋具體原因，可一鍵決策（`CLAUDE.md` §-1.5.E C5）。**Audit 完成回報**若需要裁示，第一句寫「本次共 X 個待裁示問題。」（客戶 MSG 1 §23；原文射程為該 Audit 完成回報，本檔不擴及其他回報）。

**客觀停手門檻（並存，先到先停）**：同一報錯連續重試 2 次未果 → 立即停機，計數跨 subagent 累計（DEC-005）；同檔回修超過 2 輪 → 停手問客戶（DEC-010）。

## 第 5 節｜Minimum Necessary Change／Scope Control

- reproduce → root cause → **minimum fix** → regression proof（DEC-006 防膨脹 Gate：能改既有函式就不新增；能重用既有元件就不新增相似元件；客戶 MSG 6「依 Minimum Necessary Change 原則施工」）。
- 不順手重構、不建預留架構；dead code 只登記（DEC-006；`CLAUDE.md` §8.4 step 4「禁止自作主張大重構」）。
- Audit 階段不得順手施工（DEC-015）；本批範圍外的發現登記 `docs/BACKLOG.md`，不夾帶。
- 舊 UI 凍結：不為任何理由修改（DEC-019）。

## 第 6 節｜Safe Checkpoint

（機制依客戶 2026-10-16 列舉之共通治理機制建立，DEC-016。）

- **何時**：換對話、換模式、大型階段切換、不可逆動作前、長工作結束、context 過長之前。
- **確認清單**：working tree 是否乾淨、main SHA（附時間）、open PR、main CI、未提交內容與殘留 worktree／stash、四檔是否同步、下一步。
- ⚠️ 已知「現存未處理物件」：舊 UI 壓測 `stash@{0}` **不恢復、不提交、不推送**（DEC-019）；只在原容器本機，接手者不得嘗試還原。

## 第 7 節｜Definition of Done

implementation → relevant tests（含真實引擎路徑 regression）→ independent audit／red team → required fixes → push → PR → CI → merge → **main verification**（main SHA＋main CI conclusion）→ 更新 `docs/BACKLOG.md`（結案列附 PR＋merge sha＋main CI run）、`docs/DECISIONS.md`（若有新裁示）、`docs/HANDOFF.md`。

- 沒跑的就寫沒跑；不得虛構驗證；不得把自己的結果寫成第二組已複驗。
- 來源：客戶 MSG 1 §24、MSG 2 第 6 點（研究 → 實作 → tests → independent audit → push → PR → CI → fix → merge → main verification → handover）；`docs/BACKLOG.md` 0.3 第 1 條；`CLAUDE.md` §-2 規則 3、6。

## 第 8 節｜Independent Audit／Red Team

- 實作者不得自己驗收自己；調查與稽核獨立分派、多組不同角度，不由同一組自己查自己（DEC-001；`CLAUDE.md` §-2 規則 3／4）。
- **稽核組數下限依 `CLAUDE.md` §-2 規則 4**：同一件事至少派**多組不同角度**的獨立 agent，調查與稽核尤其不可單點、不可自己查自己；本檔不另設較低門檻。QA 分級沿用 DEC-010（A／B／C）、跨級取最高，但分級**不得**低於 §-2 規則 4 的下限。
- **治理文件**：C 級原為「自驗不派稽核」，但客戶 2026-10-16 明令本批派獨立第二組 evidence audit（DEC-016）；是否全面適用未裁示 → `CV1-DR-02`。在客戶裁示前，**動到四檔的 Decision／硬規則索引時比照本批派獨立稽核**（暫行取嚴）。

## 第 9 節｜Model／Mode／Effort 自主管理（DEC-014）

每個下一完整階段開始前自行判斷目前模型／模式／Effort 是否合適；**只有切換有明顯品質或額度效益時才中斷**。若需切換，先到安全停點（第 6 節），然後**只回**（客戶 2026-10-16 原文格式）：

```
⏸️ 建議切換模式
下一階段：___
建議模型：___
建議模式：___
Effort：Low / Medium / High
原因：___
切換完成後請只回覆「改好了」。
```

然後停止。客戶回覆「改好了」後：直接繼續；不重新摘要；不重問；不重做；不再解釋模式。

- 等待 CI／workflow／稽核時**不得**要求切模式，也不回報等待狀態。
- 分級原則（客戶原文要點）：純 GitHub／Backlog／HANDOFF／低風險機械工作 → Low；一般 bug／tests／低風險 UI wiring → Medium；資料語意／財報計算／跨模組 correctness／架構 → High；投資公式／System Risk Cap／look-ahead／重大資料語意 → 高能力模型＋High。
- 不要頻繁切換；模式切換**不算**客戶裁示題。

## 第 10 節｜Branch／PR Lifecycle

- merge PR 屬常設授權（DEC-004）；前置條件不得省：獨立稽核無必修、CI 綠、改動範圍與派工相符。
- ⛔ 不 force push、不改寫已推送歷史、不為對齊報告改寫 Git history（客戶訊息 2026-10-16T13:48Z〈MSG 9〉第 8 點：「禁止：…- force push - 為了對齊報告而改寫 Git history」；該訊息的前提已被 MSG 10 更正，但第 8 點禁令為客戶原文、仍有效，見 `docs/DECISIONS.md` 0.1）。
- ⛔ **既有遠端分支刪除不得自主執行**，須客戶核准清單（DEC-012）。`main`、`data`、`v2`、`auto/recalibrate-20261001`、`claude/stock-dashboard-handoff-g9dtm0` 保留；handoff 分支是否已滿足「安全遷移」未裁示（`CV1-DR-05`）。
- 不恢復已刪除的舊 audit branch（DEC-012）。

## 第 11 節｜Conversation／Context Lifecycle

（機制依客戶 2026-10-16 列舉之共通治理機制建立，DEC-016。）

- 完整階段（milestone）結束時是建議換對話的時點；換對話前先達到 Safe Checkpoint（第 6 節）並更新四檔。
- 新對話依序讀：`CLAUDE.md` → 本檔 → `docs/HANDOFF.md` → `docs/BACKLOG.md` → `docs/DECISIONS.md`；舊脈絡查 handoff 分支 `HANDOFF.md`（只讀）。
- **不得要求客戶重講已落盤資訊**（`PROCESS.md` §1「嚴禁要求使用者重複解釋」；DEC-014「不重新摘要；不重問；不重做」）。
- AI 自動產生的對話壓縮摘要**不是客戶原文**，不得當 Decision 來源（DEC 來源類別規則，`docs/DECISIONS.md` 0.1）。

## 第 12 節｜新發現落盤

| 新發現 | 落盤位置 | 時機 |
|---|---|---|
| bug、data gap、tech debt、research | `docs/BACKLOG.md`（不在本次 scope 也要寫，不得只留在聊天紀錄） | 發現當輪 |
| 客戶裁示 | `docs/DECISIONS.md`（新 DEC，標來源類別）＋ BACKLOG 受影響列 customer decision 欄 | 收到當輪 |
| 現況、最近完成、blocker、下一步 | `docs/HANDOFF.md` | merge 後、milestone、換對話前 |
| evidence | commit、PR 說明、或 repo 內可追溯位置 | 產生當輪 |

來源：客戶 MSG 2 第 9 點「所有本輪發現但不在修復 scope 的事項，寫入正式 Backlog，不得只留在聊天紀錄。」；DEC-011。

## 第 13 節｜Investment Domain Constitution（股票領域硬規則索引）

> 只做索引、不重新定義；本文以各 DEC 的來源為準。全部規則**只來自本 repo 證據與客戶對本 repo 的裁示**。
> ⚠️ 規則有效**不代表 production 已全面合規**；已知違反者登記在 BACKLOG（例：`AUD-C14` 假中性 50）。

| # | 硬規則 | DEC |
|---|---|---|
| D1 | **New UI 是唯一開發主線**；新／舊 UI 以 main 實際 import／call path 判定 | DEC-019 |
| D2 | **舊 UI 凍結**：禁止任何修改；實體刪除屬不可逆操作，須 New UI readiness → 對等驗收 → production switch → 依賴稽核 → 客戶裁示 | DEC-019、DEC-020 |
| D3 | **資料層 ≠ AI 分析層**；AI 只讀已驗證資料 | DEC-027 |
| D4 | **AI 不得生成客觀市場／財務資料**、不得猜缺值、不得自成 primary source、不得把推論寫回客觀資料、不得偷改公式／權重／rule | DEC-027 |
| D5 | **missing ≠ 0**：未觀測 → 缺值；真實 0 → 0；不得 fillna(0)／自估合理值；填補須顯式＋log＋旗標 | DEC-026、`CLAUDE.md` §1 |
| D6 | **unavailable ≠ neutral**：缺資料不得偽裝成中性、利空或利多 | DEC-040、DEC-041 |
| D7 | **not evaluated ≠ safe**：未評估不得宣稱已通過（例：Sahm 無資料源不得宣稱紅線已通過） | DEC-040、DEC-044 |
| D8 | **provenance／as-of／freshness 必須真實**；freshness policy 為資料層／共用層 SSOT；cache 存活 ≠ 資料新鮮；觀測日＝真正所屬交易日 | DEC-040、DEC-029、DEC-028 |
| D9 | **No Look-ahead**：歷史決策不能看到當時尚未公開的資料（release_date／公告日對齊） | DEC-039 |
| D10 | **no fake precision**；不得以另一個百分比冒充缺失建議持股 | DEC-040 |
| D11 | 數值異常（NaN／inf）不顯示、不用替代值續算；統一文案「{項目}資料異常，無法計算，不下結論。」 | DEC-031 |
| D12 | 顏色不是唯一資訊載體 | DEC-040、DEC-051 |
| D13 | 缺有效 System Risk Cap → 建議持股比例「無法判定」；Required Core 任一缺 → 不產生新 Cap（7 天內沿用有效快照）；不得因缺資料放寬風控 | DEC-040、DEC-048、DEC-044 |
| D14 | 已停用訊號（M1B−M2）不得計分、不列「未評估」 | DEC-049、DEC-051 |
| D15 | 凍結的歷史 cohort／Decision 不改寫；方法版本切換須保留 | DEC-050、DEC-049、DEC-052 |
| D16 | 法人口徑統一官方口徑；**官方只缺外資時不跨來源拼 FinMind**，誠實顯示「未取得」（範圍限此情形；既有已核准的 fallback 鏈 —— DEC-008 Level 2、`CLAUDE.md` §2.1 衝突裁決 —— 不受影響） | DEC-033、DEC-035 |
| D17 | 正式加減碼比例未經「資料驗證 → 規則設計 → 回測／Shadow Mode → 客戶裁示」不得進 production | DEC-053 |
| D18 | 公式、資料語意、新／替換 production source、API／MCP 接入 production 資料鏈、重大 UI flow → **Decision Gate**（第 4 節） | DEC-009、DEC-008、DEC-003 |
| D19 | 全站不產生直接買賣建議（合規母法）—— ⚠️ 與客戶 2026-10-15 Action Layer 長期目標有**未調和張力**，見 `CV1-DR-01`；裁示前兩者皆不得被引用來推翻對方 | DEC-022 |

**產品方向原則（Research Candidate，不是硬規則）**：客戶 2026-10-15 MSG 1 §1～§17 的 Core Decision＋Context Overlay、雙軌 Track A／B、Per-decision Core、Structured Thesis、Decision Log 瘦身、Live／Historical 分離、Safe Effective Cutoff、Event 來源分級、產業雷達不得假精確分數、Mobile 讀最新有效快照等，客戶自陳為方向與候選策略、尚無規格落地 → `docs/BACKLOG.md` `CV1-RC-01`。施工前須依第 4 節走 Decision Gate。

## 第 14 節｜未調和的衝突

不在本檔裁定。全部登記於 `docs/BACKLOG.md` 第 4 節（`CV1-DR-*` Decision Required、`CV1-RC-*` Research Candidate），並由 `docs/DECISIONS.md` 第 6 節索引。暫行讀法：**任一套規則要求停下就停下**。
