# Phase 1 Supersede Map（取代關係、過期指令、清理與 #970 處置）

- **狀態**：正式／現行
- **日期**：2026-10-29　**基準**：PR base＝main `978ecedc`；本分支 HEAD `55739129`（＝`978ecedc`＋PR #970 commit `06a7a3e5`）；clone 為 shallow（2026-10-23 以前 git 歷史查不到）
- **決策來源**：「舊記錄／規格整理分 A／B／C／D」「被取代者明確標 `SUPERSEDED BY <new DEC>`」「不要為了乾淨破壞 audit trail」「#970 盤點後決定」＝**客戶 2026-10-29（DEC-109 一、二十八，逐字）**；各條目的取代判讀、#970 處置（R11）、刪除清單＝**AI 總管內部決定（DEC-110）**。
- **上位**：`CLAUDE.md` > `PROCESS.md` > `PROJECT_RULES.md`（第 25 節 SSOT 位階）＋`docs/governance/*` > 最新有效 DEC > 本檔。
- **慣例**：舊條文**不刪**；標記＝條頭 📌「SUPERSEDED BY …」或「部分取代 BY …」＋「有意識的政策變更，不是漏刪」＋日期＋決策者＋兩邊理由（詳見 `docs/DECISIONS.md` 各條）。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：取代判讀以單組調查 Inv-5 為底＋獨立稽核組勘誤（已併入）；撰寫組逐條回讀 DECISIONS 原文核對出處，**仍未經第二組驗證**；程式碼內客戶裁示盤點（§6）為 grep，**非窮舉**。

---

## §1 位階（摘要；全文 `PROJECT_RULES.md` 第 25 節）

- **規範軸**：`CLAUDE.md`（§-2 > §-1.5 > §-1 > §0～§8）> `PROCESS.md` > `PROJECT_RULES.md`＋`docs/governance` > 最新有效 DEC（客戶 DEC > AI 總管內部 DEC）> 正式契約／Visual SSOT（Phase 1 新文件＋A／B／C 規格＋Digest 契約）> `docs/PROJECT_STATE.md` > `docs/BACKLOG.md` > `docs/HANDOFF.md`（索引）> historical／superseded。
- **事實軸**：GitHub 實況 > code／tests > 正式文件 > HANDOFF > PROJECT_STATE > AI 記憶 > 聊天。

## §2 Supersede 表

