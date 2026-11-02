# Final UI Supersede Map（Conflict／Supersede：客戶 2026-11-02 指示 vs 現行 DEC／契約）

- **狀態**：**客戶指示 A 生效；Freeze 內容待客戶拍板（含 Q1～Q3）**——本表的取代判讀隨 Freeze 送客戶拍板，拍板前「部分取代」各條只作為待拍板的判讀，**舊條文在拍板前一律照舊有效**（Final UI Contract Freeze 配套；決策 `docs/DECISIONS.md` **DEC-122**；契約 `docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md`；能力對照 `docs/vnext/FINAL_UI_CAPABILITY_MAP_2026-11-02.md`）。
- **日期**：2026-11-02　**基準**：`origin/main`＝`ce8422d`（撰寫組 `git fetch` 實查；以當下 `git fetch` 為準）。
- **決策來源**：「不要直接刪除或覆蓋舊 DEC；要明確記錄哪些內容被 supersede、哪些繼續有效」＝**客戶 2026-11-02 裁示第 1 點（逐字見 DEC-122）**；各條的 supersede 判讀＝依客戶指示原文逐條比對（盤點底稿＝invA 調查 §5 S1～S18，2026-11-02，單組），判讀者標於各條。
- **上位**：`CLAUDE.md` > `PROCESS.md` > `PROJECT_RULES.md`（第 25 節）＋`docs/governance/*` > DEC-122（最新客戶 DEC）> 本檔。
- **慣例（沿 `PHASE1_SUPERSEDE_MAP_2026-10-29.md`）**：舊條文**一字不刪**；只在原處加 📌「部分取代 BY DEC-122」＋「有意識的政策變更，不是漏刪」＋日期 2026-11-02＋決策者 客戶（DEC-122）＋兩邊理由；**客戶 DEC 的呈現裁示只有在客戶新指示明確點名或直接牴觸處才被取代**（`PROJECT_RULES.md` §25.3），其餘一律維持。
- **表內欄位**：〔客戶 §n〕＝客戶 2026-11-02 指示章節；「落標」＝本 PR 在何處加了 📌。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：單組撰寫；盤點底稿 invA 為單組 grep＋讀檔；DEC-109 全文（約 1,170 行）只比對 Phase 列表與被引段；**「取代判讀只有本表 S1～S20 與 §2 條件式各項」是單組結論**（經一輪獨立稽核補正：新增 Q3 條件式、DEC-051／PQ-C6-3、DEC-074／075、DEC-109 十一／十三／二十一、DEC-083 E 段、Gate §8 例外表、DEC-110 R8），仍只能當待驗事項（BACKLOG `FUI-FREEZE-SECOND-AUDIT`）。

---

## §1 Supersede 表（S1～S20；S10／S11 為條件式待 Q3）

