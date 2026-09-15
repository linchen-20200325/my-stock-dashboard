# `docs/v2/` — IA v2 / 戰情室重寫的**文件存檔**（2026-09-15）

> **給三分鐘後就要接手的人（或未來的 AI）。先讀完這一頁再讀任何一份文件。**
>
> 本目錄是**存檔**，不是規格庫。它把一批原本只活在暫存容器（scratchpad）裡的文件
> 收進 git，**因為那個容器閒置後會被回收，檔案會全部消失**。
>
> **本次入庫是零程式碼變更**：只新增 `.md` / `.html` / `.js` 文件檔，
> **沒有動任何一行 `.py`、沒有動 `CLAUDE.md` / `PROCESS.md` / `requirements*.txt` / `.github/`**。

---

## 0. 現在停在哪（⚠️ 先看這格）

| | |
|---|---|
| **已交付** | **階段 A —— 問題分級**（`stage1/PROBLEM_TRIAGE.md`，2026-09-15） |
| **下一步** | **等客戶說「繼續」才進階段 B**。⛔ 客戶沒說「繼續」之前，**不要開工** |
| **階段 B 的內容** | 四份規格書：`INDICATOR_SPEC` / `DECISION_RULES` / `DECISION_FLOW` / `TEST_CASES` |
| **階段 B 的節奏** | **一次只交一份**（客戶指定，不是四份一起丟） |
| **本次入庫的 commit** | 僅新增 `docs/v2/**`，零程式碼變更、零行為變更 |

⚠️ **「等客戶說繼續」這條同時受 `CLAUDE.md §-1` 拘束**：沒有指派、沒有實際 bug 觸發 → **停手等指令**，
不得拿本目錄裡任何一份「待辦 / 待修 / 待查」清單當成主動動工的授權。

### 📌 有**兩組「四份文件」**，⛔ 不是同一批改名

這是最容易搞混的一點，先講清楚（決策者：AI 總管，2026-09-15）：

| | 出處 | 四份叫什麼 | 現況 |
|---|---|---|---|
| **甲** | **客戶母法**指定的四份**子法** | `CONSTITUTION` / `DATA_DICTIONARY` / `UI_SPEC` / `ACCEPTANCE` | **從未被建立**（`audit/wf_fund_archive.md` 實測：四份全部 0 命中，且 `docs/v2/` 當時整個不存在 —— 本次入庫是這個目錄的**首次建立**） |
| **乙** | 客戶 **2026-09-15 另一次指派**的**階段 B** | `INDICATOR_SPEC` / `DECISION_RULES` / `DECISION_FLOW` / `TEST_CASES` | **尚未開始**（等客戶說「繼續」） |

⛔ **甲與乙是不同層級、不同時間、不同用途的兩批東西，不是同一批換了名字。**
看到其中一組的名字時，先確認講的是哪一批再往下讀。

⚠️ `wf_fund_archive.md` 另自標**一個沒查證的點**：既然 `docs/v2/ACCEPTANCE.md` 不存在，
客戶讀到的那份 ACCEPTANCE **實際來自哪裡，該組沒有查** —— ⛔ 不得當成已查清。

---

## 1. 這批是什麼 · 四個子目錄各是什麼

| 目錄 | 是什麼 | 能不能當成「講好的規格」？ |
|---|---|---|
| **`stage1/`** | 本輪文件工程的交付（**4 份**）：資料血緣、指標 SSOT、階段一稽核、問題分級 | ⚠️ 是**產出**，但**全部單組、未複驗**（見 §2） |
| **`spec/`** | **規格與白皮書**：S1 系列（資料白皮書、指標 SSOT、狀態矩陣、持股模型、合規文案、權限 PII）＋ S2 系列（PRD / UI Spec / Eng Spec） | ⚠️ 是**草稿規格**，**客戶尚未逐份拍板** |
| **`audit/`** | **稽核軌跡**（合規掃描、紅隊、秘密掃描、血緣缺口…）—— **查證紀錄，不是規格** | ⛔ **不是規格**。詳見 `audit/README.md` |
| **`wireframe/`** | **線框稿的原始碼**（HTML 外殼 ＋ 各頁 `wf_*.js` ＋ 線框說明文件） | ⚠️ 線框＝**要送客戶拍板的草稿**，不是已核准的畫面 |