| # | 條目 | 衝突點 | 標記 | DECISIONS 落標 |
|---|---|---|---|---|
| 1 | DEC-017（IA v2 五頁＋鐵律） | IA 已被 DEC-092 Q6／DEC-097 四頁取代；鐵律 4「空狀態三要素」的**呈現位置**與預設下沉衝突 | IA：SUPERSEDED BY DEC-097；鐵律 4 呈現：部分取代 BY DEC-109（內容保留；DEC-109 七明確點名）；葉1 ②「兩套刻度常駐非摺疊」：**維持有效**（DEC-109 未點名），改否＝Phase 6 線框待客戶拍板（契約 §22 W7） | ✅ 條頭 📌 |
| 2 | DEC-018（舊 7 頁籤第一排、新版走側欄） | DEC-097(2)／DEC-098 已預設四頁、舊版走 `?legacy=1` | SUPERSEDED BY DEC-097（DEC-020 不變） | ✅ |
| 3 | DEC-021（寫入功能在「💼 我的持股 › 組合設定」） | DEC-083 Q1 改「👤 我的」為唯一設定入口；CRUD 移 P2（`ME-P2`） | 部分取代 BY DEC-083（位置；INFERENCE，客戶可推翻） | ✅ |
| 4 | DEC-071 第 4 點（導航改名、候選非 final）／第 6 點（保留「大盤」字樣） | 四個標籤已由 DEC-091 §二／DEC-097 逐字定案為「📊 市場」 | 第 4 點：SUPERSEDED BY DEC-092／097；第 6 點：部分取代（導航標籤；頁內「大盤合理區間」等用語仍有效；INFERENCE，客戶可推翻） | ✅ |
| 5 | DEC-072（📊 大盤／🎯 標的／⚡ 行動／🛡️ 持股＋輔助入口） | 已被 DEC-091／092 四頁取代 | SUPERSEDED BY DEC-092（頁面結構）；「底層能力完整，前台流程極簡」原則**仍有效** | ✅ |
| 6 | DEC-073（Model／Effort Gate） | 正文已寫被 DEC-084 部分取代，條頭與 §5 未標 | 部分取代 BY DEC-084（「高於所需不需降級」一句） | ✅ 條頭＋§5 |
| 7 | DEC-076 §6（⚡ 行動、🩺 資料中心、「憑什麼」作為獨立頁） | DEC-091 §二 改為各頁能力 | 部分取代 BY DEC-092；§4.1、§7 漸進揭露、§8 語意界線**仍有效** | ✅ |
| 8 | DEC-081 Q1／Q4 分流目的地（⚡ 行動、🩺 資料中心、🛡️ 持股） | 頁面 IA 已改四頁 | 部分取代 BY DEC-092；Q2-1 結論句**內容**仍有效，**位置**依 DEC-109（第一屏）；Q2-2 措辭逐字仍有效 | ✅ |
| 9 | DEC-083 Q1「側欄新增獨立 👤 我的」 | 現為 nav4 頁 | 措辭部分取代 BY DEC-097；「唯一設定入口」與 E 段（Google 側欄暫時保留）**仍有效** → 兩入口並存（R14） | ✅ |
| 10 | DEC-091 §四「市場狀態：🟢偏多／🟡中性／🔴偏空／⬜無法判定」 | DEC-105 2A「不得映射成偏多／中性／偏空」 | 部分取代 BY DEC-105（同一取代亦適用 A 規格 §4.1.1 表格與 `d25_wireframes/index.html` 圖例與 `market.html` 首屏圖例；**HTML 不改**，A 規格加註） | ✅ |
| 11 | DEC-091(d)／§九「One AI Brain 固定五段輸出」＋A 規格 §5＋`ai_summary.html` | DEC-109 二十一新輸出格式（市場一句／持股一句／標的機會一句／主要風險 1～3／本期行動 ≤3） | 呈現格式部分取代 BY DEC-109（R12）；分類資料保留；經 DEC-092 設計核准承接者一併 | ✅ DEC-091 條頭＋A 規格 §5 加註 |
| 12 | DEC-091 §一「禁止：大量三要素文字卡＋工程說明＋資料來源＋門檻＋診斷全部同層」 vs 2026-09-24／09-25 程式碼註解裁示「三要素要在卡面上看得到」「卡面三列短句」 | **兩者有張力且從未調和**（前者禁三要素文字同層外露，後者要求三要素上卡面） | DEC-109「資訊保留、預設下沉」**同時調和兩者**：三要素內容保留（滿足 09-24／09-25 的「不得消失、不得只剩 hover」）、位置下沉到 L3（滿足 DEC-091 §一 禁令）。09-24／09-25 的**位置**部分取代 BY DEC-109 | ✅ DEC-109 記載；09-24／09-25 補登為歷史條目 |
| 13 | DEC-099（NAV-1 過渡切換方案 A） | 已由 DEC-107／PR #968 執行完畢 | 標「已執行完畢」（不算 superseded） | ✅ |
| 14 | DEC-105 1A（結論句放在 Hero 與 ⚡ 之間） | 新契約要求第一屏 1 句主要判讀 | 位置部分取代 BY DEC-109（相對順序可維持，但須進第一屏；客戶原文出處＝同日前序指示「今日結論必須在第一屏可見」、DEC-108 ①）；2A、3A、第 4 點**仍有效**（第 4 點指路句 chip 化與否＝Phase 4 線框待拍板，契約 §22 W2） | ✅ |
| 15 | DEC-107 1A 版面順序／UIT 線框「▾ 選股條件（預設展開）」／4A 候選表全表外露 | Top-N First、候選提前 | **4A 候選表全表外露**：部分取代 BY DEC-109（十二 Top-N First 明確點名）。**選股條件預設展開、1A 頁面順序**：**維持有效**（DEC-109 未點名；客戶核准線框裁示，DEC-108 記「改此點須客戶明確回覆」）→ Phase 5 線框待客戶拍板（契約 §22 W4、W5；R3 總管 2026-10-29 改判）；DEC-107 資料、操作、語意邊界**仍有效** | ✅ |
| 16 | DEC-108（十項視覺原則＋凍結＋線框待核准） | 客戶 DEC-109 一：⛔ 依 #970／DEC-108 往下施工；#970 只作歷史輸入 | 部分取代 BY DEC-109：十項原則**仍有效**（由契約具體化；③ 讀為主圖外露但縮小，R2）；線框 5 題撤回；凍結解除條件改為「Phase 1 契約合併後依 Phase 2→7 推進，每個 UI phase 過 Visual Fidelity Gate」 | ✅ |
| 17 | 客戶 2026-09-24「三要素要在卡面上看得到」（`page_today.py` 約 L2933） | 與預設下沉直接衝突 | 部分取代 BY DEC-109（只換位置，內容不刪） | ✅ 補登 |
| 18 | 客戶 2026-09-25「v2 卡面三列短句」（`page_find.py` 約 L769；`page_hold`／`page_inspect`／`page_why` 同構） | 第一屏列數與 Visual Budget 衝突 | 列數：部分取代 BY DEC-109；K1「卡面句須為 Note 原文子字串」**仍有效** | ✅ 補登 |
| 19 | 客戶 2026-09-25「⛔ 不得只剩 hover」（`page_find.py` 約 L774／L2098／L2134） | 不衝突 | **仍有效**，升格寫進契約並延伸到手機（必須可點開） | ✅ 補登 |
| 20 | 客戶 2026-09-25「16 燈卡三列出處收進 ▸ 詳細」（`page_today.py` 約 L3014）、「(b) 純 CSS 開關」（約 L3019） | 機制同向；標籤字樣 | 機制與「▸ 詳細」字樣**仍有效**（`markup.FOLD_SUMMARY_TEXT` 註解自陳「客戶核可線框逐字『▸ 詳細』」）；DEC-109 五的新字樣只明確點名主圖下方 → 卡片摺疊換字與否＝各頁線框待客戶拍板（契約 §22 W3；R7 總管 2026-10-29 改判） | ✅ 補登 |
| 21 | PR #970 線框草稿 A.4／Q2「大圖只在 L2」「首屏只 sparkline」、Q2-B「首屏完全不放圖」 | 與「1 Primary Visual 在第一屏、主圖外露 compact」衝突 | SUPERSEDED BY DEC-109（R2）；5 題撤回 | （草稿已移除，見 §4） |
| 22 | PR #970 線框 A.7「🟢偏多／🟡中性／🔴偏空」 | 違 DEC-105 2A；🔴 重用為失敗態以外 | 不採用 | — |
| 23 | PR #970 線框 B.1 第一屏 4 tile＋3 風險 chip＋5 桶 chip＋需處理 chip＋5 mini 圖 | 超出 Visual Budget（3～5） | 不採用；以契約 §2 為準 | — |
| 24 | PR #970 線框 B.3 ② 價格資料時間移頁首 chip | 違 DEC-102 Q3「沿用 E17」 | 更正回 E17（契約 §16） | — |
| 25 | `CLAUDE.md` §-1.5.D v3 §00「固定 3 欄自適應網格」 vs KPI 首列 4 格 | 憲法層級，⛔ 以 DEC 覆寫 | **不改 CLAUDE.md**；R4 讀法（卡片網格 ≤3、KPI 首列 ≤4、手機 2×2），相容理由見契約 §15 | —（讀法） |
| 26 | A 規格 §2.5「`src/ui_v2/tokens.py` 是視覺 SSOT」 vs DEC-092 核准 mockup | 兩來源色值不同 | R15：blueprint＝驗收基準、tokens＝實作來源，衝突 blueprint 為準；**tokens 內客戶裁示色值維持有效**，改否＝Phase 3 草稿待客戶拍板（契約 §14.2、§22 W1） | — |
| 27 | `PROJECT_RULES.md` §11「新 UI 另讀 `VNEXT_PRODUCT_BLUEPRINT.md`」 | Blueprint 已非新 UI 現行 SSOT | 刪除線＋現行指向本 phase 契約 | ✅ PROJECT_RULES |
| 28 | `PROJECT_RULES.md` §19.11「衝突時以較嚴者為準」 | 呈現上「較嚴」無定義 | 補呈現讀法（資料／投資／安全照舊取嚴；呈現以 Visual SSOT 為準） | ✅ PROJECT_RULES |
| 29 | `PROCESS.md` §1「每次任務只讀 STATE.md」 vs `PROJECT_RULES.md` §15 五檔讀序 | 上位憲法層已過期指令 | **本 phase 不改 `PROCESS.md`**；維持 `CV1-DR-04` 待裁示；契約／PROJECT_RULES 第 25 節註明 | —（登記） |
| — | 仍有效、與新契約同向 | DEC-091 §一（三層資訊）、DEC-092 Q2／Q3／Q5、DEC-097、DEC-101／102、DEC-085／`PROJECT_RULES.md` §19.9（呈現與決策邏輯分離） | 仍有效 | — |