| # | 舊條文（DEC／契約＋章節） | 被 supersede 的部分 | 仍有效的部分 | 依據（客戶 2026-11-02） | 判讀者 | 落標 |
|---|---|---|---|---|---|---|
| **S1** | **DEC-107** 第 1 點（1A 整頁順序：問句→資料狀態→搜尋→AI→第一區→第二區→第三區→進階） | 單頁全展開順序 → **雙模式**（[市場精選][即時查一檔]，不得同時完整展開；查詢後精選收合） | 2A（選一檔＋🔍 查看此檔＝精選模式進入 workspace 的入口）、3A（不放 ⚡）、4A 六欄、5A（仍未覆蓋功能揭露）、補充邊界（不新增資料源／公式／語意／Risk Cap／AI 規則；不寫 Sheet；缺維度 ⬜）、效力邊界 | 〔客戶 §10、§12〕 | 客戶原文明示；位置讀法＝撰寫組 | ✅ DEC-107 條頭 📌 |
| **S2** | **DEC-121** Q2=B「整頁已核准順序不變」一句 | 「順序不變」 | Q2 其餘（選股條件預設收合＋一行摘要、候選 Top 10、完整候選展開取得、`DEFAULT_TOP_N=50` 不變、Top 10 僅呈現切片）；**Q1=A、Q3=A 全部**；效力邊界（DEC-117～120 例外不繼承） | 〔客戶 §10、§11〕 | 同上 | ✅ DEC-121 條頭 📌 |
| **S3** | **DEC-099** 第 3 點的終態讀法（「整合回單一 🎯 標的頁並移除此過渡切換」→ 不得有任何模式切換） | 「單一頁不得有模式切換」的**終態**讀法 | 第 1 點（過渡切換不是最終設計）、第 2 點（不視為新增正式 IA）、第 4、5 點；「已執行完畢」歷史紀錄（PR #968）。**新雙模式是頁內元件，⛔ 回到 NAV-1 葉選擇器 `NAV4_TARGET_LEAF_KEY`** | 〔客戶 §10、§12〕 | 撰寫組讀法（INFERENCE：DEC-099 否決的是 NAV-1 過渡葉選擇器，不是最終設計的頁內模式） | ✅ DEC-099 條頭 📌 |
| **S4** | **Presentation Contract** §6 R8 第 2 點、§8 第 3 點；**`UI_VISUAL_FIDELITY_GATE.md` V8**（「🔴／紅色只給系統真錯誤」） | 「只」→ 擴為「系統真錯誤＋**確定性違規（Danger／Risk Cap）**，兩者文字必須不同」 | 未載入＝灰；stale 用 ⚠ 琥珀；每個色塊都要有文字；metadata chip 不在訊號文字頻道；`CLAUDE.md` §1.A 第 4 點（不衝突，原文不動） | 〔客戶 §4、§19〕 | 客戶原文明示 | ✅ 契約 §6／§8 📌、Gate V8 📌 |
| **S5** | **DEC-115 D3=A** 末句「不得新增會與既有 Missing／限制語意混淆的第四套視覺語言」 | 新增 Positive／Warning／Danger／Neutral-Info **語意 tone 軸**（與三族外觀軸正交） | 三族外觀（資訊／狀態／護欄）、護欄實線粗框、D10(a)；該句的**目的**（不得與 Missing／限制語意混淆）仍有效；D1a／D1b／D5／D6／D8 全部 | 〔客戶 §4〕 | 客戶原文明示；兩軸讀法＝撰寫組 | ✅ DEC-115 條頭 📌 |
| **S6** | BACKLOG **`P5-CHIP-KIND-NAMES`** 的「或維持」選項 | 判型／計數／估值口徑繼續用 `guard_chip` | 該列其他敘述；`guard_chip` 用於客戶逐字護欄句 | 〔客戶 §4〕「禁止拿 guard_chip 之類的警告元件表示：半導體、3 項、PE、股票」 | 客戶原文明示 | ✅ BACKLOG 該列 📌 |
| **S7** | **Presentation Contract** §6 表 `unavailable` 列（＝委派 `⛔ 未接線`） | 「Unavailable」一詞改指**來源目前不可用**；舊義改稱「功能尚未提供（未接線）」 | `⛔ 未接線` 符號與字樣（功能未接）不變；**§6 表該列文字本 PR 不改**（`tests/ui_v2/test_compact.py::_contract_kinds` 以此表對帳 `META_KINDS` 20 項）→ kind 改名在 Stage A 與程式同 PR 同步 | 〔客戶 §5〕 | 客戶原文明示；處置＝AI 總管暫定 | ✅ 契約 §6 📌 |
| **S8** | **Presentation Contract** §8 第 1 點／客戶 2026-09-23 **D-3(a)** 的 **L1 外露**字樣（`⟳ 缺漏 · 可重跑`、`▨ 無資料`、`⊘ 不適用 · 重跑無效`） | L1 Missing 字樣統一為 `⬜ 資料未取得`／`⬜ 資料未備` | `shared/ui_state.UI_STATE_META` 十態本身（DEC-110 R8 十態不另造）；⟳／⊘／▨ 作為 L0 與 L2 子原因 | 〔客戶 §5〕「全站統一」 | 客戶原文明示；只限 L1 為撰寫組讀法（客戶可推翻） | ✅ 契約 §8 📌 |
| **S9** | **`ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md` §3**「⛔ 把 Risk Cap 連到具體行動」 | 「超限 → 禁止新增曝險／任何地方不得出現 unrestricted Add」這一條 | 其餘「Risk Cap → 具體行動」（例：自動減碼比例）仍屬新規則（HI-1／HI-4）⛔；RC-VISIBILITY 核准前只答 Risk Cap 狀態（**數值啟用 PENDING Q1**） | 〔客戶 §19、§38〕 | 客戶原文明示 | ✅ Boundary §3 📌 |
| **S10**（**條件式，待 Q3**） | **DEC-118 問題 1=A**（手機 ⚡ mobile exception：位於第一屏之後、緊接 3 核心狀態；客戶 2026-10-30 看過「手機第一屏一定看得到是否需行動」選項後知情選 A〔總管轉述〕） | **僅在 Q3=A 時**：📊 市場頁**手機**「是否行動」進第一屏（不用滑），並連帶改 DEC-117 Q1 手機 2＋1；Q3=B 則不取代、§40 在市場頁改讀為「緊接第一屏」；**裁示前 DEC-118 問題 1=A 照舊有效** | 問題 2=D1（更新真錯誤放今日結論正下方）、Customer Decision Gate 輸出硬限制、GitHub Verification Gate 以當下 `origin/main` 為準；桌機不受影響 | 〔客戶 §40〕「市場 不用滑：市場狀態、Risk Cap、是否行動、refresh」 | 客戶原文明示 | ✅ DEC-118 條頭 📌 |
| **S11**（**條件式，待 Q3**） | **DEC-120**（市場頁 A10／A11 🟡 接受為已知偏離） | **僅在 Q3=A 時**：A10、A11 隨 S10 失去前提，降為 Phase 4 歷史基準、Stage B 重新量測；Q3=B 則照舊；**裁示前照舊有效** | A2、A4 例外；「僅市場頁、不得泛化他頁」；Phase 4 Gate PASS 的歷史結論 | 〔客戶 §40、§41〕 | 撰寫組讀法（INFERENCE） | ✅ DEC-120 條頭 📌 |
| **S12** | **DEC-089 G6=A**（🛡️ 逐檔戰情表＋展開明細；Stage B 草稿欄位集：代號、名稱、張數、均價、現價、損益%、市值、健檢等第、235 燈） | L1 欄改為：代碼、名稱、持股比例、成本、現價、報酬、策略、System Action | 「補逐檔戰情表＋展開明細」本身；「欄位僅限已存在事實」；其餘欄（張數、市值、健檢等第、235 燈）下沉 L2；缺值不當 0；G2／G5／G7 與 7 項補充執行條件 | 〔客戶 §22〕 | 客戶原文明示 | ✅ DEC-089 條頭 📌 |
| **S13** | **`PHASE5_TARGET_PAGE_WIREFRAME_2026-10-31.md`** §3.4／§4 單檔區（摘要卡 ≤4＋主圖 placeholder＋「▸ 完整分析」順序） | 單檔 workspace 順序改為：Header → 6 維 Snapshot → Primary Price Chart → Fundamental → Valuation → Institution／Chip → Industry → Risk → OneBrain Research Explanation | 判型 chip（改 Neutral/Info 族，S6）、真錯誤外露、v2 卡面 DEC-111／112 保護、§10 已合併驗收條件（Phase 5 歷史） | 〔客戶 §14、§15〕 | 客戶原文明示 | —（線框檔本 PR 不改；本表登記） |
| **S14** | `shared/decision_digest_rules` docstring「市場事實不編造 rule id」；**Digest 契約 §4**「rule result：市場事實刻意不帶 rule（維持）」 | 市場事實**可以**帶 Registry 產生、對映既有 SSOT 門檻的 rule id | 「Registry 外 id 一律違規」、⛔ 編造 rule id、Digest 不搬門檻值（§6 A8）；現行正式 id 只有 `RULE_ID_ALLOWLIST` 6 個；新 id＝新規格（Stage E／F 內部規格＋獨立 QA）；屬改契約 → Stage F 升 `SCHEMA_VERSION` | 〔客戶 §26、§27、§36〕 | **INFERENCE**（由客戶 §27 範例「VIX 32.4　R-VIX-02」推得；客戶未逐字點名 Digest 契約 §4，客戶可推翻）；命名規則＝內部 | ✅ Digest 契約 §4 📌（程式 docstring 本 PR 不改） |
| **S15** | **`ONEBRAIN_ARCHITECTURE_2026-10-31.md` §11** 概念 schema（status／confidence／evidence／risks／contradictions／reasoning_summary／action_context／missing_data） | 以客戶欄位為**最低集**：summary、outlook、signal_consistency、reasons[]、counter_evidence[]、limitations[]、evidence_refs[]、system_action_ref；`confidence` 不納入（§7） | §11 硬規則全部（只用既有正式詞彙、新詞走 Customer Gate、evidence 回指 Digest／RuleRef、raw text 不是 final result）；`outlook`／`signal_consistency` 值域**未定**→ Stage G Gate | 〔客戶 §35〕 | 客戶原文明示 | ✅ ONEBRAIN Arch §11 📌 |
| **S16** | **DEC-109 三十一** Phase 1～7 執行階段編號 | 以 **Stage A–J** 為準（Phase 7 拆成 F Headless Digest＋G OneBrain；新增 E、H、I、J） | 「不得在 Digest contract 未凍結前寫新 LLM prompt／glue」；「具體 dependency 可以調整」；Phase 1～5 已完成成果（不回退）；DEC-109 其餘各點 | 〔客戶 §2、§52〕 | 客戶原文明示 | ✅ DEC-109 條頭 📌 |
| **S17** | **DEC-060**（一般完成回報 ≤5 行） | **只限 Stage 完成回報**改用客戶 §48 表格 | 「完整技術／稽核證據留在 PR」；一般（非 Stage 完成）回報 ≤5 行；裁示題只留裁示所需資訊 | 〔客戶 §48〕 | 撰寫組讀法（INFERENCE：表格行數 >5） | ✅ DEC-060 條頭 📌 |
| **S18** | `docs/vnext/d25_wireframes/target.html`、`holdings.html`（及 `market.html` 首屏若變）＝Visual SSOT（Presentation Contract §14，DEC-109 二十四） | 對應頁的 Visual SSOT 由 Final UI Blueprint（契約 §2、§16）取代對應部分 | IA 四頁；整體視覺方向；HTML 檔**不改**（同 PHASE1 慣例） | 〔客戶 §6～§27、§40〕 | 客戶原文明示 | —（HTML 不改；本表登記） |
| **S19** | `docs/governance/MODEL_EFFORT_POLICY_2026-10-25.md` Rule 2「文件整理優先 Haiku＋Low」 | 本 Final UI 主線的文件同步改依客戶 §0 表（Sonnet 5.5＋Low／Medium） | 政策其餘；「治理文件不寫死版本號」（本主線沿用客戶原文模型名，為客戶指定，非 AI 自訂） | 〔客戶 §0〕 | 撰寫組讀法（INFERENCE） | —（本表登記；政策檔本 PR 不改） |
| **S20** | **DEC-109 十一**（📊 市場第一屏優先：市場位階、Risk Cap／尚未核准狀態、今日主要風險、是否需行動、主要市場圖）、**十三**（💼 持股第一屏優先：目前該做什麼、需處理幾檔、加碼／留／換／減摘要、主要風險、組合狀態、Primary Visual）、**二十一**（AI 投資總結輸出：市場／持股／標的機會各一句、主要風險 1～3、本期行動 ≤3） | **十一**：不取代，同向——客戶 §6 新增 System Action State、OneBrain Outlook；「今日主要風險」「主要市場圖」§6 未列但未撤銷 → 仍有效（手機位置待 Q3）。**十三**：§19 新增 Risk Cap、目前曝險為第一屏項目（加性，部分取代第一屏優先清單的**組成**）；「加碼／留／換／減摘要」與 §20 五詞的關係 **條件式待 Q2**（Q2=A 時以「加／留／換／減」分組顯示既有分支原名）。**二十一**：不取代——§35 是 OneBrain **domain output schema**，二十一是**呈現切片**（INFERENCE）；二十一「本期行動 ≤3」須引用 `system_action_ref`、⛔ AI 自創 | 十一、十三其餘項；二十一全部（含「Risk Cap 是否限制行動」「哪些地方因 Missing 無法判斷」） | 〔客戶 §6、§19、§20、§35〕 | 撰寫組讀法（INFERENCE） | ✅ DEC-109 條頭第二則 📌 |

