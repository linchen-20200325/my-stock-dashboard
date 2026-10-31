# UI Visual Fidelity Gate（視覺保真閘門）

- **狀態**：正式／現行
- **日期**：2026-10-29
- **決策來源**：Gate 的存在、「UI Stage 完成條件」地位、每個 UI PR 至少附 desktop＋mobile 390px 截圖、對核准 blueprint 檢查 11 項、「CI／QA／tests／mutation 全綠 ≠ UI Stage complete」、明顯偏離＝Visual Fidelity FAIL、第一屏三層答不出＝FAIL ＝ **客戶 2026-10-29（`docs/DECISIONS.md` DEC-109 四、二十三、二十四，逐字收錄於該條）**；本檔的量化門檻、截圖規格、判定流程、補充檢查 V1～V11、工具 ＝ **AI 總管內部決定（DEC-110，依 `CLAUDE.md` §-1.5.D v3 §03-1；客戶可推翻）**。
- **上位**：`CLAUDE.md` > `PROCESS.md` > `PROJECT_RULES.md`（第 24 節為本檔治理入口）＋`docs/governance/*`（本檔）> 最新有效 DEC。
- **配套**：呈現規格＝`docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md`（下稱「契約」）；baseline＝核准 blueprint `docs/vnext/d25_wireframes/*.html`（DEC-092；DEC-109 二十四定為 Visual SSOT）；現況 baseline 量測＝`docs/vnext/visual_fidelity/phase1_baseline/VISUAL_GAP_AUDIT_2026-10-29.md`；工具＝`tools/visual_fidelity/`。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：本檔單組撰寫，未經第二組獨立驗證；門檻數字依 blueprint 量測推出（契約 §19），是建議值。

---

## §1 Gate 定義

1. **前置**：Phase 3～7 每個 UI phase 寫 UI code 前，須先出**文字線框**（含該頁 W 點、與 blueprint 的版面差異、總管推薦），依 `CLAUDE.md` §-1.5.D v3 §03-2 ①；線框核准後施工，施工完過本 Gate。
2. **適用**：任何改變新 UI（`src/ui/views/**`、`src/ui_v2/**`、新 UI 依賴的共用 render 層、`app.py` 站殼）**畫面**的 PR，含 Phase 3～7 全部 UI 批次。純 docs、純資料層／L3 且畫面零變化的 PR 不適用（PR 描述寫「Visual Fidelity：N/A，理由…」）；Phase 2 等「宣稱畫面零變更」的 PR 須附批前／批後截圖或量測值對照證明零變更。
3. **核心規則（客戶原文）**：**CI / QA / tests / mutation 全綠 ≠ UI Stage complete。** 若 screenshot 與 blueprint 在資訊層級、圖文比例、第一屏、Visual Budget、圖表尺寸、卡片密度明顯偏離：**Visual Fidelity FAIL**。若一頁無法明確回答「第一眼看什麼？第二眼看什麼？第三層才看什麼？」：**Visual Fidelity FAIL**。
4. **與 Definition of Done**：UI Stage 的 DoD（`PROJECT_RULES.md` 第 7 節＋第 24 節補註）＝**CI 綠＋Visual Fidelity PASS**：`… → independent audit → Visual Fidelity Gate（本檔）→ … → merge`。Gate 未過，BACKLOG 不得把該 Stage 移到「已結案」，HANDOFF 不得寫 complete。
5. **與客戶 Gate 的關係**：本 Gate 是**內部品質閘門**（判定者＝獨立 QA＋總管複驗），**不是**客戶裁示 Gate。只有「偏離屬版面設計變更」時才走 `CLAUDE.md` §-1.5.D v3 §03-2 ① 草稿先行送客戶（§5）。
6. **不勝過資料規則**：截圖只證明「長什麼樣」，**不**證明資料正確；Gate 通過不豁免任何資料／投資／安全守衛。⛔ 為了過 Gate 改資料語意、公式、Risk Cap、投資語意或刪資訊（契約 §9）。

## §2 檢查項