**規格 vs 稽核軌跡的差別（一句話）**：
**規格**說「**應該長什麼樣**」（是主張、要被拍板、被實作、被驗收）；
**稽核軌跡**說「**當時實際查到什麼**」（是證據、附量測日、只能被引用不能被實作）。
把稽核軌跡當規格照做，等於把「現況有這個問題」誤讀成「我們決定要這樣做」。
完整說明見 **`audit/README.md`**。

---

## 2. ⚠️ 全域限制（**必讀，引用本批任何一句之前先看這格**）

1. **本批所有文件皆為單組產出 —— 沒有任何一份「它自己」被第二組複驗過。**
   本組實測（量測日 2026-09-15，關鍵字 `未經第二組` / `單組產出` / `（單組）`）：
   33 份 `.md` 中有 **26 份在檔內明文自陳**「單組 / 未經第二組複驗」；
   其餘 7 份（`stage1/STAGE1_AUDIT.md`、`spec/S1-6_COMPLIANCE_COPY_GUIDE.md`、
   `audit/S1-3B_REDTEAM.md`、`audit/SECRET_SCAN_CROSSCHECK.md`、`wireframe/UI-B/UI-C/UI-E_*.md`）
   **沒有這句自陳，本組也未逐份確認其複驗狀態** —— ⛔ 不得把「沒寫」讀成「有驗過」。
   ⚠️ **一個必須分清的地方**：`audit/` 裡有幾份**本身就是對另一份文件的第二組複驗**
   （`COMPLIANCE_CONTROLFLOW_E` 複驗丁組、`SECRET_SCAN_CROSSCHECK` 交叉驗證
   `SECRET_SCAN_HISTORY`、`STATE_SEMANTICS_QA2` 獨立重跑、四份 `*REDTEAM*` 紅隊稿）。
   **被複驗的是「被它稽核的那一份」，不是「它自己」** —— 紅隊報告本身仍是單組結論。
2. **唯一經第二雙眼睛看過的是 `stage1/PROBLEM_TRIAGE.md` 的 `P1-01`**
   —— 流程是「稽核組 AST 掃描發現 → **總管親自實跑** `f(None, None, None)` 拿到真實輸出」
   （見該檔 §0.3 與 §1 的 P1-01 列）。
   ⚠️ **據實標明**：本存檔組收到的派工單寫的是「`PROBLEM_TRIAGE` 的**緊急級**經總管複驗」，
   但**該檔本身只對 `P1-01` 一條做此宣稱**（§4.2 逐字：「除 P1-01 的函式回傳值（總管實跑）外，
   都繼承這個限制」）。**以文件本身為準**；派工單的說法涵蓋面較寬，未經查證。
3. 🔴 **沒有任何一份跑過實機 Streamlit。**
   所有「畫面會顯示 X」「使用者會看到 Y」的敘述，**都是讀 render 函式推導出來的，沒有一張截圖**。
   （`PROBLEM_TRIAGE §4.2` 引用 `INDICATOR_SSOT §9.3 U-22` 與 `STAGE1_AUDIT §8.2 #4` 的自陳。）
4. ⛔ **不得因為被引用第二次就升格成事實。**
   一份單組結論被另一份文件引用，**只代表它被引用過**，不代表它被驗過。
   依 `CLAUDE.md §-2` 規則 6，未經第二組驗證的全稱句只能當**待驗事項**，
   **不得作為後續動作的前提**，也**不得寫進 commit message / PR 描述當成已完成的事實**。