## §3 過期 active instructions 與本 PR 處置（客戶 DEC-109 二十八 B）

| 位置 | 問題（FACT） | 本 PR 處置 |
|---|---|---|
| `docs/HANDOFF.md` Resume Checkpoint | main SHA 寫 `3dad82e0`（實際 `978ecedc`）；stop point「停在 UI-T 線框」已過期（#968 已合併）；next action 三處矛盾（表格 UI-T／補註 UI-H／#970 等線框）；#970 next action 刪除線配對壞掉（「建議下一步＝UI-T…」未被劃掉） | **重寫成索引**（新節置頂）；舊表保留於下方標 historical；修正壞掉的刪除線配對 |
| `docs/HANDOFF.md` L62「DEC-085 段仍是唯一現行短版標記」、L68 AB-4r「待 PR」（實際 #955 已合併）、L108–302 多層「現行短版」、§1–§6 2026-10-22 快照 | 歷史段落誤導 | 由新索引宣告「下方全部 historical」；不刪 |
| `docs/PROJECT_STATE.md` 檔頭量測 main `08272e5`；§2「目前階段＝vNext 1.0、1.0-B4 未開始」；§24「DEC-017 五頁仍為現行實作依據」；§43／§44 Stage B／DEC-089 六向未標被取代；§47 #970 線框「待客戶核准」 | 過期 current state | 加刪除線＋現行指向；新增 §48 |
| `docs/BACKLOG.md` `VN1-MT-NAV`／`VN1-MT-HOME`／`VN1-MT-IA`、`BP-DR-01` | 仍標 blocked-on-customer，實際已被 DEC-081／091／092／097 回答 | 標 superseded（Gate 題已答；剩客戶實機驗收者另指） |
| `docs/BACKLOG.md` `NEWUI-STAGE-D2-SHELL-IMPL` 前段「PR 待開」 | 已合併 #944 | 加註狀態更正 |
| `docs/BACKLOG.md` `NAV1-DEC097-REQS` 前段「待客戶裁示／未合併」 | 已合併 #957 | 加註狀態更正 |
| `docs/BACKLOG.md` `NEWUI-STAGE-D-UNSCHEDULED`、`NEWUI-STAGE-D3`～`D11` | 已被 D25 PLAN／DEC-092 取代 | 標 superseded |
| `docs/BACKLOG.md` §F「Freeze 2026-10-23 交接入口」 | 已過期 | 標 historical |
| `docs/BACKLOG.md` `UI-CORRECTION-WIREFRAME`、`UI-VISUAL-PAUSE-DEC108`（#970 帶入） | DEC-109 取代 | 標 superseded by DEC-109 |
| `docs/BACKLOG.md` ID 前綴撞名 `UIM-*`（舊 UI 移植 vs UI-M P2） | 混淆 | 登記 `P1R-UIM-PREFIX-COLLISION`（P2）；新 ID 一律用 `P1R-` |
| `PROJECT_RULES.md` §11 Blueprint 必讀 | 過期指向 | 刪除線＋現行 |
| `PROCESS.md` §1 只讀 STATE.md | 上位層過期 | 不改（`CV1-DR-04`） |