> 每項判 ✅ 通過／🟡 輕微偏離（可合併，但須在 PR 寫理由並登記 BACKLOG P2）／❌ 明顯偏離（**不得標 complete**，走 §5）。
> 量測在 **desktop 1440×900** 與 **mobile 390×844**、**已載入**狀態（冷啟動另驗 A1、A9、A10、V9）；量法＝`tools/visual_fidelity/measure_app.js` 或等價 DOM 量測。分母「blueprint」＝同頁同寬 `measure_mock.js` 量測。

### 2.1 客戶 11 項（DEC-109 二十三，項目名逐字）

| # | 檢查項 | ✅ | 🟡 | ❌ |
|---|---|---|---|---|
| A1 | **第一屏結構** | 區塊順序與種類與 blueprint 一致（經客戶裁示覆蓋者除外，契約 §14.1）；五問全可見（契約 §3） | 順序一致但缺 1 問，或多 1 個 blueprint 沒有的區塊 | 骨架不同；或缺 ≥2 問 <br>📌 **就地加註（2026-10-30；有意識的更新，不是漏刪；決策者 客戶〔DEC-117〕，落文 AI 總管；上列原文一字未動）**：📊 市場頁的「經客戶裁示覆蓋」依據＝**DEC-117**：區塊順序 頁首 → 更新 CTA → 今日結論 → 3 個核心狀態 → ⚡需要處理 → AI／資料狀態 → Primary Visual（Q5）、桌機 3 tile＋頁首 CTA／手機 2＋1（Q1）、Primary＝圖 A＋國際 small multiples（Q4）；與 blueprint「4 張 hero」等差異依 §5 第 2 列不算偏離。手機五問④：⚡ bar（或「⬜ 無警示來源」）**須在 390×844 第一屏**（Q7 例外只豁免 Primary；AI 總管判定，線框 §10 C1-10）。 |
| A2 | **Primary Visual 是否突出** | 恰 1 個 Primary 在第一屏（header＋圖上緣可見），視覺權重最高 | Primary 在第一屏但被同權重元素並列 | 0 個或 ≥2 個大型圖互搶；Primary 收在 expander <br>📌 **就地加註（2026-10-30；有意識的更新，不是漏刪；決策者 客戶〔DEC-117 Q7〕，落文 AI 總管；上列原文一字未動）**：**📊 市場頁手機（390×844）**登記合理 mobile exception——Primary 可位於第一屏下方，**成立條件**：(1) 手機第一屏優先序＝今日結論 > 核心狀態 > 是否需行動 > Primary Visual；(2) ⛔ 為塞主圖把結論或核心狀態擠出第一屏；(3) Primary **緊接 L1 決策區後方**、不得被 L2／L3 長內容插隊。條件不成立＝❌（不得以本例外放行）。依 §5 **第 2 列**（後續客戶裁示覆蓋）：**不算偏離、不計 🟡**。桌機 A2 照上列判準。紀錄見 §8。 |
| A3 | **圖表 / 文字比例** | 外露字數 ≤ 1.3× blueprint；blueprint 有圖處實作有圖或誠實 placeholder | 1.3×～2× | > 2×；或 blueprint 有主圖而實作外露 0 張且無 placeholder |
| A4 | **卡片密度** | 主卡卡面 ≤ 60 字（契約 Q6）；主卡平均高 ≤ 1.2× blueprint 對應卡 | 1.2×～1.5×，或 1～2 張卡超字數 | > 1.5×；或 prose card（卡面 > 2 句） |
| A5 | **空白比例** | 同列卡高差 ≤ 16px；無 > 120px 無內容空洞；全頁 ≤ 1.3× blueprint（Q12） | 卡高差 16～50%；或全頁 1.3×～2× | 卡高差 > 50%；或全頁 > 2× |
| A6 | **圖表大小** | Primary ≤ 220／140px；mini ≤ 96px；sparkline ≤ 64px（契約 Q3～Q5） | 超上限 ≤ 30% | 超上限 > 30% |
| A7 | **Top-N** | 產業／風險／候選／排名預設 Top 5～10 並有「查看全部」；L3 請求參數未變（契約 §10） | N 超建議值 ≤ 2 倍 | 長清單全量外露（> 2×） |
| A8 | **詳細文字是否下沉** | 外露層 0 段 > 32 字的非客戶原句；下沉清單（契約 §5）全在 L3 | 1～2 處 | ≥ 3 處 |
| A9 | **Missing 是否用 placeholder** | 缺值全為 ⬜ chip／placeholder；0／中性／續抱／安全 0 次冒充；未載入灰、出錯紅分離 | placeholder 正確但重複（同句每列重寫） | 缺值畫成 0／中性／HOLD；或未載入畫成紅色錯誤 <br>📌 **就地加註（2026-10-30；有意識的更新，不是漏刪；決策者 客戶〔DEC-115 D6=B〕，落文 AI 總管；上列原文一字未動）**：依 DEC-115 D6，契約 §8-4 的「圖槽」同高判準**讀作僅 Primary**；Secondary／small multiples／mini 圖缺資料時縮成一行誠實 placeholder，**不得隱藏 Missing／unavailable 狀態**。DEC-115 與契約 §8-4 措辭與此一致。 |
| A10 | **主要 CTA / 行動是否首屏可見** | 主 CTA 與行動（或下一步）在兩個 viewport 第一屏內；主要判讀句頂端符合 Q11 | 只在 desktop 第一屏可見 | 兩個 viewport 都不可見 |
| A11 | **mobile 是否被大表、大圖、長文塞滿** | 390px 第一屏無單一元素 > 50% 屏高；無水平捲動；KPI 區塊 ≤ 340px（KPI 列欄數暫不判定，待 `CV1-DR-12`） | 單一元素 50%～100% 屏高 | 單一元素 > 1 屏高；或水平捲動 <br>📌 **就地加註（2026-10-30；有意識的更新，不是漏刪；決策者 客戶〔DEC-117 Q1〕；上列原文一字未動）**：📊 市場頁「KPI 列欄數暫不判定」解除——手機 KPI 排法＝**2＋1**（市場位階｜水位並排、今日主要風險整列），KPI 區塊仍以 ≤340px 判；客戶明示「固定 3 欄」是桌機核心狀態網格要求、手機依可讀性自適應。 |

