# Phase 4 P4-3｜📊 市場頁正式 Visual Fidelity Gate 報告

- **日期**：2026-10-31｜**基準**：`origin/main` `228b9fa9`（含 P4-1 #984、P4-2 #985；撰寫時 `git fetch` 實查＝同一 SHA）｜分支 `ccr-c8ef17de-9tw7yt`（＝main）
- **依據**：`docs/governance/UI_VISUAL_FIDELITY_GATE.md`（A1～A11、V1～V11、§5 例外流程）；DEC-117／DEC-118（含送審題幹附錄）；線框 `docs/vnext/PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30.md` §10、§10.7～§10.8；契約 `PRESENTATION_CONTRACT_vNext_2026-10-29.md` §2／§3／Q1～Q12
- **本批性質**：docs＋量測腳本／截圖；`src/`、`tests/` **0 diff**（不改任何產品碼；判定過程發現的缺口只記為發現項 F1～F6）
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：
  1. **判定者＝本批執行 AI（非 P4-1／P4-2 實作組），但仍是單組**。Gate §4 要求「獨立 QA 組判定＋總管複驗（A1、A2、A10、A11、V7 與全部 ❌／🟡 項）」**尚未發生**；本報告＝供其複驗的**初判**。下列「量測值」皆為本批腳本實跑（FACT，可重現）；「判定」是把量測值套 Gate 條文（INFERENCE，單組）。
  2. 量測環境＝`tools/visual_fidelity/harness_app.py` **夾具**（L3 假資料；harness 的 `&cold=1` 仍由假 L3 提供位階「多頭」，BACKLOG `P1R-P4-HARNESS-COLD-NOT-TRUE`），Streamlit 1.59.2；floor 1.56.0 另以獨立 venv 量一份（§9）。**真資料態、真冷啟動、1.57～1.58、手機實機、Streamlit Cloud、Safari／Firefox 全部未驗。** 截圖上的數字是示意，不得引用為投資結論。
  3. 「CI 綠」本批只查到：`228b9fa9` 的 check-runs＝`Slow tests` success、`Fast checks` 撰寫時仍 `in_progress`；**請總管以 GitHub 實查為準**，Stage 完成須「CI 綠＋Gate PASS」。

---

## §0 結論先講

**Gate 判定：❌ FAIL（Stage 維持「未完成」）**（📌 **2026-10-31 獨立 QA 複驗更正（有意識的更新，不是漏刪；出處＝獨立 QA 複驗，AI 總管轉交；原文保留）**：獨立 QA 同意 ❌；成因重述見 §15）。依 Gate §2「合計規則」：A 或 V 任一 ❌＝不通過；🟡 ≥4 亦視為 ❌。本批兩條都成立。

| 類 | 內容 | 項數 |
|---|---|---|
| **(A) PASS** | A1、A2、A3、A7、A9；V1、V2、V4、V5、V6、V7、V8、V9、V10、V11 | **A 表 5 項＋V 表 9 項＝14 項** |
| **(B) 🟡 登記** | A4、A10、A11、V3（量化內部建議值偏離，源於客戶已核准結構；登 BACKLOG P2）＋已有 DEC 依據、**不計 🟡** 的例外 4 條（Q7 手機 Primary、DEC-118 手機 ⚡、report 態 36px、partial 態）| **4 項 🟡＋4 條例外** |
| **(C) ❌／需裁示** | **A5**（桌機全頁高 3061／blueprint 1517＝2.018× > 2×）、**A6**（手機 Primary 圖高 220 > 契約 ≤140，+57%）、~~**A8**（外露 >32 字非客戶原句 3 塊）~~ 📌 **2026-10-31 P4-4 更新（有意識的更新，不是漏刪；決策者 AI 總管〔v3 §03-1 內部自決〕；原文保留）**：A8 已於 P4-4 內部修正，loaded 態非客戶原句 >32 字 **0 塊**（見 §14）；**A5**、**A6** 仍待客戶裁示；🟡 累計 4 項觸發合計規則（不變） | **3 項 ❌＋1 條合計規則** |

(C) 項裡**需客戶判斷的 3 題**與**可內部修的項目**分開列於 §11；**本報告不自行裁決、不宣稱 Stage complete**。

---

## §1 量測方法與檔案

| 檔 | 內容 |
|---|---|
| `measure_p4_1.js`／`measure_p4_2.js`（沿用 p4_1、p4_2 腳本，未改） | L1 區塊順序／y／結論頂端（Q11）／頁首動作列；圖區順序／Primary／小倍數／摺疊標籤 → `_measure_p4_1.json`、`_measure_p4_2.json`（1.59.2）；`*_floor156.json`（1.56.0） |
| `measure_p4_3_gate.js`（**本批新增**，只量測） | A3 外露字數、A4 卡面字數／卡高、A5 同列卡高差、A8 外露 >32 字清單、A9／V9 Missing 符號、A10／A11（KPI 區塊高／單一元素占屏比／水平捲動）、V3 chip、V10 工程字樣、V11 `title=`、Q10 → `_measure_p4_3_gate.json`（1.59.2）、`_measure_p4_3_gate_floor156.json`（1.56.0） |
| `tools/visual_fidelity/measure_app.js`／`measure_mock.js` | 全頁高、blueprint contentH（`_measure_app_market*.json`；blueprint＝`mock_market_*.png`，contentH 市場 **1517（1440）／2480（390）**） |
| `compare_other_pages.js` | 其他頁與 `?legacy=1` 前後文字比對（§8）→ `_compare_other_pages.json` |
| 截圖（Gate §3；每張 <300KB） | `app_market_<loaded\|cold\|report\|partial>_<1440\|390>.png`（第一屏）、`…_tall_x0.4.png`／`_x0.5.png`（全頁，縮放＋64 色量化）、`mock_market_<1440\|390>.png`（blueprint 並排用）、`zone_loaded_<1440\|390>_zone.png`（圖區） |

量法重點：第一屏可用高＝viewport 高 − 手機底部固定導覽 53px（手機 791、桌機 900）；y 一律頁面絕對座標；blueprint 分母＝契約 Q12 的 mockup contentH。**全頁高＝scroll 容器 `scrollHeight`**（與 Phase 1 baseline、線框 §2.4 同量法）。

---

## §2 客戶 11 項（A1～A11；loaded 為判定基準，cold／report／partial 為補充）