---

## §2 條件式／待裁示（**不是**已 supersede；裁示前一律以舊條文為準）

| 舊條文 | 張力 | 狀態 |
|---|---|---|
| **DEC-081 Q2-2**（卡面措辭「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」）＋BACKLOG `RC-VISIBILITY` | 客戶 §6／§19 要 Risk Cap 上 L1 並可執行 | **PENDING Q1**；裁示前逐字仍有效，市場頁維持隱藏 |
| **DEC-051**／**PQ-C6-3**（DR-2026-10-16-4，客戶 2026-10-16 核准：今日頁與持股頁上限卡卡面揭露 Optional 資料完整性；持股頁卡⑤外露建議持股區間 `range_text`） | 市場頁隱藏 vs 持股頁外露＝跨頁差異；客戶 §19 Risk Cap 閘門 | **條件式，待 Q1**（Q1 一併問是否保留持股頁區間）；**裁示前照舊有效**，持股頁區間**不是違規**；DEC-051 中性措辭與完整性揭露在任何 Q1 結果下都仍有效 |
| **DEC-118 問題 1=A**、**DEC-120 A10／A11**、**DEC-117 Q1 手機 2＋1** | 客戶 §40「市場 不用滑：……是否行動」 | **條件式，待 Q3**（見 S10、S11）；裁示前照舊有效 |
| `docs/governance/UI_VISUAL_FIDELITY_GATE.md` §8 例外表「📊 市場頁手機 ⚡ 位於第一屏緊接之後（DEC-118）」列與「四項 🟡 已知合理偏離（DEC-120）」列 | 同上 | **條件式，待 Q3**；已加 📌 |
| **DEC-092 Q4**（不創新行動語意、第一版沿用既有建議動作）、**DEC-053**（正式加減碼比例須驗證＋回測／Shadow＋客戶裁示）、**DEC-054** 七種 Action 名稱 | 客戶 §20 五詞「加碼／持有／減碼 1/2／全出」 | **PENDING Q2**；裁示前仍有效 |
| **DEC-117 Q1** 手機「2＋1」核心狀態排法 | 為滿足 §40，手機第三格（今日主要風險）需移到第一屏之後 | **併入 Q3**（Q3=A 即正式改此排法）；實際放得下與否未實測，Stage B 第一步實測（`FUI-MARKET-MOBILE-FIRST-SCREEN`）；裁示前 DEC-117 Q1 有效 |
| **DEC-092 Q3**／**DEC-117 Q6**（今日主要風險在第一層、退化句逐字外露） | 客戶 §6 市場 L1 清單未列「主要風險」 | **不取代**（客戶 §6 用「包含」；L1 ≠ 第一屏）；桌機維持第一屏，手機緊接第一屏之後 |