## §4 清理 A／B／C／D 結果（R1，客戶定義 DEC-109 二十八）

| 類 | 客戶定義 | 本 phase 結果 |
|---|---|---|
| **A** 正式歷史 Decision | 保留；若已被新規格取代 → 明確標 `SUPERSEDED BY <new DEC>` | §2 表全部落標於 `docs/DECISIONS.md`；0 刪除 |
| **B** 過期 active instructions | 更新／清除 HANDOFF 過時 next action、PROJECT_STATE 過時 current state、BACKLOG duplicate／superseded items | §3 表全部處置（刪除線＋現行，不刪原文） |
| **C** 未合併草稿 | 例如 #970：close superseded／重做／吸收部分有效內容 | #970 → §5（R11） |
| **D** 可刪文件／assets | 只有在：無正式引用、無 audit 唯一價值、已被新 SSOT 完整吸收、不影響 tests／build 時才刪 | 只刪 #970 帶入本分支的線框檔＋15 png（§5）；其餘 D 類候選**本 phase 不刪不改**，登 BACKLOG `P1R-ROOT-LEGACY-DOCS`（P2） |

### 4.1 刪除 vs 保留清單

**刪除（自本分支移除；從未進 main；稽核出處＝PR #970 commit `06a7a3e5`）**：
- `docs/vnext/NEWUI_D25_UI_CORRECTION_WIREFRAME_2026-10-29.md`
- `docs/vnext/ui_correction_assets/`（15 張 png：`mock_{market,target,holdings}_{1440,390}.png`、`now_{market,target,hold}_{1440,390,390_tall}.png`）