| # | 判 | 證據（FACT 量測） | 依據 |
|---|---|---|---|
| **A1 第一屏結構** | ✅ | 順序＝頁首 → 更新 CTA → 今日結論 → 3 核心狀態 → ⚡ → AI／資料狀態 → Primary（DOM 實量 4 態×2 viewport 皆同；`TestC1Order::test_c1_1_*`）。桌機五問①位階②3 tile＋⚡③圖 A header＋圖上緣（header y760、圖本體約 y850 起、第一屏 900）④⚡ y622～713⑤🚀 y192 全可見。手機：①②（位階｜水位）⑤（🚀 y351）可見；③④依 DEC-117 Q7／DEC-118 例外（見 §4）。| Gate A1 就地加註（DEC-117）；§5 第 2 列；contract §3 豁免 |
| **A2 Primary 突出** | ~~✅~~ → 📌 **2026-10-31 獨立 QA 複驗更正（有意識的更新，不是漏刪；出處＝獨立 QA 複驗，AI 總管轉交；原文保留）**：🟡（report 態桌機圖本體 y≈916＞900，依契約 B1「第一屏至少露圖上緣」未達；loaded 基準態仍 ✅；見 §15） | 桌機 loaded：恰 1 個 Primary（圖 A，容器 y760～1160：header＋chips＋1 句 y760～868，圖本體 y868～1088；第一屏 900 內露 header 全部＋圖上緣 **約 32px**＝Gate 下限）；⚠️ **report（乾淨報告）態桌機**容器 y830、圖本體 y938＞900：header 露、**圖上緣不在第一屏**（見 §4／§10 觀察 O1，Gate 基準態為 loaded 故不改判）；Secondary 國際 small multiples 單格 ≤85px、圖 D／圖 C 為表／一行，無同權重大圖並列。手機：Q7 三條件皆成立（§4），**不計 🟡**。| Gate A2 就地加註；§5 第 2 列 |
| **A3 圖文比例** | ✅ | 外露可見字數 loaded 桌機 1158／blueprint 1138＝**1.02×**、手機 1174／1108＝**1.06×**（≤1.3）；blueprint 有主圖處實作有 Primary（loaded）／同高 220 槽＋誠實 placeholder（cold）。| Gate A3 |
| **A4 卡片密度** | 🟡 | 桌機三主卡高 156／156／272，均高 195／blueprint 277＝**0.70×** ✅；**手機**三卡 178／204／250 均高 211／blueprint 162＝**1.30×**（1.2～1.5＝🟡）；卡面字數：位階 26、水位 54 ✅，**今日主要風險 98（桌機）／114（手機）>60**（1 張超字數＝🟡）。超標原因＝C6-3／C2 要求外露逐字保留的退化／指路句（客戶 DEC-117 Q6／DEC-105 第 4 點），不是新增內容。| Gate A4；DEC-117 Q2／Q6 |
| **A5 空白比例** | ~~❌~~ → 📌 **2026-10-31 P4-5 更新（有意識的更新，不是漏刪；決策者 **客戶**（DEC-119）；原文保留）**：**客戶接受之已知輕微偏差**（DEC-119 題 2=A；Gate §8 登記；不計 ❌；不得據此展開頁尾結構重構；見 §16） | **全頁高 loaded 桌機 3061／1517＝2.018×（>2× 判 ❌，超出 27px）**；手機 3747／2480＝1.51×（🟡）；cold 桌 2573／1517＝1.70×（🟡）、手 3029／2480＝1.22×（✅）。同列卡高差：桌機位階／水位 156 vs 風險 272＝**差 116px（43%，🟡 帶）**；手機位階｜水位 178 vs 204（差 26px，13%）。>120px 空洞：無（桌機兩張短卡下方空白 116px，<120）。cold 桌機 Primary 220px 空槽屬 DEC-115 D6=B，不計。⚠️ 邊界案例：以「主內容底（頁尾 y≈2901）」而非 scrollHeight 當分子約 1.9×（🟡）——Gate 未規定量法，本報告沿用 Phase 1 baseline 量法（scrollHeight）故判 ❌；11 個 L2 具名摺疊列＋頁尾（y2231～2901＝670px）是 DEC-117 要求「原樣保留」的結構，扣掉後 2391／1517＝1.58×（仍 🟡）。| Gate A5／契約 Q12 |
| **A6 圖表大小** | ~~❌~~ → 📌 **2026-10-31 P4-5 更新（有意識的更新，不是漏刪；決策者 **客戶**（DEC-119）；原文保留）**：**✅（客戶例外）**：手機 Primary 維持約 220px 為 DEC-119 題 1=A 對契約 Q3 ≤140px 內部建議值的明確例外（Gate §8 登記）；圖例 5 項已可見（F1 已修，見 §16） | 桌機 Primary 圖高 **220**（≤220 ✅）、小倍數單格 ≤85（≤96 ✅）。**手機 Primary 圖高 220，契約 Q3 上限 ≤140＝+57%（>30% 判 ❌）**；契約 §19 註明「手機 Primary 依 Q7 例外，**Q3 尺寸上限照舊**」。P4-2 對兩 viewport 都用 220（`compact.SLOT_HEIGHT_MAX_PX`），PR_NOTES 未標示此偏離。| Gate A6；契約 Q3 |
| **A7 Top-N** | ✅ | 風險 tile 縮短行 ≤3；圖 D 表 5 桶（`HERO_RISK_MAX_ITEMS` 只切片）；指路到「指標明細（16 項）」；`hero_risk_items` 維持純顯示切片（N6 守衛）。| Gate A7；contract §10 |
| **A8 詳細文字下沉** | ~~❌（邊界）~~ → 📌 **2026-10-31 P4-4 更新（有意識的更新，不是漏刪；決策者 AI 總管〔v3 §03-1 內部自決〕；原文保留）**：✅（P4-4 重量測：loaded 非客戶原句 >32 字 0 塊，兩種計法皆 0；見 §14） | 外露層 >32 字且**非客戶原句**共 **3 塊**（loaded）：① 狀態列「本次使用中尚未按過更新｜資料日：…（加權指數，來源：市場評估輸入）」42 字；② AI／資料狀態行「🤖 AI 投資總結：⬜ 尚未提供 ⬜ 資料狀態：尚未彙總（逐來源結果見頁首更新鈕下方的更新報告）」44 字；③ 圖 C 一行 `CHART_C_EMPTY`「需先核准：EPS 資料來源…不畫任何圖形、區間或指數位置。」50 字。今日結論句 93 字＝客戶原句（DEC-081 Q2-1）豁免。Gate：1～2 處 🟡、**≥3 處 ❌**。⚠️ 若總管判 ① 屬 metadata 狀態列不計，則為 2 處＝🟡；本報告依字面計數判 ❌，交複驗。下沉清單（線框 §3.6）全在 L3：`TestC80` 守衛綠。| Gate A8；contract Q8 |
| **A9 Missing placeholder** | ✅ | cold：缺值全為 ⬜ chip／灰字（`⬜ 尚未載入，請按更新`、`⬜ 尚未核准／無法判定`、`⬜ 尚未定義`、`⬜ 資料日未提供`）；紅色錯誤 0（`errs`＝0）；partial 的 1 個紅框是真錯誤（可重現的取不到來源）；0／中性／HOLD／安全冒充 0 次（`test_n2_cold_first_screen_has_no_red_and_no_zero_standins`）。圖 D「是否惡化：⬜ 尚未定義」只在 header 寫一次（P1R-P4-CHART-D-COLUMN 已處理）。| Gate A9＋DEC-115 D6=B |
| **A10 主 CTA／行動首屏** | 🟡（📌 **2026-10-31 獨立 QA 複驗更正（有意識的更新，不是漏刪；出處＝獨立 QA 複驗，AI 總管轉交；原文保留）**：數字以 P4-4 後實量為準：手機結論頂端 loaded +269／cold +269／report +356／partial +292，仍 >260 ⇒ 🟡；桌機 report +195 ≤200 ⇒ 桌機不超標；下方原文數字為 P4-3 當時值，保留）| 🚀 更新：桌機 y192、手機 y351（兩 viewport 第一屏內）✅。Q11 結論句頂端（相對 H2）：桌機 loaded **+147**／cold +147／partial +170（≤+200 ✅；report **+218**，>200 by 18）；**手機 loaded +292／cold +269／report +379／partial +314，皆 >+260**（loaded 超 32px＝+12%），但手機結論句四態皆在第一屏內。Q11 是內部建議值（契約 §19／DEC-110），超標源於客戶 DEC-117 Q1／Q5 把更新 CTA（動作列實高桌機 128／手機 106px，`P1R-P4-HEADER-FORM-HEIGHT`）放在結論之前。| Gate A10；契約 Q11；DEC-117 Q1／Q5 |
| **A11 手機不被塞滿** | 🟡（📌 **2026-10-31 獨立 QA 複驗更正（有意識的更新，不是漏刪；出處＝獨立 QA 複驗，AI 總管轉交；原文保留）**：理由改為「手機 KPI 區塊 loaded 461／cold 394 > ≤340」；~~引「圖 D 723px＝86% 屏高」為理由~~ 已移除——圖 D 在第一屏外，改列獨立觀察，見 §15；下方原文保留）| 水平捲動：0（四態×2 viewport，含 floor 1.56）✅；第一屏單一元素最高 250px（風險 tile，30% 屏高）✅（partial 真錯誤區塊 336px＝40%）。**KPI 區塊（三張 tile 區）高 loaded 462px／cold 394px／report 461px，契約 Q2 ≤340＝+36%／+16%**；全頁最高單一元素＝圖 D 容器 **723px＝86% 屏高**（在第一屏外；🟡 帶 50%～100%）。2＋1 排法本身是客戶裁示（DEC-117 Q1），340 是 2×2 mockup 值。| Gate A11；契約 Q2；DEC-117 Q1 |

---

## §3 補充 V1～V11（DEC-110 內部）