---

## §3 「不得讀成已取代」防誤讀清單（全部**繼續有效**）

- **DEC-092 Q2**（台股／國際趨勢未定義＝`⬜ 尚未定義`；AI 不得補多空結論）——客戶 §8「正式趨勢線」不等於定義已核准。
- **DEC-092 Q3**（市場第一層風險）、**Q4**（不創新行動語意）、**Q5**（產業趨勢研究）。
- **DEC-053**、**DEC-054**、**DEC-081 Q2-1／Q2-2**（直到 Q1 裁示）。
- **DEC-083 Q2**（觀察清單／Sheet CRUD＝P2）、**DEC-021** 寫入方向（逐筆、預覽、二次確認、同本重複阻擋）——「加入觀察」CTA 在新 UI 為 disabled，⛔ 讀成已核准寫入。
- **DEC-019／DEC-020**（舊 UI 不得提前刪除；Removal Gate 前置）——Stage J 六條件是加嚴，不是放寬。
- **DEC-105 2A**（市場位階五態、⛔ 映射偏多／中性／偏空）——術語統一（契約 §21）只統一名稱，不改五態字樣。
- **DEC-110 R8**（`UI_STATE_META` 十態不另造；既有徽章族優先）——四態是語意層，不是第 11 態；L1 外露字樣改依客戶 §5（S8），十態符號與 L0 不動；已加 📌。
- **DEC-074／DEC-075** 客戶逐字字樣「`⬜ 未評估／資料不足`」——**保留原字樣**，歸為四態 Not evaluated 的子原因字樣（契約 §5.1），⛔ 改寫成「尚未評估」。
- **DEC-083 第 11 點 E 段 Removal Gate**（舊 UI 暫時保留、七步刪除條件）——與客戶 Stage J 六條件**取聯集**（兩組都成立才可提出 Removal Decision Gate；契約 §19），⛔ 讀成被 Stage J 取代；已加 📌。
- **DEC-044**（Risk Cap 既有細項維持）、**DEC-048**（Required Core）、**DEC-051**（完整性揭露）——「有效上限」判定照舊（契約 §8.1 第 5 點）。
- **DEC-111／DEC-112**（v2 卡面 K1、⛔ 完整原文只剩 hover、▸ 詳細機制）。
- **DEC-115** D1a／D1b／D5／D6／D8／D10(a)；D3 三族外觀。
- **DEC-117** Q2～Q8（含 Q5 桌機順序、Q4 國際 small multiples、Q8 圖 C Research 下沉）；**DEC-119** 題 1／2（手機 Primary 約 220px、自訂圖例；桌機 2.02×）。
- **Digest 契約 §5 不動項、§6 A8**（不搬門檻值）；**OneBrain G1～G10**、**ADR-OB-001**、OB-3（shadow 需 key Decision）、OB-6（另行客戶裁示）。
- **DEC-109** 十五～二十二（Data View ≠ Decision Context ≠ AI Output 等）、二十三～二十八（Gate、Visual SSOT、Durable Memory）。
- **DEC-091(g)／DEC-092**「EPS×PE 保留 Research Framework，正式公式仍需 High Gate」、BACKLOG `DEC092-EPSPE-HIGH-GATE`——客戶 §43 明示保持 Research。
- **DEC-101(1)**（外幣不得與 TWD 加總）——持股比例分母須排除外幣列並揭露。
- **DEC-017 葉1 ②**（兩套刻度常駐揭露）——Stage D 線框待拍板（`P1R-P6-WF-TWO-SCALES`）。
- **HI-1～HI-6** 未核准狀態（含 HI-3 估值帶、HI-5 寫入面）。