5. **每一份文件自己的「我沒查到的」章節，比它的結論更重要。**
   例：`INDICATOR_SSOT §9`（U-1~U-24）、`DATA_LINEAGE §F`（F-1~F-7）、
   `STAGE1_AUDIT §8`（12 條）—— 合計 40+ 條待查事項，**`PROBLEM_TRIAGE` 一條都沒有分級**
   （它們是「不知道」，不是「問題」）。

---

## 3. 客戶明令的四條約束（貫穿本批全部文件）

1. ⛔ **不得動程式碼。** 本批是純文件工程；入庫時同樣零程式碼變更。
2. ⛔ **不得發明不存在的資料源。** 任何指標都要能指回真實 endpoint 與可回溯算式
   （對齊 `CLAUDE.md §1` Fail Loud、§2.1 SSOT）。
3. ⛔ **不得產生直接買賣建議。** 文件中凡出現行動語（加碼／減碼／買進／停利／持股 %），
   一律是**引用現行 code 的字串常數作為稽核軌跡**，並逐處標註。
4. ⛔ **缺失值不得填 0。** 缺值要有第三態（顯式標註／raise／帶 `is_imputed` 旗標），
   不得用 `0` 或 `''` 冒充觀測值（對齊 `CLAUDE.md §1`）。

---

## 4. 🔴 未解的承重事項（**客戶還沒回答**）

**`stage1/PROBLEM_TRIAGE.md` §4.3 第 3 點的那一題：症狀 vs 根因。**

> `P1-02` / `P1-03` / `P1-06` / `P2-03` / `P2-04` / `P2-10` 在**機制上都是同一個病**
> ——「**缺值用 `0` / `''` 表達，沒有第三態**」。
> 該檔按**檔案與消費端**拆開列（因為修的時候是分開修的）；
> **但如果客戶要的是「幾個根因」而不是「幾個症狀」，這份分級要重做。**

**這題客戶尚未回答。** 在客戶回答之前：

- ⛔ **不得**把現行的「緊急 6 / 重要 19 / 登記 25，合計 50」當成已定案的分級；
- ⛔ **不得**拿現行優先序當**施工順序** —— 它是「**先看哪個**」的順序，
  排序時**完全沒有考慮修復成本**（同檔 §4.3 第 4 點）；
- ✅ 要推進的話，先把這題送回客戶（依 `CLAUDE.md §-1.5` 第二條：業務規則取捨屬請示白名單，
  且須**附總管推薦方案**，不得只丟兩個選項）。

**另外 7 條最可能被推翻的判斷**：該檔 §0.4（2 條客戶點名為緊急、本組判為其他級）
＋ §4.1（5 條來源互相矛盾時的裁決）—— **覆核請從這 7 條開始。**

---

## 5. 線框稿：成品在 Artifact，**來源在這裡**

- **已發布的成品**（可直接開來看的互動線框）在 **Artifact** 上，那份是安全的、不會隨容器消失。
- **但來源檔沒存就會消失** —— 這正是 `wireframe/` 存在的理由。
- **組裝產物 `warroom_ia_v2_full.html`（866 KB）刻意不入庫**，因為它可以從
  外殼 `warroom_ia_v2.html` ＋ 各 `wf_*.js` **完整重建**（本存檔組已實測重建並逐位元比對）。
- **重建步驟、實測驗證結果、以及 `wf_onboarding.js` 的特殊狀況**，
  全部寫在 **`wireframe/README.md`** —— 動線框稿之前請先讀那一份。

---

## 6. 檔案清單（49 個檔，約 3.30 MB；量測日 2026-09-15）

### `stage1/` — 本輪文件工程交付（4 檔）
`DATA_LINEAGE.md` · `INDICATOR_SSOT.md` · `STAGE1_AUDIT.md` · `PROBLEM_TRIAGE.md`