| # | 判 | 證據 |
|---|---|---|
| V1 Primary 數量 | ✅ | 恰 1（圖 A；`TestZone`／`TestC41`） |
| V2 Secondary 數量 | ✅ | 3（國際 small multiples 一組、圖 D、圖 C；上限 ≤3，已達上限） |
| V3 第一屏核心數字／status chip | ~~🟡~~ → 📌 **2026-10-31 獨立 QA 複驗更正（有意識的更新，不是漏刪；出處＝獨立 QA 複驗，AI 總管轉交；原文保留）**：✅（契約 B3：圖 header 的 chip 歸 §4 不計入 V3；第一屏判斷用 chip 計 5 ≤5）| 桌機第一屏「判斷用」計：位階值、水位 `⬜ 尚未核准／無法判定`、今日主要風險、⚡ 計數（4）＋圖 A 語意護欄 `⬜ 尚未定義`（5）＋AI 行 `⬜ 尚未提供`（6）＝**6（🟡 帶 6～7）**；若不把 AI 行計入則 5（✅）。計法交複驗；metadata chip（資料日／窗口／可讀性）依 B3 不計。 |
| V4 主要判讀句 | ✅ | 1（今日結論句）；圖 A 的 1 句白話說明屬各卡 1 句摘要，不計（B4） |
| V5 禁止清單 | ✅ | 0 項命中：第一屏僅 1 張大圖；0 donut／pie；無 Report／Chart Wall |
| V6 第一屏五問 | ✅ | 桌機五問全可見；手機 ③④ 依客戶例外（contract §3 豁免、§5 第 2 列） |
| V7 三層 | ✅ | 見 §5 |
| V8 chip 文字化 | ✅ | 每個色塊／圖示皆有文字；loaded／cold 🔴 0 次（符號集合只有 ⬜、⚠）；風險 tile 燈色皆帶桶名＋燈名＋方向 |
| V9 Missing 符號 | ✅（附註） | 外露層符號集合只有 `⬜`（＋⚠ 為圖 D 標題）；同一狀態沒有兩種符號。⚠️ 觀察（不判 ❌）：cold 的 ⚡ bar 值寫「尚未載入」無 ⬜，tile 同狀態寫 `⬜ 尚未載入，請按更新`——bar 值非 metadata chip，不在 V9 射程；登為 P2 文字一致性備註 |
| V10 工程字樣 | ✅ | 外露層命中 `Gate`×2、`C2b`×2＝皆在客戶逐字句「風險上限：獨立顯示待 C2b＋RC-VISIBILITY Gate」內（DEC-081 Q2-2，客戶自訂措辭例外）；其餘清單（SSOT／digest／expander／widget／session／L0～L5／warroom…）0 |
| V11 手機無 hover 依賴 | ✅ | 外露層帶資訊的 `title=` 0 個（只有 Vega 內建動作選單 `Click to view actions`，非資訊）；位階 tile 原 hover-only 出處已併入「🔍 查看依據」六欄（`test_c3_2_hover_only_regime_provenance_is_visible_text_in_the_basis`） |

**🟡 合計（loaded，扣除已有 DEC 依據的例外）＝ 4（A4、A10、A11、V3）→ 依合計規則視為 ❌。**

---

## §4 使用者點名項目逐項判定

| 項目 | 判 | 證據與依據 |
|---|---|---|
| **Q7 手機 Primary 例外**（Gate §8 第 1 條） | ✅ 條件成立，不計 🟡 | 三條件：(1) 手機第一屏優先序 結論 > 核心狀態 > ⚡ > Primary：DOM 與 y 皆照此序（loaded 結論 y427／位階｜水位 y537／⚡ y1016／Primary y1167）；(2) 為塞主圖擠出結論或核心狀態：**否**——四態結論句皆在第一屏內（loaded 427、cold 404、report 514、partial 449，可用高 791）；(3) Primary 緊接 L1 決策區、不被 L2／L3 插隊：AI 行→Primary 間距 **0px**（四態×2 viewport），圖區 4 容器間隔 16px、間無他物（`test_chart_zone_order_and_nothing_between`）。依 §5 第 2 列：不算偏離。 |
| **DEC-118 手機 ⚡ mobile exception**（Gate §8 第 2 條） | ✅ 條件 ①③ 成立；② 見下兩列 | ① ⚡ bar 緊接 3 核心狀態、中間無 L2／L3（`test_c1_10_alerts_bar_follows_the_three_tiles_with_nothing_in_between`，M26／M27）；③ DEC-117 Q7 三條件同上。手機 ⚡ 頂端 loaded y1016／cold y900／report y1102／partial y1485（皆在第一屏外，客戶知情＝DEC-118 送審附錄 A 缺點「手機要往下捲一下才看到 ⚡」）。 |
| **DEC-118 條件②：report（乾淨報告）態** | 🟡→已接受邊界（不計 🟡） | 手機 report：結論 y514～632 ✅；位階｜水位列 y624～828，標題與值在第一屏內，底部「🔍 查看依據」標題列約 **36～37px** 超出可用高 791（水位 header 頂 y778＋約 40）。Gate §8 條件②已明列此邊界為接受（QA 第二輪但書）。 |
| **DEC-118 條件②：partial（報告含真錯誤）態** | ✅（依但書） | 手機 partial：今日結論 y449～568 在第一屏、真錯誤區塊 y576 起緊接（336px，40% 屏高）；3 tile 下推（位階｜水位 y1006，風險 y1218）＝客戶知情接受（D1 缺點）。桌機 partial：結論 305～372、真錯誤 380～548、3 tile 604、⚡ 884（框底 976，部分出第一屏）、**Primary y1022 在第一屏外**——這是 D1 的桌機延伸後果，送審題幹只明寫「3 張狀態卡會被往下推」，Primary 在 partial 桌機被推出第一屏**未被明寫**；Gate 判定基準是 loaded，故僅登記為 **B 類觀察**。 |
| **桌機 Primary 只露上緣**（C1-8） | ✅ | loaded 桌機：Primary header＋chips＋1 句 y760～868、圖本體（vega）y868～1088，第一屏（900）露 header 全部＋圖上緣**僅約 32px**——剛好是 Gate A2／契約 B1「至少 header＋圖上緣」的下限（截圖 `app_market_loaded_1440.png` 可見 y 軸 20,000 刻度與線的頂端）。**report 態桌機**（使用者按過更新後的真實常見態）：Primary 容器 y830、圖本體 y938＞900 ⇒ **圖上緣不在第一屏**（只有 header 前段）；partial 桌機 y1022 整個出第一屏。cold y664 ✅（同高槽可見）。Gate 基準態為 loaded → A2 判 ✅；report／partial 態登為觀察 O1。 |
| **風險 tile 手機僅露 42px**（`P1R-P4-RISK-TILE-FIRST-SCREEN`） | 🟡（B 類，P2 已登） | loaded 手機風險 tile y749，可用高 791＝僅露 42px（標題）；cold y701（露 90px）。DEC-118 條件②只要求「結論＋位階｜水位列」，**風險 tile 不在其內** → 不違 DEC-118；但送審題 1 做法欄寫「第一屏維持『結論＋位階｜水位＋風險卡』」，與實量差距已登。手機五問④（⚡ 是否需行動）本身依 DEC-118 例外。 |
| **手機圖例被裁**（`P1R-P4-PRIMARY-LEGEND-MOBILE`） | **發現項 F1**（非 Gate 項） | 手機 390px 圖 A 圖例單行，5 項（MA120／MA200／MA5／MA60／加權指數收盤）DOM 皆在，**可見 ≈2 項**（`zone_loaded_390_zone.png`）；原生 `st.line_chart` 行為、P4-1 基底同。⚠️ DEC-117 C4-1 客戶明列「保留…圖例」，手機視覺上資訊被裁＝與核准條件有落差；修法屬內部（縮短 MA 系列名／圖例換行／折行 CSS 需不選圖內部，受 `test_c4_1_layout_css_never_selects_chart_internals` 約束）。 |
| **圖 D 手機 723px**（`P1R-P4-CHART-D-MOBILE-HEIGHT`） | 🟡（併入 A11） | 723px＝86% 屏高（不在第一屏）；表格兩欄、「方向」欄窄螢幕換行；表本身約 437px。再壓＝改核准的表格形式。 |
| **契約 Q11**（結論句頂端） | 見 A10 | 桌機 ✅（+147～+218，report +218 超 18）；手機 +269～+379 皆 >+260（內部建議值；需客戶判斷與否見 §11）。 |
| **手機 KPI 區塊 ≤340** | 見 A11 | 462／394／461（loaded／cold／report）＝+36%／+16%／+36%；2＋1（客戶 Q1）下三 tile 的卡高 178～250（含摺疊入口按鈕 ≈40px 與卡內距）。 |

---

## §5 V7 三層（逐頁寫出）

**📊 市場｜桌機 1440×900（loaded）**
- **第一眼（L1）**：「📊 市場」＋右上主 CTA「🚀 更新今日戰情」→ 今日結論句（位階：多頭；台股／國際趨勢：⬜ 尚未定義；指標危險度：黃…；風險上限：獨立顯示待 C2b＋RC-VISIBILITY Gate）→ 三張核心狀態（市場位階｜建議總持股水位 ⬜｜今日主要風險 3 行）→ ⚡ 需要處理 一行（1 紅·1 黃）→ AI／資料狀態 → 圖 A Primary header＋上緣。
- **第二眼（L2）**：圖 A 本體（原生圖＋MA 參考線＋y 軸＋圖例）、國際 small multiples（5 格、無數字）、圖 D 主要風險 5 桶表、圖 C 研究框架一行；其下 11 個 L2 具名摺疊（原樣保留，預設收合）。
- **第三層（L3）**：各 tile／⚡「🔍 查看依據」六欄、各圖「▸ 為什麼／來源／限制／去哪補」、「更新選項」、更新報告。

**📊 市場｜手機 390×844（loaded）**
- **第一眼**：標題＋CTA → 今日結論 → 位階｜水位並排（風險 tile 只露上緣 42px）。
- **第二眼**（往下捲）：今日主要風險 → ⚡ → AI 行 → 圖 A Primary（Q7 例外）→ 國際小倍數（2 欄）→ 圖 D → 圖 C。
- **第三層**：同桌機（全部收合）。