刪除理由（四條件逐一）：(1) **無正式引用**——指向它的 DECISIONS／BACKLOG／PROJECT_STATE／HANDOFF 文字均已就地改註「已移除，出處 PR #970 commit `06a7a3e5`」；(2) **無 audit 唯一價值**——全文與截圖永久保存在 GitHub commit `06a7a3e5`（PR #970）；(3) **已被新 SSOT 吸收**——§C 偏差量測→`VISUAL_GAP_AUDIT_2026-10-29.md`（已載入狀態，取代冷啟動量測）、§D 能力守恆→契約 §17、§E 順序→Migration Plan、A.5 工程字樣→契約 §18、A.8 token→契約 §14.2；(4) **不影響 tests／build**——撰寫組 `grep -rn` tests 0 引用（`tests/test_sec_s3_batch_s3.py` 只掃 tracked `*.md`，刪檔不致失敗）。

**保留（不刪不改）**：其餘全部，含 `STATE.md`、`PLAN_T3.md`、`ARCHIVED_FEATURES.md`（root 與 docs）、`MACRO_HEALTH_*`、`ring1_report.txt`、`scratchpad/*.md`（repo 內 4 份，有稽核價值）、`docs/vnext/d25_wireframes/*.html`（blueprint）、全部 DEC 原文。

**D 類候選（只登記，R17）**：根目錄 `HANDOFF_2026-08-15.md`（0 引用）、`PLAN_T1_T2.md`、`PLAN_T4.md`、`BATCH_A_DELIVERY.md`（只被前者引用）——「已被 STATE.md 吸收」未逐項驗證 → BACKLOG P2。

## §5 #970 處置（R11）

- **處置**：**關閉 #970（superseded）＋同分支 `ccr-6eace3b6-0gglrs` 開新 PR**（本 Phase 1 PR；一般 push、⛔ force；關閉與開 PR 由總管執行）。
- **吸收進新 SSOT 的有效部分**：DEC-108 客戶裁示（保留於 DECISIONS，標「部分取代 BY DEC-109」，並補登客戶逐字原文）；§C 偏差量測（由 Phase 1 已載入量測取代並引用）；§D 能力守恆表（契約 §17）；§E 順序（Migration Plan 吸收為 Phase 3→7）；A.5 工程字樣清單（契約 §18）；A.8 token 差異（契約 §14.2）。
- **不吸收（衝突或缺陷）**：A.4／Q2／Q2-B（R2）、A.7 偏多／中性／偏空（DEC-105 2A）、B.1 超出 Visual Budget、B.3 ② 價格時間移頁首（違 DEC-102 Q3）、§客戶待確認 5 題（撤回）、HANDOFF 壞掉的刪除線與過期 SHA（本 PR 修正）。
- **#970 不成為 production baseline**（客戶 DEC-109 一原文「不得直接把 #970 當新的 production baseline」）。
- 為何不選 A（直接關閉不吸收）：DEC-108 是真實客戶裁示，直接關閉會讓它在 main 消失（違 Context Loss Check A）。為何不選 C（rebase 改寫 #970）：#970 標題與描述是「線框待核准」，改寫同一 PR 會讓稽核軌跡混淆；同分支開新 PR 可同時保留 #970 原貌。

## §6 程式碼內客戶裁示盤點（2026-09-22～26；grep `src/ui/views`、`src/ui_v2`，**非窮舉**）及新地位