📌 **為什麼是 4 份不是 5 份（2026-09-15 總管釐清，已結案）**：
客戶**最初**要的五份是 `DATA_LINEAGE` / `INDICATOR_SSOT` / **`DECISION_RULES`** /
**`DECISION_FLOW`** / **`TEST_CASES`** —— **後三份屬階段 B，尚未寫**（見 §0 乙表）。
本目錄實際的 4 份 ＝ 前兩份 ＋ 後來追加的 `STAGE1_AUDIT`（稽核）與 `PROBLEM_TRIAGE`（分級）。
⇒ **沒有「漏存的第 5 份」** —— 缺的三份是**還沒產出**，不是**沒存到**。

### `spec/` — 規格與白皮書（9 檔）
`S1-1_DATA_WHITEPAPER.md` · `S1-2_METRIC_SSOT.md` · `S1-4_STATE_MATRIX.md` ·
`S1-5_HOLDINGS_MODEL.md` · `S1-6_COMPLIANCE_COPY_GUIDE.md` · `S1-7_PERMISSIONS_PII.md` ·
`S2-PRD.md` · `S2-UI_SPEC.md` · `S2-ENG_SPEC.md`

### `audit/` — 稽核軌跡（16 檔 ＋ 本目錄的 `README.md`）
`COMPLIANCE_SCAN_A/B/C.md` · `COMPLIANCE_BLAST_D.md` · `COMPLIANCE_CONTROLFLOW_E.md` ·
`DRAFT_GAP_AUDIT.md` · `PB_LEVEL_TRACE.md` · `SECRET_SCAN_HISTORY.md` ·
`SECRET_SCAN_CROSSCHECK.md` · `STATE_SEMANTICS_QA2.md` ·
`S1-3B_REDTEAM.md` · `S1-3B_REDTEAM_B.md` · `S1-3B_REDTEAM_C.md` · `S1-4_REDTEAM.md` ·
`wf_fund_archive.md`

### `wireframe/` — 線框稿原始碼（17 檔 ＋ 本目錄的 `README.md`）
外殼：`warroom_ia_v2.html`｜
資料：`wf_page_today.js` · `wf_page_find.js` · `wf_page_inspect.js` · `wf_page_hold.js` ·
`wf_page_why.js` · `wf_page_fund.js` · `wf_global.js` · `wf_questions.js` · `wf_onboarding.js`｜
組裝：`assemble.js`｜
說明：`S1-3_IA_WIREFRAME.md` · `S1-3B_FULL_DRAFT_SPEC.md` ·
`UI-A_page_today_wireframe.md`（⭐ 只有 7 行，但裝著**文案瘦身的原始量測** —— 見 `wireframe/README.md`） · `UI-B_wireframe.md` · `UI-C_wireframe.md` · `UI-E_page3_wireframe.md`

---

## 7. 本存檔組做了什麼 / 沒做什麼（依 `CLAUDE.md §-2` 規則 6 據實揭露）

**做了**：
- 建 `docs/v2/` 四層目錄、從 scratchpad **原樣複製** 46 個檔（**逐檔 sha256 比對，46/46 相符，0 不符**）；
- 寫本檔與 `audit/README.md` / `wireframe/README.md` 三份索引；
- **實測重建**線框稿全檔並與既有組裝產物逐位元比對（結果見 `wireframe/README.md`）;
- 對入庫檔案跑一次金鑰樣式掃描（`AIza…` / `sk-…` / `ghp_…` / PEM / JWT）——
  唯一命中為 `audit/SECRET_SCAN_CROSSCHECK.md` 內**引述的測試 fixture 佔位字串**
  （該檔自陳 PEM 本體為 `\nx\n`、5 字元、無金鑰材料），**非真實憑證**。

**沒做**：
- ⛔ **沒有改任何一份文件的內容一個字** —— 全部是原樣複製；
- ⛔ **沒有驗證任何一份文件的結論是否正確** —— 本組是存檔組，不是稽核組；
- ⛔ **沒有跑實機 Streamlit**、沒有跑專案測試、沒有動任何 `.py`；
- ⛔ **沒有** 對 §2 那些單組結論做第二組複驗 —— 它們入庫後**仍然是待驗事項**。