---

## §6 零資料語意證明 (a)～(g)（`git diff` 為據）

**範圍 1：P4-2＝`git diff 4c1546b5..HEAD`**（35 檔；非 docs 檔僅 `src/ui/views/_market_blocks.py`、`src/ui/views/page_market.py`、`src/ui_v2/compact.py`＋6 個測試檔）。**範圍 2：整個 Phase 4＝`git diff 7484c57b..HEAD`**（Phase 4 還原鏈基底）：非 docs／非 cron 資料快取檔＝`src/ui/views/{_market_blocks,_ui_kit,page_market}.py`、`src/ui_v2/compact.py`＋`PROJECT_RULES.md`（P4-1 的 docs 補註）＋測試檔；`data_cache/**` 變更皆為 cron bot commit（`aee09870`／`673eddc0`／`18664378`），與本批無關。

| 項 | 結果 | 實查 |
|---|---|---|
| (a) 新資料源 0 | ✅ | 兩範圍 `src/services`、`src/compute`、`src/data`、`shared/`、`src/config` 皆 **0 diff**；新增 import 僅 `shared.ia_nav`／`shared.market_conclusion`／`shared.ui_state`（既有 L0 常數）、`src.ui_v2.compact`、`_ui_kit.single_submit_form`、函式內 `MacroRefreshReport`（isinstance 用型別） |
| (b) schema 0 | ✅ | 無 pandera／schema 檔異動；`MarketRisks` 等資料結構未動 |
| (c) 公式／門檻／TTL 0 | ✅ | `src/ui` diff 內無 `rolling`／`mean`／`ewm`／`pct_change`／`fillna`／`ffill`／`ttl`／`cache_data`；唯一日期運算＝`datetime.strptime` 把既有 `as_of` 字串格式化成 chip 顯示值（解析失敗回 None、不猜日期，M29 必紅） |
| (d) Risk Cap 數字顯示 0 | ✅ | 水位 tile 只放 `WATER_VALUE`＋`RISK_CAP_PENDING_TEXT`（逐字）；diff 內無 `%`／數字上限；`test_n1_water_tile_has_no_number_and_verbatim_guards` |
| (e) 趨勢定義 0 | ✅ | `⬜ 尚未定義` 外露（圖 A、圖 B header 各一）；MA 是 `mkt_info` 既有純量畫成水平線；`test_c4_5_no_new_formula_in_the_chart_zone` |
| (f) Digest／Brain import 0 | ✅ | `test_layering_no_data_layer_and_no_digest_import`＋`TestScope`；diff 內 `digest|brain` 0 命中 |
| (g) `page_today.py`／`app.py`／`requirements.txt`／`markup.py`／`pytest.ini`／`.github` 0 diff | ✅ | 兩範圍皆 0（z60 指紋不動；`_ui_kit.single_submit_form` 只加參數 `options_note=None`，預設逐呼叫相同，P4-1 已守） |

**N5～N7**：N5（分層：`page_market`／`_market_blocks` 零 `src.data.*`、零 Digest／Brain；上列 0 diff）✅——`tests/test_c3_layering_guard.py`、`tests/test_batch_z60.py` 綠；N6（Top-N／收合不影響 Digest）✅——`hero_risk_items` 純顯示切片，Phase 2 不變性守衛綠；N7（新文案全稱詞登記）✅——`tests/test_views_no_unverified_universal_claims.py` 綠（P4-2 PR_NOTES：無新增全稱關鍵詞）。

**測試複跑（本批，HEAD `228b9fa9`）**：`pytest -q` 市場頁 8 檔（`test_p4_1_market_first_screen`、`test_p4_2_market_charts`、`test_page_market`、`test_uim_market_page`、`test_market_blocks`、`ui_v2/test_compact`、`test_p4_revert_chain`、`test_macro_v2_tab`）＋鏈守衛（`test_uim`／`test_nav1`／`test_xvext_revert_chain`）＋`test_c3_layering_guard`／`test_batch_z60`／`test_views_no_unverified_universal_claims`＝**978 passed、0 failed**。docs 同步（HANDOFF／BACKLOG／PROJECT_STATE／Gate §8／Plan §20.6／線框 §10.9）後，另跑 11 個會讀 docs 的測試檔（含 `test_p4_1`／`test_p4_2`／`ui_v2/test_compact`／`test_xv_asof`／`test_vn1_*`／`test_dec074_breadth_gate`／`test_p02`／`test_p04`／`test_p2_step1…`）＝**3811 passed、6 skipped、1 deselected、0 failed**。⚠️ 不是全量 Fast／slow lane（P4-2 PR_NOTES 記錄：Fast 35802＋slow 183 passed、1 個便攜守衛紅已修；以 PR CI 為準）。

---

## §7 線框 §10 全表最終狀態（每條 → 守衛測試／Gate 項）

> ✅＝守衛綠（含 mutation 必紅，見 §10.7／§10.8）；📏＝屬 Gate 量測，已於本報告判定；測試名依**現行**檔案（§10.7 內少數舊測試名已改名：`test_c1_5_mobile_two_plus_one_rule_is_scoped_and_hides_nothing`→`…_is_scoped`、C1-9 舊「真錯誤留收合區外」測試已被嚴格化＋D1 取代）。

| # | 最終 | 守衛（`tests/test_p4_1_market_first_screen.py`＝P41、`tests/test_p4_2_market_charts.py`＝P42）／Gate 項 |
|---|---|---|
| C1-1 順序 | ✅ | P41 `TestC1Order::test_c1_1_block_order_is_dec117_q5`、`…_order_holds_with_a_report`；Gate A1 |
| C1-2 結論句逐字 | ✅ | P41 `TestC1Structure::test_c1_2_*`；`test_uim_market_page::test_conclusion_sentence_and_expanders_are_identical_to_pre_uim` |
| C1-3 3 tile | ✅ | P41 `test_c1_3_*`；`test_market_blocks::TestStructure` |
| C1-4 頁首主 CTA | ✅＋📏 | P41 `test_c1_4_*`（3 條）；Gate A10（🟡，Q11 手機超標） |
| C1-5 手機 2＋1 | ✅＋📏 | P41 `test_c1_5_mobile_two_plus_one_rule_is_scoped`、`…_layout_css_declarations_are_whitelisted`、`…_whitelist_rejects_hiding_tricks`、`…_fold_contents_wrap_instead_of_overflowing`；Gate A11（🟡，KPI 區塊 462 vs ≤340） |
| C1-6 手機結論句第一屏 | 📏 ✅ | loaded／cold／report／partial 皆在第一屏（本報告 §4）；Q11 超標歸 A10 |
| C1-7 Primary 緊接 AI 行 | ✅ | P41 `test_c1_7_primary_follows_ai_line_with_nothing_in_between`；實量間距 0px |
| C1-8 桌機 Primary 第一屏 | 📏 ✅（只露上緣） | 本報告 §4；Gate A2 |
| C1-9 CTA→結論間無外露 | ✅ | P41 `test_c1_9_between_cta_and_conclusion_only_collapsed_report_expander`、`…_strict_nothing_exposed_between_cta_and_conclusion_in_any_state`、`TestD1Fallbacks::*` |
| C1-10 手機 ⚡（DEC-118） | ✅（例外成立） | P41 `test_c1_10_alerts_bar_follows_the_three_tiles_with_nothing_in_between`、`test_d1_partial_true_errors_are_exposed_directly_below_the_conclusion`；Gate §8 |
| C1-11 動作列實高 | 📏 | 桌機 106px（量測值，form 區塊）／手機 106px；PR_NOTES 記壓縮後 128／106（量法含 expander 標題列差異）；登 `P1R-P4-HEADER-FORM-HEIGHT` |
| C2 指路 | ✅ | P41 `TestC2Pointer`（3 條）；`test_uim_market_page::test_danger_card_demotion_is_signposted_from_hero_and_chart_d` |
| C3-1 圖四段摺疊 | ✅ | P42 `TestC31`（7 條）、`TestC8a::test_c8_a_say_is_verbatim_in_why_and_basis_verbatim_in_source` |
| C3-2 tile／⚡ 單一「🔍 查看依據」 | ✅ | P41 `TestC3Basis`（4 條） |
| C6-1／C6-2 風險縮短行／整句下沉 | ✅ | P41 `TestC6RiskTile::test_c6_1_*`、`test_c6_2_*` |
| C6-3 退化／護欄句外露逐字 | ✅ | P41 `test_c6_3_degenerate_and_guard_sentences_are_exposed_verbatim`、`…_cold_and_failed_on_the_page`、`…_other_true_errors_stay_outside_folds`、`TestInvariants::test_c6_3_alerts_failed_bar_is_red_with_reason_outside` |
| C6-4 coverage／C6-5 | ✅ | P41 `test_c6_4_*`、`test_c6_5_tile_never_adds_new_unevaluated_wording_and_chart_d_keeps_it_outside`；P42 `TestChartD::test_c6_5_*` |
| C4-1 Primary | ✅＋📏 | P42 `TestC41`（8 條）；Gate A6（桌機 ✅／**手機 ❌**）；**F1 手機圖例被裁** |
| C4-2／C4-3 小倍數 | ✅ | P42 `TestC42C43`（16 條）、`TestZone::test_c4_2_no_switcher_widget_is_called_by_the_market_page` |
| C4-4 L2 原樣 | ✅ | P42 `TestC44` |
| C4-5 趨勢定義 | ✅ | P42 `TestC45`（3 條） |
| C4-6 冷啟動 | ✅ | P42 `TestC46`、`test_c4_1_primary_cold_and_unreadable_keep_a_slot_not_a_missing_chart` |
| C8-0／C8-a | ✅ | P42 `TestC80`（5 條）、`TestC8a`（3 條） |
| C8-b／C8-c | ✅ | P41 `TestC8`（5 條） |
| N1～N3 | ✅ | P41 `TestInvariants::test_n1_*`／`test_n2_*`／`test_n3_*`（5 條） |
| N4 還原鏈 | ✅ | `tests/test_p4_revert_chain.py`（基底 `7484c57b`）；uim／nav1／xvext 鏈全綠 |
| N5～N7 | ✅ | 見 §6 |