### 2.2 Visual Budget／契約補充檢查（DEC-110 內部）

| # | 檢查 | 判準（✅ 條件；不符＝❌，除非註明 🟡） |
|---|---|---|
| V1 | Primary 數量 | 恰 1（契約 §2 B1） |
| V2 | Secondary 數量 | ≤ 3；small multiples 一組算 1（B2） |
| V3 | 第一屏核心數字／status chip 數 | 3～5（B3；metadata chip 不計）；6～7＝🟡 |
| V4 | 第一屏主要判讀句數 | ≤ 1（B4） |
| V5 | 禁止清單 | 0 項命中：Report Wall、Chart Wall、第一屏多張大型圖互搶、每欄位一張圖、大量 donut／pie、文字牆換圖表牆（B5、B6） |
| V6 | 第一屏五問 | 五問各至少一元素可見（豁免見契約 §3） |
| V7 | 三層 | Gate 報告逐頁寫出「第一眼／第二眼／第三層」三行；寫不出＝FAIL（客戶原文） |
| V8 | chip 文字化 | 每個色塊／圖示都有文字；🔴 只用於系統真錯誤；metadata chip 不在訊號文字頻道（契約 §6） |
| V9 | Missing 符號（**只適用 metadata chip 家族**） | **狀態一律沿用 `shared/ui_state.UI_STATE_META` 既有符號，既有徽章族優先**（`⛔ 未接線`、`▨ 無資料`、`⟳ 缺漏 · 可重跑`／`⊘ 不適用 · 重跑無效`（客戶 2026-09-23 D-3(a) 三態）、`⬜ 尚未載入`、`◧ N／M 計入`、`🔴 取得失敗`＋1 句原因）；既有徽章族沒有的狀態才用 metadata chip 既有字樣（`⬜ 尚未定義`、`⬜ 尚未核准／無法判定`）；stale＝⚠；**同一狀態出現兩種符號＝❌**（契約 §6、§8） |
| V10 | 工程字樣 | 外露層 0（契約 §18；客戶自訂措辭例外） |
| V11 | 手機無 hover 依賴 | 0 項資訊只活在 `title=` 屬性；所有 L3 內容在手機可點開 |