| 日期 | 出處（約 L，僅參考） | 內容要點 | 新地位 |
|---|---|---|---|
| 2026-09-22 | `src/ui_v2/page_today.py` 約 L125～L278（「裁示 B 覆寫線框 3/2/1」、U-1） | 今天頁密度階／卡數 | 舊今天頁（legacy 可達）；仍有效於該頁；新四頁依契約 |
| 2026-09-22 | `src/ui_v2/tokens.py` 約 L88、L134（CTA 主色 `#1f6feb`／light `#044cb6`） | 色值客戶拍板 | **仍有效**；R15 收斂時不得默默覆寫（契約 §14.2） |
| 2026-09-21 | `src/ui_v2/tokens.py`（`--sig-neutral`／`-bg`） | 色值客戶裁示 | 同上 |
| 2026-09-23 | `page_today.py` 約 L43、`page_why.py` 約 L59（D-3(a) `UI_EMPTY` 分三態）；`page_why.py` 約 L2535（D-4(a)）；`markup.py` 約 L351、L373、L388 | 狀態語意與卡 CSS | 狀態語意**仍有效**（Missing 契約同向）；CSS 細節依契約可演進 |
| 2026-09-24 | `page_today.py` 約 L2683／L2689（三張同版）、L2764／L2775（一次整頁卡化）、L2847（退回截尾）、**L2933（三要素要在卡面上看得到）**、L2977、L3300、L3384（一行→2～3 列）、L3611、L3788；`markup.py` 約 L267、L309 | 卡面形態 | **L2933 三要素位置：部分取代 BY DEC-109**（補登 DEC 歷史條目）；其餘卡面形態裁示屬 legacy 今天頁，新頁依契約；「不截尾、不改寫原文」精神**仍有效** |
| 2026-09-25 | `page_find.py` 約 L360、L769（裁示 2：三列短句）、**L774／L2098／L2134（不得只剩 hover）**、L2045；`page_hold.py` 約 L393、L4782；`page_inspect.py` 約 L301、L2566；`page_why.py` 約 L337、L2605；`page_today.py` 約 L3014、L3019、L3518；`markup.py` 約 L412、L586（「▸ 詳細」逐字）、L693、L697、L733；`src/ui_v2/blocks.py` 約 L1；`src/ui_v2/page_{find,hold,inspect,why}.py` 檔頭（裁示 1、3） | 三列短句、K1、不得只剩 hover、摺疊、登記處 | 三列上卡面：**部分取代 BY DEC-109**；K1、不得只剩 hover、摺疊機制：**仍有效**（補登 DEC 歷史條目）；摺疊標籤依 R7 |
| 2026-09-26 | `src/ui_v2/components.py` 約 L207、L248、L267、L272（徽章 #11）；`src/ui_v2/page_today.py` 約 L514、L528、L554；`page_hold.py` 約 L2880、L3016；`markup.py` 約 L713（a11y） | 徽章封閉集第 11 種、失敗≠沒結果、a11y | **仍有效**（BADGES 封閉集、R8 metadata chip 另族） |

- 程式碼註解引用的 `UI_COMPONENTS.md`、`wf_page_today.js`、`docs/v2/spec/UI_TOKENS.md` 等規格檔：撰寫組於本分支工作樹 `find` 0 命中（FACT，2026-10-29；`docs/v2/spec/` 只有 `S1-6_COMPLIANCE_COPY_GUIDE.md`）——這些 2026-09-2x 裁示的規格原文**不在本 repo**，只剩程式碼註解轉述；歷史分支是否仍有未查（shallow clone）。
- 補登：2026-09-24、2026-09-25 兩則已補登為 `docs/DECISIONS.md` 歷史條目（「補登，來源＝程式碼註解」），見 DEC-109 取代鏈。其餘日期只在本表登記。

## §7 總管改判（2026-10-29）：AI 總管讀法不得推翻客戶核准過的呈現

- **改判內容**：R3 由「DEC-107 選股條件改預設收合」改為「DEC-107『選股條件預設展開』**維持有效**；在 DEC-109 Visual Budget 下是否改為預設收合＋摘要 chip，列為 Phase 5（🎯 標的）線框草稿的一個待客戶拍板點（依草稿先行，本 phase 不另開 Gate、不改）」。
- **同原則複查**：凡「總管讀法改變客戶核准過的呈現」且 DEC-109 客戶原文沒有明確點名者，一律改為「維持＋列入該頁 phase 線框待拍板點」——結果見 Presentation Contract §22（W1～W7）；維持原判（客戶原文明確點名）者見 `docs/DECISIONS.md` DEC-110「同原則複查」。
- 本節與上方 §2 第 1、14、15、20、26 列已同步改寫（該等列為本 PR 內撰寫之文字，直接改寫，不另加刪除線）。