---

## §8 其他三頁與 `?legacy=1`（前 `7484c57b`／後 HEAD 文字比對）

`compare_other_pages.js`：現行分支 harness（port 8571，HEAD `228b9fa9`）vs **Phase 4 開工前基底 `7484c57b`**（`git worktree`，port 8572，同為 Streamlit 1.59.2）。比對主內容區＋側欄可見文字與按鈕／expander 標題（正規化 repo 路徑與時間後）。

| 情境 | 1440 | 390 | 主內容字數 |
|---|---|---|---|
| 🎯 標的（`?p=target`） | **逐字相同** | **逐字相同** | 727／756 |
| 💼 持股（`?p=hold`） | **逐字相同** | **逐字相同** | 5310／5339 |
| `?legacy=1` 市場（`p=market&legacy=1`） | **逐字相同** | **逐字相同** | 1474／1474 |
| `?legacy=1` 標的（`p=target&legacy=1`） | **逐字相同** | **逐字相同** | 425／425 |

8 組全部 `same: true`、`diff: null`（`_compare_other_pages.json`）。⚠️ 限制：(1) harness 下 `?legacy=1&p=market` 兩邊都顯示同一個既有例外 traceback（夾具限制，非本批引入；字數 1474 是該例外頁），故「legacy 市場」只證明**前後相同**，不證明 legacy 市場頁在真環境可用；(2) 👤 我的頁 harness 不支援，**未比對**（以 `src/` 內 `page_me*`／`app.py` 0 diff 為間接證據：兩範圍 diff 只含 `_market_blocks.py`、`page_market.py`、`_ui_kit.py`〔加性參數、預設逐呼叫相同〕、`compact.py`〔加性〕）；(3) 比對的是可見文字，不是像素。

---

## §9 Streamlit floor 1.56.0（獨立 venv，同 harness、同腳本）

- 順序（L1 與圖區）與 1.59.2 **完全一致**（8 態皆 `orderByY` 相同）；A5／A11 量測值：全頁高 桌機三態同、手機 +42～74px（loaded 3789 vs 3747，cold 3072 vs 3029，report 3908 vs 3834，partial 4268 vs 4216）；Primary 圖高 220、y 軸刻度 14、圖例 5 項、小倍數 5 格、水平捲動 0；report 手機結論句相對 H2 +411（1.59.2 為 +379，仍在第一屏內）。Gate 判定在 1.56.0 下**結論不變**。
- 未驗：1.57～1.58；本批沒在 1.56.0 重跑 pytest（P4-2 PR_NOTES 記錄 floor 1.56.0 市場頁 8 檔 AppTest 769 passed，屬前一批證據）。

---

## §10 (A)／(B)／(C) 三類（Gate 結論）

### (A) PASS（14 項）
A1、A2、A3、A7、A9；V1、V2、V4、V5、V6、V7、V8、V9、V10、V11（V9 附一條 P2 文字一致性備註）。

### (B) 🟡 登記項（登 BACKLOG P2；已有 DEC 依據者標明）
| 項 | 偏離量 | 依據／處置 |
|---|---|---|
| A4 卡片密度 | 手機三卡均高 1.30×（上限 1.2×）；風險 tile 卡面 98～114 字（>60） | 超標句為 C6-3／C2 客戶要求外露逐字句（DEC-117 Q6／DEC-105）；登 `P1R-P4-RISK-TILE-FACE-DENSITY`（新） |
| A10 CTA／Q11 | 手機結論句 +269～+379（上限 +260）；桌機 report +218（上限 +200） | 內部建議值；源於客戶 Q1／Q5 順序；登 `P1R-P4-Q11-MOBILE`（新）；`P1R-P4-HEADER-FORM-HEIGHT` 已量（106px） |
| A11 手機 KPI／圖 D | KPI 區塊 462／394（上限 340）；圖 D 723px（86% 屏高） | 客戶 Q1 2＋1 排法的結果；`P1R-P4-CHART-D-MOBILE-HEIGHT` 已登；KPI 新登 `P1R-P4-KPI-BLOCK-MOBILE` |
| V3 chip 數 | 6（上限 5） | 計法待複驗；登 `P1R-P4-V3-CHIP-COUNT`（新） |
| 例外（不計 🟡）：Q7 手機 Primary；DEC-118 手機 ⚡；report 態 36px 邊界；partial 態 | — | Gate §8 紀錄＋§5 第 2 列 |
| **O1 觀察：桌機 report 態 Primary 圖上緣不在第一屏（圖本體 y938＞900）、partial 態整個出第一屏；report 態 Q11 +218** | — | 按過更新後的真實常見態；Gate 基準為 loaded 故不計 🟡。⚠️ **若總管／獨立 QA 把 report 態視為 Gate 基準態，A2 降 🟡、🟡 累計變 5**。新登 `P1R-P4-PRIMARY-EDGE-REPORT-STATE`（新）；成因＝客戶 Q5（結論前移）＋D1，非 P4-2 圖區 |
| 觀察：風險 tile 手機僅露 42px、cold ⚡ bar 「尚未載入」無 ⬜ | — | 已登 `P1R-P4-RISK-TILE-FIRST-SCREEN`；V9 備註新登 `P1R-P4-V9-BAR-SYMBOL`（新） |

### (C) ❌／需客戶判斷
**3 項 ❌（A5、A6、A8）＋🟡 ≥4 合計規則**；詳細＋最少必要數值＋推薦＝§11。

---

## §11 (C) 項明細

### 11.1 需客戶判斷（Gate §5 第 3／4 列；≤3 題，附推薦）

| 題 | 偏離量（最少必要） | 選項（一句差異） | AI 總管推薦（本報告單組意見） |
|---|---|---|---|
| ~~**題 1｜桌機頁面長度（A5 ❌）**~~ 📌 **已由客戶 DEC-119 題 2=A 結案（2026-10-31）** | 桌機全頁 3061px，是 blueprint 1517 的 **2.02×**（上限 2×，超 27px）；其中 **670px 是你核准要原樣保留的 11 個 L2 摺疊列＋頁尾**，扣掉也還有 1.58×（仍屬 🟡）；手機 1.51×（🟡）。 | **A** 接受現況，把「保留 L2 摺疊列」記為對全頁高上限的已知例外；**B** 把 11 個 L2 摺疊列合併成較少群組（動 L2 結構，需先出線框）；**C** 只把摺疊列往下收進單一「更多資料」摺疊（同樣動結構） | **A**（L2 是你要求保留的資訊，B／C 要改已核准結構；全頁高是內部建議值） |
| ~~**題 2｜手機主圖高度（A6 ❌）**~~ 📌 **已由客戶 DEC-119 題 1=A 結案（2026-10-31；實作改自訂圖表元件，不是「接受 220＋維持單行圖例」）** | 手機圖 A 高 **220px**，契約上限 **140px**（+57%）；桌機 220 符合。要做到 140 需手機專用圖或另一種圖表元件，且 y 軸與 5 項圖例更擠（圖例手機現已被裁到只剩約 2 項）。 | **A** 接受 220（手機主圖本就在第一屏下方，已是你核准的例外）；**B** 手機專用 140px（成本高、可讀性差）；**C** 折衷 ≈180px 並同時修圖例換行 | **A**（另外圖例被裁是獨立的內部缺口，見 §12 F1，不必問你） |
| **題 3｜四項輕微偏離是否接受（🟡≥4 合計規則）** | 4 項：手機三卡均高 1.30×（上限 1.2×）且風險卡 98～114 字（上限 60）；手機結論句頂端 +269～+379（上限 +260）；手機三卡區塊 462px（上限 340）；第一屏判斷用 chip 6 個（上限 5）。四項成因都是你核准的結構（CTA 在結論前、2＋1、風險卡保留逐字退化句與指路句）。 | **A** 接受這 4 項為已知合理偏離，不累計成 ❌；**B** 逐項壓到上限（要動你已核准的內容或排法，例如風險卡指路句改進摺疊）；**C** 只接受其中部分 | **A**（B 會與 DEC-117 Q1／Q6／DEC-105 第 4 點相牴觸） |