- **合計規則**：A 或 V 任一 ❌ ＝ Gate **不通過**；🟡 合計 ≥ 4 項亦視為 ❌（累積偏離即明顯偏離）。
- **墨水比例**（`inkRatioFirst`）只作 INFERENCE 級輔助觀察，⛔ 單獨據以判 ✅／❌。
- 👤 我的（非分析頁）：A2、V1、V2 以「設定卡結構」判（契約 §12.4），不要求 Primary Visual。
- **KPI 列欄數**（3 vs 4、手機 2×2）：與 `CLAUDE.md` v3 §00「固定 3 欄」的牴觸待客戶裁示（BACKLOG `CV1-DR-12`、契約 §22 W9）；裁示前本 Gate **不判定欄數**，現狀維持。
  - 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-117 Q1）**：📊 市場頁已裁示（`CV1-DR-12` 結案）——**桌機核心狀態 tile 恰 3 個**（市場位階／建議總持股水位／今日主要風險；更新為頁首主 CTA、不占 tile）、**手機 2＋1**；本 Gate 自此對 📊 市場頁**判定 KPI 欄數**（不符＝A1 ❌：骨架與核准線框不同）。客戶解釋「固定 3 欄是桌機核心狀態網格要求，不代表手機必須硬排 3 欄」記於 DEC-117，`CLAUDE.md` 不改。其他頁仍依各頁線框，裁示前不判。
- **線框待拍板點**（契約 §22 W1～W9）：未經客戶拍板者以現行呈現為準，⛔ 據以判 ❌。

## §3 必附截圖規格

| 項 | 規格 |
|---|---|
| viewport | **desktop 1440×900**、**mobile 390×844**（headless chromium；`tools/visual_fidelity/measure_app.js`） |
| 範圍 | 每個 viewport 各一張**第一屏**＋一張**全頁**（viewport 拉高到 scrollHeight） |
| 狀態 | **冷啟動**＋**已載入**兩態（已載入＝`harness_app.py` 夾具或真資料；註明哪一種） |
| 對照 | 同頁 blueprint 截圖（`measure_mock.js`，desktop 框＋phone 框）**並排** |
| 檔案位置 | PR 描述直接貼圖，或 `docs/vnext/visual_fidelity/<phase>/`；檔名 `app_<page>_<state>_<1440\|390>[_tall].png`、`mock_<page>_<1440\|390>.png` |
| 大小 | **單張 < 300KB**（全頁長圖可縮放 25%～50%，或 PNG 256 色量化；範例 `docs/vnext/visual_fidelity/phase1_baseline/`） |
| 量測數據 | A／V 兩表＋關鍵量測值（全頁高、主要判讀句頂端、主卡高、Primary 高、外露字數、工程字樣次數） |
| 誠實標註 | 夾具 vs 真資料；Streamlit 版本（`requirements.txt` floor 未驗寫「1.56 floor 未驗」）；手機實機／Streamlit Cloud 未驗 |

- **Phase 1 baseline 例外**：`docs/vnext/visual_fidelity/phase1_baseline/` 的 app 截圖皆為**已載入**態（夾具），檔名不含 state 段（`app_<page>_<1440|390>[_tall].png`）屬例外；冷啟動 baseline 需於 Phase 3 Gate 重量（PR #970 §C 冷啟動量測只存於 commit `06a7a3e5`；BACKLOG `P1R-COLD-START-BASELINE`）。
- ⛔ 截圖不得含真實個人持股、Sheet ID、金鑰或 OAuth 資訊；用夾具或遮蔽。
- 截圖上的夾具數字是**示意**，PR 描述須寫明，⛔ 被引用為投資結論。

## §4 誰判定

1. **獨立 QA 組判 Gate**（不得是實作組；`CLAUDE.md` §-2 規則 3／4；v3「實作者不得自己驗收自己」）。
2. **AI 總管複驗**：至少抽驗 ❌／🟡 項與 A1、A2、A10、A11、V7 的截圖；⛔ 只轉述 QA 結論。
3. **結果寫進 PR 描述**（§6）與交付報告第 2 段。
4. **明顯偏離** → 不得標 complete；HANDOFF／BACKLOG 照實寫「Visual Fidelity Gate 未過」。