---

## §4 本 PR 落標清單（📌 位置）

- `docs/DECISIONS.md`：條頭 📌＝DEC-051（條件式 Q1）、DEC-060、DEC-083（E 段聯集）、DEC-089、DEC-099、DEC-107、DEC-109（兩則：三十一；十一／十三／二十一）、DEC-110（R8）、DEC-115、DEC-118（條件式 Q3）、DEC-120（條件式 Q3）、DEC-121；§5 取代鏈總表新增列；新條 DEC-122。**未加 📌**：DEC-074／075（字樣保留、無取代）、DEC-081、DEC-092、DEC-053／054、DEC-117（條件式／仍有效者只在本表登記）。
- `docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md` §6（S4、S7）、§8（S4、S8）📌。
- `docs/governance/UI_VISUAL_FIDELITY_GATE.md` V 表後 📌（S4＋Decision Density／Text Reduction 新增）；§8 例外表後 📌（DEC-118／DEC-120 兩列條件式待 Q3）。
- `docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md` §4 📌（S14）。
- `docs/vnext/ONEBRAIN_ARCHITECTURE_2026-10-31.md` §11 📌（S15）。
- `docs/vnext/ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md` §3 📌（S9）。
- `docs/BACKLOG.md` `P5-CHIP-KIND-NAMES` 📌（S6）。
- 未落標（只在本表登記，原檔不改）：S13（Phase 5 線框）、S18（d25 HTML）、S19（MODEL_EFFORT_POLICY）。