⚠️ 上列門檻（Q2、Q3、Q11、Q12、4 項 🟡 的上限）皆為 **DEC-110 內部建議值**，總管可自行修訂內部值，但**為了過 Gate 而放寬判準不在本報告權限內**；若總管選擇內部修訂，請另走 DEC 紀錄並在 Gate 報告註明「判準變更」。

### 11.2 可內部修（不需客戶；本批未動 `src/`，列為發現項／下一批建議）
- **A8 ❌（3 塊）**：縮短 AI 自寫的 ①狀態列、②AI／資料狀態行（把 `（逐來源結果見頁首更新鈕下方的更新報告）` 下沉或縮短）、③圖 C 一行 `CHART_C_EMPTY` 至 ≤32 字（內容全文已在摺疊「為什麼／來源」逐字，資訊不丟）。屬內部自決（v3 §03-1）；改字須同步 REGISTRY／守衛（`test_p4_2` `TestC8a`）。

---

## §12 發現項（判定過程發現；需改 `src/`／`tests/` 才能處理；本批未動）

| # | 發現 | 證據 | 建議 |
|---|---|---|---|
| **F1** | （P4-4 更新：**未修，停點回報**，見 §14）手機圖 A 圖例被裁，客戶明列「保留圖例」（DEC-117 C4-1）的手機可見度不足 | `zone_loaded_390_zone.png`；`_measure_p4_2.json` legend 5 項但可見約 2 項 | P4-4：縮短 MA 系列名或讓圖例換行（守衛 `test_c4_1_layout_css_never_selects_chart_internals` 限制 CSS 手法） |
| **F2** | P4-2 手機 Primary 圖高 220 超契約 Q3 ≤140（+57%）未在 PR_NOTES 揭露，守衛只釘「≤`SLOT_HEIGHT_MAX_PX`」 | `_measure_p4_2.json` chart.h＝220（390） | 題 2 裁示前不動；若選 B／C 才改（需 viewport 分流） |
| **F3** | ~~守衛缺口：沒有任何測試釘「外露層非客戶原句 ≤32 字」（A8）與「手機 Primary ≤140」 | 本批 A8／A6 皆由量測腳本發現 | 若 P4-4 修 A8，補外露句長度守衛（註冊客戶原句白名單）~~ → 📌 **2026-10-31 P4-4 更新（有意識的更新，不是漏刪；決策者 AI 總管〔v3 §03-1 內部自決〕；原文保留）**：**已補**（`tests/test_p4_4_market_exposed_text.py`，見 §14）；「手機 Primary ≤140」不釘（A6 待客戶裁示），改釘現況 220 |
| **F4** | 文件過期：HANDOFF／BACKLOG 寫 P4-1／P4-2「未 push、未開 PR」，實際已合併（#984／#985） | `git log` `228b9fa9`／`4c1546b5` | 本批已更正 HANDOFF 現行列 |
| **F5** | 線框 §10.7 內 2 條測試名已改名／被取代（見 §7 說明） | §7 | 僅文件追溯，不影響守衛 |
| **F6** | harness `&cold=1` 位階仍顯示「多頭」，本批 cold 量測的位階 tile 不是真冷啟動 | `app_market_cold_*.png`；`P1R-P4-HARNESS-COLD-NOT-TRUE` | 真冷啟動需真資料環境；Gate 報告據實標「夾具」 |

---

## §13 未驗

真資料態／真冷啟動、1.57～1.58、手機實機（iOS／Android）、Streamlit Cloud、Safari／Firefox、`?legacy=1&p=market` 在 harness 下的既有例外（兩邊皆有，夾具限制）、👤 我的頁（harness 不支援）、全量 Fast／slow lane 於 HEAD 重跑（本批只跑 978 項相關子集）、獨立 QA 組判定與總管複驗（Gate §4）。

---

## §14 P4-4 內部小修批更新（2026-10-31；有意識的更新，不是漏刪；決策者 AI 總管〔v3 §03-1 內部自決〕；上文 §0～§13 全部保留不改，僅在 A8／F3 兩處就地劃線）

- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：本節與 P4-4 全部量測、mutation 為**實作組單組產出，未經第二組驗證**。量測環境同 §1（harness 夾具，1.59.2；floor 1.56.0 另量）。「A8 已 0 塊」只涵蓋 loaded 基準態的 DOM 葉節點量測，不涵蓋真資料態。
- **A8（原 ❌ 邊界）→ 已修**：3 塊 AI 自寫句縮到 ≤32 字，**原整句逐字下沉**（資訊只下沉、不刪）：

| 塊 | 外露（之前 → 現在） | 縮短用字來源 | 原整句逐字落點 |
|---|---|---|---|
| ① 頁首狀態列 | 42 字 `本次使用中尚未按過更新｜資料日：…（加權指數，來源：市場評估輸入）` → 26 字 `本次使用中尚未按過更新｜資料日：2026-10-23` | 原句前半（只拿掉尾端括號） | 「資料來源與完整度」展開區 caption：`資料日：…（加權指數，來源：市場評估輸入）` |
| ② AI／資料狀態行 | 44 字 → 23 字 `🤖 AI 投資總結：⬜ 尚未提供　⬜ 資料狀態：尚未彙總` | 原句前兩段（`HERO_AI_PLACEHOLDER`＋`HEALTH_CHIP`） | 「資料來源與完整度」展開區 caption：原整句（含 `（逐來源結果見頁首更新鈕下方的更新報告）`） |
| ③ 圖 C 一行 | 50 字 → 28 字 `需先核准：EPS 資料來源、PE 情境、計算公式、更新頻率。` | `CHART_C_EMPTY` 第一句 | 圖 C 摺疊「為什麼」（客戶原句 `CHART_C_SAY` 之後）：`CHART_C_EMPTY` 整句 |

- **A8 兩種計法（狀態列是否算 metadata 由總管判）**：之前＝3 塊（含狀態列）／2 塊（不含）→ 現在＝**0 塊／0 塊**。
- **未動、因為是客戶／契約原句**：今日結論句（93／71 字，DEC-081 Q2-1 逐字）；`HERO_AI_PLACEHOLDER`、`HEALTH_CHIP`、`HEALTH_CHIP_POINTER`、`REFRESH_TIME_NOTE`（R8）、`CHART_C_SAY`、`CHART_C_BASIS` 全部逐字未改（`test_a8_contract_and_client_sentences_are_not_shortened`）。
- **其他態的剩餘 >32 字葉節點（DOM 量測，供總管判斷，本批不動）**：cold 態 ⚡ 一行 bar 34 字（由既有常數組成，客戶 DEC-117 Q8c 核准的一行形式；Gate 基準 loaded 不計）；report／partial 態狀態列「更新時間」半句 50 字（含 R8 契約片段 `按下更新的時間，不是資料日`，縮短＝改 R8 字樣，不在內部權限）；`✅／⚠️ 上一次更新的結果…` 48／54 字與 partial 的真錯誤「下一步…」151 字＝既有更新報告（`page_today._render_refresh_report`，DEC-081 Q1=C 禁改）。
- **F3 → 已補守衛**：`tests/test_p4_4_market_exposed_text.py`（9 項）。A6「手機 ≤140」**不釘**（待客戶題 2）；改釘**現況** Primary 圖高 220＝`compact.SLOT_HEIGHT_MAX_PX`、圖與冷啟動槽共用同一個值、無 viewport 分流（改任何值都得先改該測試＝先過客戶裁示）。
- **F1（手機圖例被裁）→ 未修，停點回報**。實測（1.59.2／1.56.0 同）：`st.line_chart` 圖例為**單行水平**、5 項 x 範圍 107～886px，手機圖寬 326px（可見 ≈2 項）；`st.line_chart` 沒有圖例設定參數，CSS 又受 `test_c4_1_layout_css_never_selects_chart_internals` 禁止。要讓 5 項都可見只能：(a) 改 `st.vega_lite_chart`／`st.altair_chart` 自訂 spec（圖例 `orient: bottom`＋`columns`），**即換圖元件、超出 `st.line_chart` 能力**；(b) 縮短 5 個系列名（`MA120（最新值，參考）`→較短），但估算 5 項仍 >326px，不能單靠它。原型實驗（scratch，未入庫）：vega_lite_chart＋`columns:2` 下 5 項全進圖例區，但第 2 欄 `MA120（最新值，參考）` 右緣 405px＞圖寬 358px 仍被裁，須再縮系列名或 `columns:1`（圖例佔 5 行、繪圖區變矮，與 A6 圖高題互相牽動）。截圖 `p4_4/f1_proto_vega_legend_cols2_390.png`、`p4_4/legend_390_before_unchanged.png`。
- **重量測**：`p4_4/_measure_p4_4_gate.json`（1.59.2）、`_measure_p4_4_gate_floor156.json`（1.56.0）、`_compare_other_pages.json`（其他頁與 `?legacy=1` 前後 8 組 `same: true`，前＝本批前 HEAD `e088c559` 的 worktree）。全頁高：桌機 loaded 3061（不變，A5 **未動**）／手機 loaded 3747→3680；A6 圖高 220 未動。