## §5 例外流程（開 Gate）

| 偏離性質 | 判定 | 處置 |
|---|---|---|
| 真資料／Streamlit／mobile 限制的合理調整（契約 §14.1） | 獨立 QA 判＋總管複驗 | PR 寫明理由與證據；🟡 登記 BACKLOG P2；❌ 須補修或改判為下一列 |
| 後續客戶裁示覆蓋 blueprint（DEC-105 2A、DEC-107 2A／3A、DEC-109 R12…） | 引用 DEC | 不算偏離；在檢查表註明 |
| 版面設計變更（區塊增減、骨架不同、動線不同、欄位增減） | `CLAUDE.md` §-1.5.D v3 §03-2 ① | **先出文字線框送客戶**（附總管推薦方案）；核准前不得標 complete |
| 技術上做不到（例：不動全站殼達不到 Q11） | 總管判 | 列最小必要改動與影響面；屬 IA／全站殼層變更 → 送客戶；否則內部拍板並在報告揭露 |

- ⛔ 以「tests 全綠」「mutation 全殺」「QA 0 BLOCKER」覆蓋 ❌。

## §6 Gate 結果記錄格式（PR 描述「Visual Fidelity」段；`.github/PULL_REQUEST_TEMPLATE.md` 同步）

```
## Visual Fidelity（UI PR 必填；非 UI PR 寫「N/A：理由」）
- 截圖（desktop 1440×900／mobile 390×844；第一屏＋全頁；冷啟動＋已載入）：<連結或貼圖>
- blueprint 並排：docs/vnext/d25_wireframes/<page>.html
- 資料來源：夾具 / 真資料；Streamlit 版本：<x.y.z>（1.56 floor 是否實驗）
- 三層：第一眼＝_；第二眼＝_；第三層＝_
- 客戶 11 項：A1 _｜A2 _｜A3 _｜A4 _｜A5 _｜A6 _｜A7 _｜A8 _｜A9 _｜A10 _｜A11 _
- 補充 V1～V11：V1 _｜V2 _｜V3 _｜V4 _｜V5 _｜V6 _｜V7 _｜V8 _｜V9 _｜V10 _｜V11 _
- 關鍵量測：全頁高 _／_；主要判讀句頂端 _；主卡高 _；Primary 高 _；外露字數 _；工程字樣 _
- 判定：PASS / FAIL；判定者：獨立 QA <組>；總管複驗：<抽驗項>
- 偏離與處置（契約 §14.1／本檔 §5）：<逐項>
- 未驗：手機實機 / Streamlit Cloud / 1.56 floor
```

## §7 工具與邊界

- 工具＝`tools/visual_fidelity/`（`harness_app.py`、`measure_app.js`、`measure_mock.js`、`mock_ink.js`、`count_eng_words.js`、`summarize.py`、`README.md`）。
- ⛔ 工具不得被 `app.py`、`src/**`、`shared/**`、`tests/**` import；檔名不以 `test_` 開頭、不在 `tests/`（`pytest.ini` `testpaths = tests`，不收集）；harness 假資料只在本 process monkeypatch，不寫 repo／Sheet、不打外部 API。
- 工具驗不到：手機實機（iOS／Android）、Streamlit Cloud、`requirements.txt` floor 實機行為、付費 AI 生成後狀態；Gate 報告照實寫「未驗」。

## §8 例外流程使用紀錄（append-only）

| 日期 | 事項 | 走的例外列 | 證據／狀態 |
|---|---|---|---|
| 2026-10-30 | 站殼間距 D7=B（nav4 上留白 96→72px＋隱藏 style-only 空容器；四頁第一屏統一上移） | §5「版面設計變更」列：整體 layout 變更 → 送客戶（附推薦方案 R）→ **客戶裁示 D7=B（DEC-116）**；核准後施工 | 四頁×1440／390×cold／loaded 前後截圖 `docs/vnext/phase3_shell/`；量測＝`PHASE3_SHELL_SPACING_MEASUREMENT_2026-10-30.md` §8。**Gate 判定：待獨立 QA（執行組不自判）**；未驗：1.56～1.58、真資料載入態、實機／Cloud |
| 2026-10-30 | **📊 市場頁手機 Primary Visual 位於第一屏下方**（Phase 4；DEC-117 Q7 客戶核准「合理 mobile exception」） | **§5 第 2 列**（後續客戶裁示覆蓋：引用 DEC-117 Q7）——**不算偏離、不計 🟡**（AI 總管判定 U3，線框 §10.6；⛔ 混用第 1 列） | **登記（施工前）**：成立條件（三條，任一不成立＝❌）＝(1) 手機第一屏優先序 今日結論 > 核心狀態 > 是否需行動 > Primary；(2) ⛔ 為塞主圖擠出結論或核心狀態；(3) Primary 緊接 L1 決策區、⛔ 被 L2／L3 插隊。例外只豁免 Primary：⚡ bar（或「⬜ 無警示來源」）仍須在手機第一屏（線框 §10 C1-10）。桌機不適用。實作後須附 390×844 第一屏＋全頁截圖與區塊 y 量測；未驗：手機實機／Cloud／1.56～1.58 |
| 2026-10-30 | **📊 市場頁手機「⚡ 需要處理」位於第一屏緊接之後**（Phase 4 P4-1；DEC-118 問題 1=A 客戶核准 mobile exception） | **§5 第 2 列**（後續客戶裁示覆蓋：引用 DEC-118）——不算偏離、不計 🟡；**成立條件**（任一不成立判 ❌）：① ⚡ bar 緊接在 3 核心狀態之後，中間不得有任何 L2／L3 內容；② 手機 390×844 第一屏必含今日結論＋核心狀態（位階｜水位列）——📌 但書（2026-10-30 QA 第二輪；依 DEC-118 送審題幹附錄 D1 缺點，客戶知情）：**partial（報告含真錯誤）態**核心狀態列可被真錯誤推出第一屏，但**今日結論仍須在第一屏內、真錯誤緊接結論**；**report（乾淨報告）態**位階｜水位列底部「🔍 查看依據」標題列約 36～37px 超出第一屏，屬接受的邊界（標題與值在第一屏內）；③ DEC-117 Q7 三條件照舊 | 守衛：`tests/test_p4_1_market_first_screen.py`（順序與「⚡ 緊接 tile」）；實量 `docs/vnext/phase4_market/p4_1/`（P4-3 正式 Gate 再判） |

| 2026-10-31 | **📊 市場頁正式 Visual Fidelity Gate 判定（Phase 4 P4-3；基準 main `228b9fa9`）** | §5 第 2 列（Q7／DEC-118 例外條件實測）＋ §2 合計規則 | **判定：❌ FAIL；Stage 維持「未完成」**（不得標 complete、BACKLOG `P1R-PHASE4-MARKET` 不得結案）。**❌ 3 項**：A5（桌機全頁高 3061／blueprint 1517＝2.018× > 2×）、A6（手機 Primary 圖高 220 > 契約 Q3 ≤140，+57%）、A8（外露 >32 字非客戶原句 3 塊）；**🟡 4 項**（A4、A10、A11、V3）觸發「🟡 ≥4 視為 ❌」。**PASS**：A1、A2、A3、A7、A9、V1、V2、V4～V11。**例外條件實測**：Q7 三條件成立（結論四態皆在手機第一屏、AI 行→Primary 間距 0px、無 L2／L3 插隊）；DEC-118 條件 ①③ 成立，② 的 report 態 36～37px 邊界與 partial 態依但書成立（不計 🟡）。**判定者＝本批執行 AI（單組、非實作組）；Gate §4 要求的獨立 QA 組與總管複驗尚未發生**。證據＝`docs/vnext/phase4_market/p4_3/GATE_REPORT.md`（量測 JSON＋截圖＋腳本）；夾具、Streamlit 1.59.2＋floor 1.56.0 各量一份（結論相同）；未驗：真資料、手機實機、Cloud、1.57～1.58。待客戶裁示 3 題（頁面長度／手機主圖高／四項 🟡 是否接受），見 HANDOFF 與報告 §11 |