---

## §15 獨立 QA 複驗更正（2026-10-31；有意識的更新，不是漏刪；出處＝獨立 QA 複驗〔AI 總管轉交，單組以上但仍待總管複驗〕；§0～§14 原文保留，僅於 A2／A10／A11／V3 列就地劃線或加註）

**QA 結論**：P4-4 程式 0 缺陷；Gate **❌ 同意**。以下為對本報告的更正。

| 項 | 更正 |
|---|---|
| **A2** | report 態桌機圖本體 y≈916＞900 ⇒ 依契約 B1 登記 🟡（loaded 基準態 ✅ 不變）。 |
| **A10** | P4-4 後實量：手機結論句頂端 loaded +269／cold +269／report +356／partial +292（皆 >260，仍 🟡）；桌機 report +195 ≤200（不再超標）。 |
| **A11** | 理由 ＝ 手機 KPI 區塊 loaded 461／cold 394 > ≤340；不再引「圖 D 723px」為理由（它在第一屏外），移列**獨立觀察**（`P1R-P4-CHART-D-MOBILE-HEIGHT` 維持登記）。 |
| **V3** | 改判 ✅：契約 B3 規定圖 header chip 歸 §4；第一屏判斷用 chip 計 5。`P1R-P4-V3-CHIP-COUNT` 可關。 |
| **🟡 合計重算** | A2、A4、A10、A11 ＝ **4 項**（V3 退出、A2 加入），數目仍 ≥4。 |
| **FAIL 成因重述** | **A6 ❌ 為主因**（手機 Primary 220 > 140，+57%）。A5 字面 ❌ 但**量法敏感**：scrollHeight 含 Streamlit 殼 padding（頂 72／底 160）；只量頁面內容約 **1.87～1.90×**（<2×）。🟡≥4 合計規則同時成立。三者都待客戶題 1～3，本批不動。 |
| **A8 殘留態（如實列）** | loaded 基準態 0 塊。殘留：cold 態 ⚡ bar 整行 34 字（DOM 葉節點；由既有卡片段組成，已改成逐片段守衛）；report／partial 態 `page_today` 更新報告既有句（48／54／151 字，DEC-081 Q1=C 禁改）與狀態列 R8 半句 50 字。這些都不是 AI 自寫的新句。 |

**§14 F1 補 QA 評估**：方案＝`st.vega_lite_chart`（或 altair）自訂 spec。`columns: 3` 加縮短系列名 ⇒ 會丟掉「（最新值，參考）」限定語，該限定語須移到**圖例標題或摺疊**（不得無聲消失）；牽動 `test_p4_2_market_charts.py` 約 5 個守衛（原生圖恰 1、MA 線／y 軸／圖例、M4／M5 寫法等）；並與 A6 圖高題（題 2）互相牽動（圖例佔高會擠繪圖區）。仍待總管決定是否換元件，本批未動。

**守衛補強（本批）**：`tests/test_p4_4_market_exposed_text.py` 白名單改精確比對（結論句固定模板 fullmatch、R8 半句 fullmatch、⚡ bar 逐片段）；HTML 元件與表格儲存格逐葉掃；Warning／Error 只排除 `page_today._render_refresh_report` 自己畫的字；QA mutation M10（長自寫句以「市場位階：」起頭）、M11（長句包在 unsafe_allow_html）、M14b（長 st.warning）＋自加 M15（長句塞進 ⚡ bar）重跑**全部轉紅**。

---

## §16 P4-5 客戶裁示落盤＋F1 修正＋Gate 重判（2026-10-31；有意識的更新，不是漏刪；決策者 **客戶**（DEC-119 題 1=A／題 2=A）；§0～§15 原文保留，僅於 §2 A5／A6 與 §11.1 題 1／題 2 就地劃線）

- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：本節量測與 mutation 為**實作組單組產出，未經第二組驗證**；Gate §4 要求的**獨立 QA 組複驗尚未發生**（本節＝供其複驗的**重判**，不是最終 Gate 結論）。量測環境＝harness 夾具（`tools/visual_fidelity/harness_app.py`，Streamlit 1.59.2；floor 1.56.0 另以獨立 venv 同腳本重量）。**真資料態、真冷啟動、1.57～1.58、手機實機、Streamlit Cloud、Safari／Firefox 全部未驗。** 「CI 綠」**未驗**（本批未 push、未開 PR；Stage complete 須 CI 綠＋Gate PASS＋獨立 QA 複驗）。
- **客戶裁示**（DEC-119）：題 1＝A（手機 Primary 維持約 220px＋自訂圖表讓 5 項圖例可見；DEC-117 Q4 澄清）；題 2＝A（桌機全頁 2.02× 登記為已知輕微偏差）。

### 16.1 F1 修正（手機圖 A 圖例）

`st.line_chart` → `st.vega_lite_chart` 自訂 spec（`_market_blocks.render_twii_chart`／`twii_chart_spec`／`twii_chart_long`）。圖高仍 220（Primary 與冷啟動槽同一個 `PRIMARY_CHART_HEIGHT_PX`）；指數線＋MA 水平參考線（最新值，不自行算均線）、y 軸（有刻度）、x 時間軸、tooltip 帶日期／**完整系列名**／數值；圖例置底 3 欄、短名（`MA5` 等），**限定語「最新值，參考」移到圖例標題**「MA 均為最新值，參考的水平線」，完整系列名（`MA5（最新值，參考）`）逐字留在資料與 tooltip；色彩固定對映（指數藍、MA5 橘、MA60 綠、MA120 紫、MA200 紅）。`twii_chart_frame`（寬表）與 L2／L3 資料 0 變動；`page_market.py` 0 diff（還原鏈 pair 不需重產）。

**圖例量測（390×844，圖寬 326px，圖高 220；`p4_5/_legend_p4_5.json`，1.59.2；floor 1.56.0 逐項相同）**

| 圖例項 | x 範圍（px，相對圖左緣） | ≤ 圖寬 326？ |
|---|---|---|
| 加權指數收盤 | 50.5～146.0 | ✅ |
| MA5 | 161.5～210.4 | ✅ |
| MA60 | 237.5～291.9（最右緣） | ✅ |
| MA120 | 50.5～110.4（第 2 列） | ✅ |
| MA200 | 161.5～221.4（第 2 列） | ✅ |
| 圖例標題 | 49.0～197.2 | ✅ |

圖例頂端 y143＞繪圖區底 → **不遮圖**（`legendOverlapsPlot=false`，六態皆同）；水平捲動 0；圖例 5 項（loaded／report／partial × 390／1440 共 6 組皆 5 項；cold 無圖，槽高 220 不變）。桌機（948px 圖寬）圖例同樣 2 列、較原單行多 1 列，圖高仍 220（繪圖區較原單行版略矮，**這是桌機唯一可見的外觀變化**）。

**第一屏／其他頁不退化（FACT，DOM 量測）**：`measure_p4_5_gate`（A3～A11／V3／V8～V11 全量）對 P4-4 的 `_measure_p4_4_gate.json` **逐欄 0 差異**（8 態：全頁高、卡高、第一屏字數、外露 >32 字清單、Missing 符號、chip 數皆同）；`measure_p4_1`（區塊順序與 y）對基底 HEAD `3f9927b4`（worktree）**0 差異**（結論句 y：手機 loaded 404／cold 404／report 491／partial 427；桌機 282／282／330／282；⚡ 緊接 3 tile、Primary 緊接 AI 行，順序未動）；`measure_p4_2`（圖區）僅圖例文字與 svg 路徑計數差異；其他三頁與 `?legacy=1` 前後 8 組逐字相同（`_compare_other_pages.json`）。全頁高（loaded）桌機 3061／手機 3680，與 P4-4 相同。截圖 `p4_5/p4_5_primary_<state>_<390|1440>.png`（第一屏 `app_market_<state>_<390|1440>.png`；全頁長圖未入庫，量測值見 JSON）。

### 16.2 Gate 重判（loaded 為基準態；其餘為補充）

| 項 | P4-3／§15 | 現在 | 依據 |
|---|---|---|---|
| A1、A3、A7、A9；V1、V2、V4～V11 | ✅ | ✅（V3 依 §15 QA 改判 ✅） | 量測 0 差異 |
| **A5 空白比例** | ❌（2.018×） | **客戶接受之已知輕微偏差**（不計 ❌） | DEC-119 題 2=A；Gate §8 登記；全頁高 3061／1517＝2.018× 未變 |
| **A6 圖表大小** | ❌（手機 220＞140） | **✅（客戶例外）** | DEC-119 題 1=A；Gate §8 登記；圖例 5 項已可見（F1 修好） |
| **A8** | ✅（P4-4） | ✅ | 外露層 0 差異 |
| A2 Primary 突出 | 🟡（report 態桌機圖本體 y916＞900；loaded ✅） | 🟡（不變） | 本批未動版面；report 態桌機 chart y916／loaded y868 |
| A4 卡片密度 | 🟡 | 🟡（不變） | 本批未動 |
| A10 CTA／行動首屏 | 🟡（手機結論頂端 +269～+356） | 🟡（不變） | 本批未動（結論 y 0 差異） |
| A11 手機 KPI 區塊 | 🟡（461／394 > 340） | 🟡（不變） | 本批未動 |

- **單項 ❌＝0；🟡＝4 項（A2、A4、A10、A11）⇒ 依 Gate §2 合計規則「🟡 ≥4 視為 ❌」仍觸發。** A5 是否也計為 🟡（客戶措辭「登記為已知輕微偏差」）有兩種讀法——計入則 5 項；無論哪種，合計規則皆觸發，**不改變結論**。
- **Gate 判定：❌ FAIL（僅因 🟡≥4 合計規則；無單項 ❌）。Stage 維持「未完成」**；⛔ 不得宣稱 Stage complete（另需：CI 綠、獨立 QA 複驗、客戶對下列題 3 的裁示）。BACKLOG `P1R-PHASE4-MARKET` 維持 open。
- **需客戶判斷（1 題；原 §11.1 題 3 沿用並更新項目）**：
  - **題｜四項輕微偏離是否接受為已知合理偏離**：A2（桌機 report 態圖上緣 y916，第一屏 900）、A4（手機三卡均高 1.30×、風險卡 98～114 字）、A10（手機結論句頂端 +269～+356，上限 +260）、A11（手機三卡區塊 461px，上限 340）；成因＝你核准的結構（CTA 在結論前、2＋1 排法、風險卡保留逐字句）。
    - **A**：接受這 4 項為已知合理偏離，不累計成 ❌。
    - **B**：逐項壓到上限（會動你已核准的內容或排法，與 DEC-117 Q1／Q6、DEC-105 相牴觸）。
    - **C**：只接受其中部分。
    - **AI 總管推薦：A**（B 會推翻已核准結構）。
- **§12 發現項狀態**：F1 → **已修**（本節）；F2（手機 220 未揭露）→ 由 DEC-119 題 1 結案；F3 已於 P4-4 補；F4～F6 不變。

### 16.3 守衛與 mutation（單組）

- 圖 A 守衛由「釘 `st.line_chart` 原始碼／AST」改為**對 vega spec 的語意守衛**（`tests/test_p4_2_market_charts.py::TestC41`，**不降強度**）：y 軸未隱藏且有刻度（labels／ticks／domain 不得 False）、x 時間軸、legend 存在且 domain＝全部系列、圖例短名對映與限定語在標題、5 系列版圖例 5 項、**圖例寬度估算 ≤ 手機圖寬 326px**、無 normalize／stack／window／aggregate／impute 等變換、無 width（非 mini）、圖高 220＋autosize fit、**golden：資料表逐值＝`view.close`／MA 最新值**（MA200 缺則無列、不補 0）、缺口保留為 null（⛔ ffill／fillna）、色彩固定對映、渲染呼叫與圖高共用 `PRIMARY_CHART_HEIGHT_PX`、元件呼叫不帶多餘參數、全模組不得再出現 `st.line_chart`。P4-4 圖高守衛（`TestA6PrimaryHeightIsPinnedAtTodaysValue`）維持綠。
- **mutation 15 項全部轉紅**（`p4_5/mutation_p4_5.py`，逐一突變 `_market_blocks.py`→跑守衛→還原）：拿掉 legend／legend 少一項／y 軸 axis=None／y 軸刻度標籤關閉／資料 normalize／缺口 ffill／圖高改 140／legend 欄數 5（右緣超出手機圖寬）／圖例標題丟限定語／色彩對調／加 width（sparkline 化）／圖例標籤帶回限定語（超寬）／加 window 滾動 transform／tooltip 丟完整系列名／退回 `st.line_chart`。
- floor 1.56.0（獨立 venv：repo `requirements.txt`＋`streamlit==1.56.0`）：市場頁相關 337 項 AppTest 綠；harness 同腳本（legend／gate 量測）結果同 1.59.2，手機全頁高 +42～75px（與 §9 同量級）。

### 16.4 未驗

真資料態／真冷啟動、手機實機（iOS／Android 的字型寬度與圖例實際換行；本批圖例寬度以 Chromium＋夾具字型量測）、Streamlit Cloud、Safari／Firefox、1.57～1.58、深色／淺色主題對比（圖例色以固定色票，僅看過深色）、CI、獨立 QA 複驗。

## §17 DEC-120 最終判定（2026-10-31；有意識的更新，不是漏刪；決策者 **客戶**（DEC-120「選 A」，經總管轉交）；§0～§16 原文保留不改）

- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：客戶裁示僅見總管轉交摘要；本節是把裁示套入 §16.2 的**登記**，不產生新量測。**CI 綠與獨立 QA 複驗尚未發生——因此下方「PASS」是裁示後的待驗判定，不得寫成已完成、不得據以宣稱 Stage complete／已 merge。**
- **客戶裁示**（DEC-120）：§16.2「需客戶判斷」題＝**A**：A2／A4／A10／A11 四項 🟡 接受為已知合理偏離，不因「🟡≥4 視為 ❌」升格。⛔ **僅限 📊 市場頁，不得泛化到其他頁面。**

| 項 | §16.2 | DEC-120 後 | 數值（未變） |
|---|---|---|---|
| A2 Primary 突出 | 🟡 | **已知合理偏離（客戶接受）** | 桌機 report 態圖本體頂 y≈916 ＞ 900 |
| A4 卡片密度 | 🟡 | **已知合理偏離（客戶接受）** | 手機均高 1.30×；風險卡 98／114 字＞60 |
| A10 CTA／行動首屏 | 🟡 | **已知合理偏離（客戶接受）** | 手機結論頂 +269／+269／+356／+292 vs ≤+260 |
| A11 手機不被塞滿 | 🟡 | **已知合理偏離（客戶接受）** | KPI 區 461／394 vs ≤340；水平捲動 0 |

- 接受理由：已核准結構的可預期結果；無資訊遺失；無 Missing／Risk／護欄語意退化；無新水平捲動或破版；再壓回上限會犧牲已核准的第一屏優先序或風險資訊。
- **Gate 判定：PASS（DEC-120）——條件式**：單項 ❌＝0；🟡 四項已裁示免升格。**成立尚需**：① CI 綠（PR #987，Fast＋Slow）；② 獨立 QA 組複驗（含「無資訊遺失／無護欄退化／無新水平捲動」免升格前提）。兩者**尚未完成**。
- Stage／BACKLOG `P1R-PHASE4-MARKET`：**維持 open，直到上述兩條件完成並 merge**；⛔ 不得宣稱 Phase 4 已結案或已 merge。
- ⛔ 範圍：只登記例外，不改 UI／程式；他頁（🎯 標的頁等）各自重新量測，照 Gate §2 合計規則判定，不繼承本裁示。

### 17.1 合併結果（2026-10-31；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；上方 §17 原文保留不改）

| 項 | 事實 |
|---|---|
| CI | PR #987 Fast＋Slow 皆綠（GitHub 實查／總管轉述） |
| 獨立 QA | 複驗通過（含「無資訊遺失／無護欄退化／無新水平捲動」免升格前提）；QA 另發現的非阻擋項已登記 BACKLOG（`P2R-P4-CHARTA-*`、`P2R-P4-QA-UNVERIFIED-987`） |
| 合併 | PR #987 squash 為 `f42ce0e6` |
| Gate／Stage | DEC-120 條件（CI 綠＋獨立 QA 複驗）已成立；`P1R-PHASE4-MARKET` 關閉；§17 前述「尚未完成／不得宣稱已 merge」為當時狀態，現已被取代 |

- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：**DEC-120 文字本身未另經獨立複驗**；本節僅登記 CI／QA／合併事實，不新增量測；真資料、手機實機、Streamlit Cloud、1.57～1.58 等 §16.4 未驗項仍未驗。
