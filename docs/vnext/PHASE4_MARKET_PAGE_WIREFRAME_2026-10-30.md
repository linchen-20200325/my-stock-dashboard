# Phase 4 步驟 0｜📊 市場頁：現況重測＋能力盤點＋文字線框＋客戶決策表

- **狀態**：**草稿 rev1，待客戶拍板**（出處：Migration Plan §1「Phase 4：先出文字線框（含 W2、W3、W9、版面差異、總管推薦）→ 客戶拍板 → 寫 UI code」；`CLAUDE.md` §-1.5.D v3 §03-2 ① 草稿先行；契約 §22）。**本檔核准前不得寫任何 Phase 4 UI code**（不得改 `src/`、`tests/`、`app.py`）；客戶不裁示的項目依各題「不裁示預設」（§6）。
- **日期／基準**：2026-10-30；main `15071a47`（Phase 3 含站殼 D7=B 已合併；`src/`、`tests/`、`app.py` 與 main 相同，本批只新增 `docs/`）。量測日一律 2026-10-30，不寫行號（`CLAUDE.md` §8.2.A.0 規則 1）。
- **決策來源**：W2／W3／W9 清單＝契約 §22（客戶 DEC-109 之後的總管改判原則）；Phase 3 已裁示約束＝DEC-115（D1a／D1b／D3／D5／D6／D8／D10）、DEC-116（D7=B）；市場頁既有客戶裁示＝DEC-081（Q2-1／Q2-2）、DEC-092（Q2 均線聲明、Q3）、DEC-105（1A／2A／3A＋指路）、DEC-109（Visual Budget、第一屏五問、Top-N、Missing Contract）；方案設計、推薦、API 對映、動檔預測＝**AI 總管內部（DEC-110 同層）**，客戶可推翻。
- **上位**：`CLAUDE.md` > `PROCESS.md` > `PROJECT_RULES.md`＋`docs/governance/*` > 最新有效 DEC > Presentation Contract／Migration Plan／Visual Fidelity Gate > 本檔。本檔**不改**契約與 DEC 一個字；在留白處提方案，與既有客戶措辭牴觸處一律列為決策題。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：本檔由**單一撰寫組**產出，**未經第二組獨立驗證**。標記：**FACT**＝本批讀碼／實跑可重現；**INFERENCE**＝由事實推出；**RECOMMENDATION**＝總管推薦，待客戶裁示。§2 的數字來自**夾具**（`tools/visual_fidelity/harness_app.py`，Streamlit 1.59.2，沙箱無外網）——**真資料態、floor 1.56、手機實機、Streamlit Cloud 全部未實測**；§4 的 px 數字來自**靜態 HTML 示意**（`compact.py` 實際產出的元件，Streamlit 元素間距以 16px 估算），**不是** Streamlit 渲染真值。所有「全部／只有／沒有」的全稱句是待驗事項，尤其 §3 的「承接完整度」，會被獨立 QA 複驗。示意文字與數字一律標 ※示意，⛔ 不得被引用為投資結論。

---

## §0 GitHub Verification Gate（FACT，2026-10-30 實查）

| 項 | 結果 |
|---|---|
| main SHA | `git fetch origin` 後 `origin/main`＝`15071a4783f681d6a28668bc7343a326f2108316`；本分支 `ccr-c8ef17de-9tw7yt` 與其相同（開工前 `git status` 乾淨） |
| Open PR | **0**（GitHub MCP `list_pull_requests state=open` 回 `[]`） |
| 相關 branch（`git branch -r`） | `origin/ccr-c8ef17de-9tw7yt`（本分支）、`origin/ccr-6eace3b6-0gglrs`、`origin/ccr-fa5b6ded-9rhvoj`、`origin/ccr-phase2-step1`、`origin/claude/stock-dashboard-handoff-g9dtm0`、`origin/auto/recalibrate-20261001`、`origin/data`、`origin/docs/newui-stage-a-inventory`、`origin/v2`；與 Phase 4 市場頁直接相關者：無（未逐一比對各分支與 main 的差異，故不宣稱其餘分支「無相關內容」） |
| 守衛基線（以當時 main 實跑） | `pytest tests/test_uim_revert_chain.py tests/test_nav1_revert_chain.py tests/test_xvext_revert_chain.py tests/test_batch_z60.py tests/test_page_market.py tests/test_market_blocks.py tests/test_uim_market_page.py tests/test_c3_layering_guard.py tests/ui_v2` → **1348 passed、1 skipped、2 deselected**（本機單組；不等於 CI） |
| 本批 diff | 僅 `docs/`（含 `docs/vnext/phase4_market/` 的量測腳本、截圖、離線示意）；`git diff --stat -- src tests app.py requirements.txt` 為空（收尾前複查，見 §8） |

---

## §1 範圍與不做清單（Scope Guard）

**本批做**：(1) 以當時 main 重測 📊 市場頁現況；(2) 能力盤點＋Old→New 對映；(3) 文字線框（桌機＋手機，冷啟動／已載入／缺資料）；(4) 客戶決策表（含 W2、W3、W9、CV1-DR-12）；(5) 風險／守衛預估；(6) 文件落盤。

**⛔ 不做**（契約 §17 守恆聲明＋Plan §9）：任何 UI code、新資料源、新 schema、改公式／門檻／TTL／投資語意、Risk Cap 公式與數字顯示、EPS×PE production rule、台股／國際趨勢正式定義（維持 `⬜ 尚未定義`）、接新 AI／Digest／Brain（Phase 7）、改 `PAGE_LABELS`／導覽殼／legacy、動 `page_today.py`、`src/ui/tabs`→`views` 改名、新增或刪除頂層頁（DEC-109 十）、提高 Streamlit floor。W4～W8 不在本頁（Phase 5～7）。

---

## §2 現況重測（FACT；夾具、Streamlit 1.59.2、main `15071a47`）

### 2.1 方法與限制（先讀）

- 工具：`tools/visual_fidelity/harness_app.py`（以 `runpy` 跑**真 `app.py`**，L3 service 換成假資料）＋本批新增 `docs/vnext/phase4_market/baseline/measure_market.js`（Playwright，`/opt/pw-browsers` chromium）＋既有 `measure_app.js`、`count_eng_words.js`。viewport 1440×900／390×844；狀態＝**loaded**（`?p=market`，預置已載入 session）、**cold**（`&cold=1`，不預置 session）、**report**（`&report=1`，另加一份全成功更新報告）。
- ⚠️ **harness 的 cold 態不是真冷啟動**：L3 的 `get_macro_regime`／`get_allocation` 等仍被假資料取代，所以 cold 態市場位階仍顯示「多頭／🟢 運作中」；真冷啟動下該卡的內容未驗。
- 沙箱無外網；真資料（真實 FRED／TWSE／Yahoo 回應、真實缺漏、真實過期）**未實測**；載入態＝夾具。
- 截圖：`docs/vnext/phase4_market/baseline/`（第一屏 4 張＋全頁縮圖 2 張，皆 <300KB）；原始量測 JSON 同目錄 `_measure_*.json`。⚠️ 截圖中 `⬜` 在 headless 字型下常畫成空框——是量測環境字型問題，不是畫面本身（`⬜` 字元在 DOM 內）。

### 2.2 區塊順序與高度（loaded；y＝距頁面頂，H2 起於 y=135，D7=B 已生效）

| # | 區塊（現況順序） | 桌機 1440（主欄 980） | 手機 390（內寬 358） |
|---|---|---|---|
| 1 | H2「📊 市場」＋副標＋狀態行（更新時間／危險度覆蓋）＋「逐項資料日：尚未提供」行 | H2 y135 h59；副標 y210；狀態 y249；資料日行 y290 | 同；狀態行 2 行、資料日行 2 行（y249～361） |
| 2 | **Hero 4 欄**：市場位階｜建議總持股水位｜今日主要風險｜更新（`st.columns(4)`） | y329 **h641**（4 欄各寬 233，等高） | y377 **h1402**（四卡堆疊：208／232／386／529） |
| 3 | 一行 AI 佔位＋資料狀態 chip（`HERO_AI_PLACEHOLDER`／`HEALTH_CHIP`） | y985 h22 | y1795 h45 |
| 4 | 今日結論（標題 h37＋句子，客戶 Q2-1） | 標題 y1024、句子 y1077 | 標題 y1855、句子 y1937 |
| 5 | ⚡ 需要處理（整塊容器：tile＋「🔍 查看依據」） | y1144 **h313** | y2055 h313 |
| 6 | 圖 A｜圖 B（兩欄；圖 B 5 張 `st.line_chart`） | y1473 **h2542**（兩欄等高） | y2385 **h3524**（A h812＋B h2695 堆疊） |
| 7 | 圖 C｜圖 D | y4031 h698 | y5925 h1268（C h246、D h1005） |
| 8 | 「以下為可展開區塊」＋11 個預設收合 expander（各 h40） | y4745～5343 | y7208～7806 |
| — | **全頁高** | **5575** | **7966** |

- **FACT 6 張圖全部是 350px 高的原生 `st.line_chart`**（桌機寬 450、手機寬 326）：圖 A 1 張、圖 B 5 張；**第一屏（0～900）內 0 張圖**（圖 A 首張圖 y=1598，手機 y=2510）。
- **FACT 冷啟動（harness cold）**：全頁高桌機 3060／手機 4404；Hero 桌機 h618（手機四卡 208／232／213／506）；結論句同樣在第一屏之外。
- **FACT 更新報告態（`&report=1`）**：桌機 5631／手機 8037（多出一個報告區塊，Hero 以下整體下移約 56～71px）。

### 2.3 欄數、hover-only、Missing 呈現、工程字樣（FACT）

| 項 | 現況 |
|---|---|
| 欄數 | Hero＝`st.columns(4)`（桌機 4 欄；手機 Streamlit 自動塌成 1 欄堆疊，**不是** 2×2）；圖區＝`st.columns(2)`（兩列：A｜B、C｜D）。`test_market_blocks` 以 AST 釘 `st.columns(4)`（T23，待 W9）。 |
| hover-only 資訊 | **1 處（loaded）**：市場位階卡的 `title=`「位階的出處：本頁一律取自 L3 總經契約 `get_macro_state()`」（`page_today.V2_HOVER_ONLY_FACTS`）；cold 態另有「今日關鍵」卡的 `title=`（「尚未載入 —— 未評估 ≠ 無異常｜為什麼沒有：冷啟動 session」）。兩者在手機無 hover，屬契約 §11「⛔ 資訊只活在 `title=`」要在 Phase 4 搬進摺疊者。 |
| Missing／unavailable | 皆以文字＋`⬜` 呈現，**沒有任何 0／中性冒充**（水位卡＝`⬜ 尚未核准／無法判定`；趨勢結論＝`⬜ 尚未定義`；圖 C＝「需先核准…不畫任何圖形」；圖 D 的「是否惡化」每列都重寫一次 `⬜ 尚未定義`——重複 Missing，契約 §8-7 要寫一次）。未載入＝灰字、真錯誤＝紅（`st.error`）。 |
| 工程字樣（`count_eng_words.js`，可見文字，`&report=1`） | `Gate`×4、`C2b`×2（皆客戶自訂措辭例外：Q2-2「獨立顯示待 C2b＋RC-VISIBILITY Gate」）、`warroom`×1（位階卡「生效分支 warroom」，契約 §18 點名）；位階卡標題帶「（總經契約）」。 |
| 摺疊入口 | 17 個 expander：6 個「🔍 查看依據」（水位、風險、⚡、圖 A、圖 B、圖 D；圖 C 是常駐 caption 不是 expander）＋11 個具名 L2／L3（位階為什麼／五桶摘要／風險上限為什麼／指標明細（16 項）／台股盤勢／國際市場／總經景氣／籌碼／研究中／資料來源與完整度／問 AI），全部預設收合。 |
| 互動／gate | 更新 form（`single_submit_form`：模式 radio＋🚀 鍵）；L2 內 4 個 checkbox gate（台股走勢圖、ADL、國際走勢圖、籌碼先行指標）；圖 A／圖 B 預設直接畫（無 gate）。 |

### 2.4 與契約量化上限／Gate 的現況差距（INFERENCE，單組、夾具；分母 blueprint＝契約 §19 Q12 的 mockup contentH 1517／2480，量測基準不同，僅供量級判斷）

| 檢查 | 現況 | 上限／判準 | 預估判定 |
|---|---|---|---|
| Q11 主要判讀句頂端（相對 H2） | 桌機 **+942**（cold +919）、手機 **+1802**（cold +1607） | 桌機 ≤+200、手機 ≤+260 | ❌ |
| A2／B1 Primary 在第一屏 | 0 張圖在第一屏（桌機圖 A 標題 y1489、手機 y2401） | 恰 1、header＋圖上緣在第一屏 | ❌ |
| A6 圖大小 | 6 張皆 350px | Primary ≤220／140；mini ≤96 | ❌（+59%／+150%） |
| A4／A5 卡高與空白 | Hero 4 卡等高 641（桌）；手機 208／232／386／529；同列圖 C 欄下方有大片空白（見 `app_market_loaded_1440_tall_x0.4.png`） | tile 96～160、同列差 ≤16、無 >120px 空洞 | ❌ |
| Q12 全頁高 | 5575／7966（loaded）；3060／4404（cold） | ≤1.3× blueprint ✅、≤2× 🟡、>2× ❌ | loaded ❌（約 3.7×／3.2×）；cold 桌 ❌邊界（≈2.0×）／手 🟡 |
| Q10 第一屏可見字（粗估） | 桌 568、手 224 | 桌 ≤420、手 ≤380 | 桌 🟡/❌（+35%）；手 ✅（但手機第一屏被卡高吃掉） |
| A10 主 CTA 第一屏 | 桌機 ✅（🚀 y507）；手機 ❌（y1428） | 兩 viewport 第一屏內 | 🟡 |
| A9 Missing | 0／中性冒充＝0 次；未載入灰、錯誤紅 | — | ✅（但圖 D「是否惡化」每列重複＝🟡） |
| V10 工程字樣 | 非客戶例外者 ≥1（`warroom`、「（總經契約）」） | 外露 0 | 🟡 |
| V11 hover-only | 1（loaded）／2（cold） | 0 | 🟡 |

> 未量：A8（外露 >32 字非客戶原句的段數；`summarize.py` 只量 >80 字＝3 段）、V3／V4 的精確計數（需人工對照）。以上預估由**獨立 QA** 做正式 Gate 判定，本檔不自判。

---

## §3 能力盤點（Capability Inventory）：Old → New 對映

> **讀法**：「現況」＝本批以 main 讀碼＋瀏覽器重測所見；「新位置」＝**推薦方案 R**（§6 各題皆採推薦：Q1=B、Q2=A′、Q3=A、Q4=P-B、Q5=B、Q6=A、Q7=A）下的去向。層級 L1＝第一屏外露、L2＝第一屏之下／收合、L3＝證據摺疊（預設收合）。「風險」欄的 ⚠ 表示該列有**資訊形式改變**，已在 §6 列為決策題或「已依契約」清單，不靜默刪。
> **全稱句聲明**：本表是單組讀 `page_market.py`／`_market_blocks.py`／`page_today` 被呼叫的 builder 與瀏覽器所見整理而成，**不證明「已涵蓋所有能力」**；漏列風險由獨立 QA 以 `INTERACTION_COVERAGE_MATRIX`／既有測試清單對照。

### 3.1 頁首與狀態

| ID | 現況能力／資訊 | 新位置 | 資訊保留方式 | 風險 |
|---|---|---|---|---|
| P-01 | H2「📊 市場」（`PAGE_TITLE`）、副標（`PAGE_SUBTITLE`，客戶原句） | L1 頁首，字不改 | 原樣 | — |
| P-02 | 狀態行：`本頁更新於 HH:MM（按下更新的時間，不是資料日）`／`本次使用中尚未按過更新`＋`指標危險度覆蓋：N／M 項有資料` | 「覆蓋 N／M」→ **風險 tile 內 coverage chip**；更新時間句→ 更新動作列旁一句（短）；`REFRESH_TIME_NOTE`「按下更新的時間，不是資料日」全句→ 頁尾摺疊「來源」段 | 兩個事實都在；`coverage` chip 字樣依 `compact.META_KINDS`（值 ≤12 字） | ⚠ F-1：同一 chip 列「最多一顆非 readable 狀態 chip」（`compact` 驗證），故 coverage 不能與「資料日未提供」同列（§4.4） |
| P-03 | 「逐項資料日：尚未提供（現行契約沒有逐指標的資料日欄位）」＋（非預設 nav 時）「🩺 資料健康：請到…」 | L1 頁級 chip 列一顆 `⬜ 資料日未提供`（`asof_missing`，現有字樣 `DATA_DATE_NOT_PROVIDED`）；整句與資料健康指路→ 頁尾摺疊「來源／去哪補」 | 整句保留於摺疊；chip 為濃縮 | ⚠ 兩種「資料日」語意（逐指標資料日 vs 加權指數最後一根，見 P-10）**不得併成一顆 chip** |
| P-04 | 更新報告（`_render_report_guarded`→`today._render_refresh_report`；舊格式畫不出來時紅字＋清掉） | 位置不變：緊接更新動作列之下（X3／X10 文案寫「頁首更新鈕下方」，位置不動則不必改字） | 原樣 | 位置字樣是既有文案的承重詞，移位須同步 X3／X10／`report_pointer` |

### 3.2 Hero 四卡與其下

| ID | 現況 | 新位置 | 保留方式 | 風險 |
|---|---|---|---|---|
| P-05 | **市場位階卡**：標題「市場位階（總經契約）」、🟢 運作中徽章、五態主值、副行重複主值、「生效分支 warroom」、hover `title=`（位階出處）；卡外一句 `REGIME_SCOPE_CAPTION`「市場位階，不是台股趨勢」（DEC-105 2A，⛔ 映射偏多／中性／偏空） | L1 **tile**：label「市場位階」、主值＝五態原詞、say＝`REGIME_SCOPE_CAPTION`（逐字）、狀態徽章沿用 `UI_STATE_META`；「生效分支 warroom」、「（總經契約）」、hover 出處→ **tile「▸ 詳細」摺疊**（hover-only 退場，契約 §11） | 全部可點開取得；X1「市場位階：為什麼？」L2 expander 原樣保留 | tile 由 `build_verdict_tiles` 同一支輸出組成（不再呼叫 `today._render_one`，故不碰 `page_today.py`）；位階 `ui_state` 對應 tile 狀態 chip 的映射需單測 |
| P-06 | **建議總持股水位卡**：`WATER_TITLE`、`WATER_VALUE`「⬜ 尚未核准／無法判定」、`WATER_WHY`「正式 Risk Cap 尚未核准，此卡不顯示任何百分比。」、「風險上限：獨立顯示待 C2b＋RC-VISIBILITY Gate」（Q2-2 客戶逐字）、「🔍 查看依據」（六欄＋原有出手區間卡①，含 `risk_cap.v2` 硬否決天花板） | L1 **tile**：主值槽留白（⛔ 不放 0／％）＋護欄 chip `⬜ 尚未核准／無法判定`（`not_approved`）＋say＝Q2-2 句**逐字**（`say_verbatim=True`）；`WATER_WHY`→ tile 摺疊「為什麼」；六欄＋原有出手區間→ tile 摺疊 | 卡①「原有出手區間」整段保留（含揭露：更新報告可能列出寫檔數值，`WATER_REPORT_DISCLOSURE`） | ⚠ 主值槽由「文字」變「留白＋chip」：`WATER_VALUE` 字串不再是主值而是 chip 字（同字）；`test_market_blocks::TestWaterAndBasis`「首屏無 %」要改寫為資訊守恆 |
| P-07 | **今日主要風險卡**：≤3 行風險項（`risk_item_text`：序號＋燈色＋桶名＋燈名＋（燈說明）＋「｜方向：…」＋並列）、「另 K 項見圖 D」、「另有 N 桶資料不足、無法判定（見圖 D）」、`HERO_RISK_NO_RANKING_NOTE`、`DANGER_POINTER`（DEC-105 指路）、「🔍 查看依據」 | L1 **風險 tile**：≤3 行**縮短行**（燈色＋桶名＋燈名＋方向詞；§6 Q6）＋「另 K 項見圖 D」＋「另有 N 桶資料不足…」＋指路句（§6 Q2）＋coverage chip；完整原句、`HERO_RISK_NO_RANKING_NOTE`、六欄→ tile 摺疊 | 每個風險項完整原句在摺疊可取得；hero 與圖 D 仍同源（同一份 `MarketRisks`，`hero_risk_items`＝`risks.risk_rows[:HERO_RISK_MAX_ITEMS]`，⛔ 重排／重算） | ⚠ 風險項字串形式改變（見 Q6）；風險燈色 emoji 走**訊號文字通道**、不是 chip（`compact` 無「風險桶 chip」kind，且 META 表封閉）；「≤3 chip」的契約字面由「≤3 行」承接＝§6 Q6 |
| P-08 | **更新卡**：標題「更新」、`single_submit_form`（模式 radio：正常更新（吃暖快取）／強制重抓（清快取）＋🚀 更新今日戰情）、一段 188 字 caption（`PAGE_REFRESH_SCOPE_WHY`＋`REFRESH_SPEED_HINT`）、`data_date_text`（資料日：加權指數最後一根，或 `⬜ 資料日未提供`） | **頁首動作列**（§6 Q1=B）：主鍵留 L1；模式 radio 進 form 內 `st.expander`（`single_submit_form(options_label=…)`，Phase 2 已備、floor 1.56 AppTest 驗過，見 D8 驗證報告）；188 字 caption→ 該 expander 內；一行短句留在鍵旁（契約 §17：「一句留 tile」） | form／gate 語意不變：只有按 🚀 才重抓，radio 不即時 rerun；`st.rerun()` 流程不動 | ⚠ 動作列內含 form＋expander，**實高可能 >40px**（靜態示意只放按鈕；INFERENCE 真高再多 ~40～56px，Gate 時實量）；Q1=A 時此卡仍為第 4 個 tile |
| P-09 | `HERO_AI_PLACEHOLDER`「🤖 AI 投資總結：⬜ 尚未提供」＋`HEALTH_CHIP`「⬜ 資料狀態：尚未彙總」＋指路 | L1 維持**一行字**（現況 `st.caption`，字不改）；Phase 7 才換為 AI 入口卡（R13） | 原樣 | `compact` **沒有**對應 chip kind（`unavailable` 委派給 `⛔ 未接線`，字不同；`ai` kind 字樣是「🤖 AI 生成·非投資建議」，語意不同）→ 維持現況字串，不硬套 chip |
| P-10 | 加權指數資料日（更新卡內）：`資料日：YYYY-MM-DD（加權指數，來源：市場評估輸入）` | 併入**圖 A header 的 `asof` chip**（圖 A 自己的 view `as_of`）與更新動作列旁短句；全句→ 摺疊「來源」段 | 資訊在 | 兩個資料日來源不同：更新卡讀 `mkt_info["index_as_of"]`、圖 A 讀 `get_twii_trend_view().as_of`——**可能不同值**，必須各自標示，⛔ 互相替代（`CLAUDE.md` §2.3／契約 §6-6） |

### 3.3 結論句、⚡、圖 A～D

| ID | 現況 | 新位置 | 保留方式 | 風險 |
|---|---|---|---|---|
| P-11 | **今日結論句**（`build_market_conclusion`；「；」並列、缺值明寫；標題 `CONCLUSION_HEADING`） | L1，**頁級唯一主要判讀句**（B4）；位置見 §6 Q5 | 句子與標題逐字不改（DEC-081 Q2-1）；`regime_clause`／`danger_clause` 輸入不變 | 位置改動＝改 DEC-105 1A 的相對順序（Q5） |
| P-12 | **⚡ 需要處理**：整塊容器（h313）＝`build_key_alert_tile`（今日關鍵：「1 紅 · 1 黃」＋關鍵事項 VIX／ISM PMI…）＋建議持股衝突提示＋`ALERTS_CONFLICTS_NUMBER_NOTE`＋`ALERTS_NO_SOURCE`＋「🔍 查看依據」 | L1 **一行 bar**：`⚡ 需要處理`＋計數 chip（沿用 tile 的主值字）＋「▸ 查看清單」；清單、衝突提示、`ALERTS_NO_SOURCE`、依據→ 該 bar 的摺疊（或 L2 區塊） | 三態判別（有警示／掃過沒有／沒有來源）仍由既有 tile 負責；「沒有來源不寫沒事」字樣不動 | ⚠ 外露高度 313→約 44px（靜態示意）；摺疊內容須逐項可取得（資訊守恆測試） |
| P-13 | **圖 A**（h812 手機）：標題、`CHART_A_SAY`（31 字，客戶原句）、原生折線圖（指數＋MA5／60／120／200 水平參考線＋圖例）、caption「近 N 日，資料至…·`TWII_SOURCE_TEXT`」、`CHART_A_MA_NOTE`、**粗體 `CHART_A_MA_DISCLAIMER`**、「台股趨勢結論：⬜ 尚未定義」、`TREND_DEFINITION_NOTE`、過期警告／失敗紅字／缺均線清單、「🔍 查看依據」 | **Primary**（§6 Q4＝P-B）：header＝標題→chip 列 5 顆（兩護欄各自獨立＋`🕒 資料 MM/DD`＋`近 252 日`＋`✅ 可讀`，來源進摺疊，D10=a）→`CHART_A_SAY`→原生圖（桌 ≤220／手 ≤140）→**恰一個**摺疊「▸ 為什麼／來源／限制／去哪補」 | 護欄兩句逐字、結論位置固定 `⬜ 尚未定義` chip；`CHART_A_MA_NOTE`、`TREND_DEFINITION_NOTE`、缺均線清單、過期警告→摺疊「限制」；六欄 Basis→四段映射（§3.5） | ⚠ 圖高 350→≤220；y 軸數字與圖例仍在原生圖（資訊保留）；`✅ 可讀` 與 `⬜ 尚未定義` 並排的誤讀風險（`P1R-P3-READABLE-VS-UNDEFINED`）→ 排序「護欄在左、可讀在最右」＋摺疊說明 |
| P-14 | **圖 B**（手機 h2695）：標題、`CHART_B_SAY`、來源 caption（Yahoo Finance…^TNX…）、按 `INTL_GROUPS` 三組小標＋**5 張 350px 折線圖**（含各系列「名稱·近 120 日，資料至…」）、`CHART_B_NOTE`、「國際趨勢結論：⬜ 尚未定義」、`TREND_DEFINITION_NOTE`、六欄 | **Secondary**（Q4=P-B）：**small multiples 一組**（5 格，桌 3 欄／手 2 欄，每格 ≤96px、各自座標、⛔ 疊軸／正規化／顯示數字，D5=A）；組級 chip 列寫一次資料日／窗口／`⬜ 尚未定義`；缺系列格＝`⬜ 本輪沒有這個系列`（既有字樣） | 數字（最後收盤、資料日、筆數）在 L2 既有「國際市場（原始資料）」expander 的表格，**該表已存在、不動**；圖 B 的走勢圖 gate 勾選仍畫完整原生圖 | ⚠ **L1 失去 5 個系列的 y 軸數值**（D5=A 的必然結果，客戶已裁示不在迷你圖顯示數字）→ 列入 Q4 的「資訊影響」；⚠ F-3：`SM_NAME_MAX_CHARS=8`，現有系列名 `納斯達克 IXIC`、`費城半導體 SOX` 各 9 字，需顯示名稱對映或調整元件上限（§7） |
| P-15 | **圖 C**（研究框架，零數值）：標題＋tag「研究框架，未啟用」＋`CHART_C_SAY`（客戶原句）＋`CHART_C_EMPTY`＋`CHART_C_BASIS` | **Secondary，D6=B 縮成一行 placeholder**：標題＋tag chip＋`CHART_C_EMPTY` 一句；`CHART_C_SAY`、`CHART_C_BASIS`→ 摺疊「為什麼」 | 零數字／零圖形不變（`chart_c_texts` 掃描範圍同） | ⚠ 客戶原句 `CHART_C_SAY` 由外露改入摺疊——依契約「下沉」允許，但屬客戶原句位置改動，列 §6.2 供客戶過目 |
| P-16 | **圖 D**：標題、`CHART_D_NOTE`、「N 項未評估（共 16 項燈；未評估不等於安全）」、五桶表（桶／方向／是否惡化，**每列「是否惡化：⬜ 尚未定義」重複**）、`CHART_D_ALL_LAMPS_POINTER`、`DANGER_POINTER`、六欄 | **Secondary compact**：「N 項未評估…」保留（⛔ 不寫成安全）；五桶表改**三欄→兩欄**（桶／方向），「是否惡化：⬜ 尚未定義」**寫一次**成 header 護欄 chip（契約 §8-7）；兩個指路句見 Q2；六欄→摺疊 | 五桶固定順序、同源 `risks`；`⬜ 資料不足／無法判定` 列照舊 | ⚠ `risk_panel_rows` 三元組變兩欄＋chip，`test_market_blocks` 對該函式的斷言要改寫；手機現表高 668px→壓為每桶 1～2 行 |

### 3.4 L2／L3 區塊（原樣保留）

| ID | 現況 | 新位置 | 備註 |
|---|---|---|---|
| P-17 | 11 個具名 expander（位階為什麼；指標危險度五桶；風險上限為什麼（X3）；**指標明細（16 項）**；台股盤勢；國際市場；總經／景氣；籌碼；研究中（X9）；資料來源與完整度；問 AI／查看依據） | **全部原樣、原標籤、預設收合**（`LAMP_DETAIL_EXPANDER_LABEL`「指標明細（16 項）」是 DEC-105 指路目標，不得改名；契約 R7：客戶裁示或測試釘字的具名 expander 不改名） | 重運算仍走既有 gate／checkbox（R10：收合≠省運算；L2 4 個 checkbox gate 不動）；「指標明細」最上方仍為指標危險度卡（`today._render_one(_danger_tile)`，DEC-105 3A） |
| P-18 | 區塊標題「以下為可展開區塊（預設收合）。」 | 保留或縮為摺疊群標題 | 純文案 |
| P-19 | 16 盞燈卡內的「▸ 詳細」（`page_today` 卡片機制） | **不動**（屬 `page_today` 共用，且在 L2 expander 內） | W3 只判新頁自有摺疊，不判此處 |

### 3.5 六欄 Basis → 四段摺疊的映射（Q3=A 下，圖用；INFERENCE，待客戶同意 Q3 後才定案）

| 現行「🔍 查看依據」六欄 | 四段摺疊 `▸ 為什麼／來源／限制／去哪補` |
|---|---|
| 規則／計算結果；AI 是否參與 | **為什麼** |
| 使用的資料；資料日期（＋被擠出的 `來源` chip） | **來源** |
| missing；confidence／availability；窗口／口徑／估算說明（`CHART_A_MA_NOTE` 等） | **限制** |
| （現無對應欄）補資料的指路：`NOT_LOADED` 原因、「請按頁首更新」、資料中心指路（`ia_nav.where_to_find`） | **去哪補** |

> 六欄元件 `Basis` 的 `ValueError`「不得留白」性質與 `AI_NOT_INVOLVED`、`confidence／availability` 欄標字面都有測試釘住（`TestWaterAndBasis` 等）；映射改字面＝測試要改寫為資訊守恆（Plan §3 T25）。Q3 選 B 才把 hero tile／⚡ 也併入四段；選 A 只動圖。

### 3.6 會丟失或改形的資訊——一覽（**不靜默刪**；皆有保留處）

| # | 變動 | 保留處 | 客戶可見？ | 去向 |
|---|---|---|---|---|
| L-1 | 風險 tile 由整句→縮短行 | tile 摺疊 | 是 | **Q6** |
| L-2 | 圖 B 5 系列在 L1 不顯示 y 軸數值 | L2「國際市場」表格＋走勢圖 gate | 是 | **Q4** 資訊影響欄（D5=A 已裁示，故不另設題） |
| L-3 | 圖 B 由「5 張直接畫」→「小倍數一組」 | 同上 | 是 | **Q4** |
| L-4 | 結論句位置前移 | — | 是 | **Q5** |
| L-5 | 更新卡 188 字 caption、模式 radio 離開 L1 | 動作列 expander | 是 | **Q1**（B）／§6.2 |
| L-6 | 圖 C 客戶原句 `CHART_C_SAY` 外露→摺疊 | 圖 C 摺疊「為什麼」 | 是 | §6.2 供過目 |
| L-7 | `⚡ 需要處理` 313px 整塊→一行 bar | bar 摺疊 | 是 | §6.2 供過目 |
| L-8 | 位階卡「生效分支 warroom」「（總經契約）」hover 出處 | tile 摺疊 | 是（外露字減少） | §6.2 |
| L-9 | 圖 D「是否惡化」每列重複→header 寫一次 | header chip | 是 | §6.2 |
| L-10 | 指路句（W2） | 見 Q2 | 是 | **Q2** |
| L-11 | 摺疊標籤（W3） | 見 Q3 | 是 | **Q3** |
| L-12 | `HERO_RISK_NO_RANKING_NOTE`、`WATER_WHY` 外露→摺疊 | tile 摺疊 | 是 | §6.2 |

---

## §4 文字線框（推薦方案 R：Q1=B／Q2=A′／Q3=A／Q4=P-B／Q5=B／Q6=A／Q7=A）

### 4.0 閱讀約定

- 框＝主欄示意，**非等比**；`( … )`＝chip（三族：資訊＝細外框、狀態＝淡底、**護欄＝實線粗框**，D3=A）；`░░`＝圖區；`▸`＝摺疊入口；`※`＝夾具示意。
- 所有字串優先用既有常數（§3）；沒有既有常數者標 ※。⛔ 示意數字不得當投資結論。
- 預覽：`docs/vnext/phase4_market/wireframe_preview/`（`compact.py` 真產出的靜態示意；`first_screen_concl-first_loaded_{1440,390}.png` 為推薦版第一屏，`w9_options_{1440,390}.png` 為 Q1 三案）。

### 4.1 桌機 1440×900（loaded，推薦方案 R）

```
y135 ┌──────────────────────────────────────────────────────────────────────────────┐
     │ 📊 市場                                            [ 🚀 更新今日戰情 ]  ← 主 CTA（form）
     │ 現在適不適合投資？未來風險正在增加還是下降？           ▸ 更新選項（模式）     │
     │ ( ⬜ 資料日未提供 )                                    ← 頁級 chip 列（metadata，B3 不計）│
y286 │ 今日結論（五項各自判斷，只並列，不合成）                 ← 逐字；頁級唯一主要判讀句（B4）│
     │ 市場位階：多頭；台股趨勢：尚未定義；國際趨勢：尚未定義；指標危險度：黃（…）；    │
     │ 風險上限：獨立顯示待 C2b＋RC-VISIBILITY Gate。                                │
y374 │ ┌ 市場位階 ──────┐ ┌ 建議總持股水位 ───┐ ┌ 今日主要風險 ───────────────┐ │
     │ │ 多頭           │ │ （主值留白，不放 0／％） │ │ 🟡 📈 中期：台灣 PMI　↗ 上升      │ │
     │ │ 市場位階，不是台股趨勢 │ │ ( ⬜ 尚未核准／無法判定 ) │ │ 🟡 🧩 籌碼：融資餘額　↗ 上升      │ │
     │ │ ▸ 詳細          │ │ 風險上限：獨立顯示待 C2b＋  │ │ 另有 1 桶資料不足、無法判定（見圖 D）│ │
     │ │                │ │ RC-VISIBILITY Gate      │ │ 指標危險度：見下方「指標明細（16 項）」│ │
     │ │                │ │ ▸ 詳細                  │ │ ( 8／16 項有資料 )   ▸ 詳細    │ │
     │ └────────────────┘ └────────────────────┘ └─────────────────────────────┘ │
y~530│ ⚡ 需要處理 ( 1 紅 · 1 黃 )  今日關鍵：VIX 21、ISM PMI 48.5 ※   ▸ 查看清單       │
y~590│ 🤖 AI 投資總結：⬜ 尚未提供　⬜ 資料狀態：尚未彙總（逐來源結果見更新報告）        │
y628 │ ┌ 圖A 🇹🇼 台股趨勢（Primary，恰 1）─────────────────────────────────────┐   │
     │ │ ( 均線為參考，不等於正式台股趨勢判斷。 )( ⬜ 尚未定義 )( 🕒 資料 10/28 )(近 252 日)(✅ 可讀) │
     │ │ 看台股目前是在長期上升、整理還是轉弱；趨勢與短期波動分開判斷。                 │
     │ │ ░░░░ 原生折線圖 ≤220px（指數＋MA 水平參考線＋圖例）░░░░                   │
     │ │ ▸ 為什麼／來源／限制／去哪補                                            │
y900 ├─┴────────────────────────────────── 第一屏分界 ─────────────────────────────┤
     │ 國際趨勢（Secondary 1）  ( 🕒 資料 10/28 )( 近 120 日 )( ⬜ 尚未定義 )        │
     │ 看海外市場、利率與美元是否正在幫助或壓抑台股風險偏好。                         │
     │ [道瓊 DJI ░][那指 IXIC ░][費半 SOX ░]   ← small multiples 3 欄、每格 ≤96px、無數字 │
     │ [美債 10Y ░][美元 DXY ░]                                                    │
     │ ▸ 為什麼／來源／限制／去哪補                                                │
     │ 圖D ⚠️ 主要風險（Secondary 2）  ( 是否惡化：⬜ 尚未定義 )  8 項未評估（未評估不等於安全）│
     │   桶 / 方向 五列（固定順序）；指路句；▸ 為什麼／來源／限制／去哪補                │
     │ 圖C 💰 大盤合理區間 ( 研究框架，未啟用 ) ⬜ 需先核准：EPS 資料來源…（一行）  ▸ 為什麼…  │
     │ ── 以下為可展開區塊（預設收合；11 個具名 expander 原樣）──                      │
```

- **第一屏預算（Visual Budget）**：Primary 1（圖 A）；Secondary 外露 0（在第一屏之下，3 個總數 ≤3，建議 2＋圖 C 一行）；核心狀態 4 個（位階、水位、風險、⚡）、metadata chip 另計；主要判讀句 1；大型圖 1。
- **靜態示意量測（FACT 示意／INFERENCE 真值，見 §4.5）**：H2 起 y135；結論句 y286（相對 H2 **+151** ≤200 ✅）；tile 列 h145（≤160 ✅）；Primary header y628、圖上緣約 y724，第一屏內可見圖約 176／220px。

### 4.2 桌機 1440×900（冷啟動；Missing 路徑，D6=B）

```
│ 📊 市場                                                  [ 🚀 更新今日戰情 ]
│ ( ⬜ 資料日未提供 )
│ 今日結論 … 市場位階：…；台股趨勢：尚未定義；…                        ← 缺值照 L0 句型寫，⛔ 補值
│ ┌ 市場位階 ┐ ┌ 建議總持股水位 ─┐ ┌ 今日主要風險 ─────────────┐
│ │ <依 L3 實際狀態；真冷啟動內容未驗> │ │ (⬜ 尚未核准／無法判定) │ │ ⬜ 尚未載入，請按更新（單行，灰）│
│ └─────────┘ └────────────┘ └──────────────────────┘   ← 同列等高（stretch）
│ ⚡ 需要處理　⬜ 尚未載入                                      ▸ 為什麼沒有／去哪補
│ 🤖 AI 投資總結：⬜ 尚未提供　⬜ 資料狀態：尚未彙總
│ ┌ 圖A 🇹🇼 台股趨勢 ──────────────────────────────────────┐
│ │ ( 均線為參考，不等於正式台股趨勢判斷。 )( ⬜ 尚未定義 )   ← 冷啟動只放護欄；「尚未載入」只寫在槽內 │
│ │ 看台股目前是在長期上升…                                    │
│ │ ┌ Primary 圖槽，**同高 220px**（不縮）──────────────────┐ │
│ │ │              ⬜ 尚未載入，請按更新                      │ │
│ │ └──────────────────────────────────────────────────┘ │
│ │ ▸ 為什麼／來源／限制／去哪補                                 │
│ 國際趨勢 ( ⬜ 尚未定義 )  ⬜ 尚未載入，請按更新  ← **Secondary 縮成一行**（D6=B；仍是 UI_STATE_META 符號＋原因） │
│ 圖D ⚠️ 主要風險  ⬜ 尚未載入，請按更新                              ← 一行
│ 圖C 💰 …( 研究框架，未啟用 ) ⬜ 需先核准…                          ← 一行（本來就無資料）
```

- 載入後，國際趨勢與圖 D 由一行撐開，下方內容**下移一次**（D6=B 已知代價，DEC-115 揭露）；Primary 不跳動。
- **系統真錯誤**（任一來源 `failed`）：該槽改 `🔴 取得失敗`＋1 句原因（紅，唯一用紅處）；`repr(e)` 進摺疊「限制」，⛔ 不外露。**過期**＝琥珀 `⚠ 過期 N 天`，⛔ 塗紅。**部分有資料**＝`◧ N／M 計入`（既有 `UI_STATE_META`）。

### 4.3 手機 390×844（loaded；有底部固定導航 53px，可用高約 790）

```
y135 📊 市場                                                  
y210 現在適不適合投資？未來風險正在增加還是下降？
y~250 ( ⬜ 資料日未提供 )
y286 [ 🚀 更新今日戰情 ]（整列寬；▸ 更新選項）          ← 動作列（Q1=B）；form＋expander 真高未驗
y342 今日結論（五項各自判斷，只並列，不合成）            ← 相對 H2 ≈ +207（≤260 ✅，靜態示意）
     市場位階：多頭；台股趨勢：尚未定義；…（4～5 行）
y~475┌ 市場位階 ─────┐┌ 建議總持股水位 ──┐          ← Q1=B 手機排法 B2：2 欄並排（各寬 ≈173）
     │ 多頭            ││ ( ⬜ 尚未核准／ ) │
     │ 市場位階，不是… ││ ( 　無法判定 　) │
     └────────────┘└──────────────┘
     ┌ 今日主要風險 ───────────────────────┐        ← 整列寬
     │ 🟡 📈 中期：台灣 PMI　↗ 上升                │
     │ 🟡 🧩 籌碼：融資餘額　↗ 上升                │
     │ 另有 1 桶資料不足、無法判定（見圖 D）          │
     │ 指標危險度：見下方「指標明細（16 項）」最上方    │
     │ ( 8／16 項有資料 )  ▸ 詳細                  │
     └────────────────────────────────┘
─── 第一屏約至此（y≈790）；⚡ bar、AI 佔位行、Primary 圖 A 在其下 ───
     ⚡ 需要處理 ( 1 紅 · 1 黃 ) ▸ 查看清單
     🤖 AI 投資總結：⬜ 尚未提供 …
     ┌ 圖A 🇹🇼 台股趨勢（Primary）──┐ chip 列換行 3 行；say 2 行；圖 ≤140px；▸ 摺疊
     國際趨勢 small multiples：**2 欄**（5 格＝3 列 ≈ 300px）＋組級 chip；圖 D／圖 C 同桌機（一行／compact）
```

- **FACT（靜態示意）手機 KPI 區塊高度（Q2 上限 ≤340px）**：W9-B1 單欄堆疊 **389**（✗）、W9-B2「位階｜水位並排＋風險整列」**299**（✓）、W9-A 2×2 **356**（✗ +16）、W9-C **467**（✗）。
- **預測偏離（INFERENCE，見 Q7）**：不論 Q1 選哪案，手機 Primary 標題約在 y≈1000（靜態示意 y997），**不在第一屏**——blueprint 手機框本身也在圖 A 前標「往下捲」。

### 4.4 chip 家族分配（D3=A）與 F-1 設計發現

| 家族 | 本頁用到的 chip（既有 kind／字） | 位置 |
|---|---|---|
| 資訊（細外框） | `asof`「🕒 資料 MM/DD」、`window`「近 252 日／近 120 日」、（`source` 溢出入摺疊） | 圖 A／國際組 header |
| 狀態（淡底） | `readable`「✅ 可讀」（只在 live）、`coverage`「8／16 項有資料」、`stale`「⚠ 過期 N 天」、`status_chip(idle/empty/failed/partial/…)`、`asof_missing`「⬜ 資料日未提供」 | 頁級列／風險 tile／圖 header |
| **護欄（實線粗框）** | `guard_chip(CHART_A_MA_DISCLAIMER)`（逐字）、`not_defined`「⬜ 尚未定義」、`not_approved`「⬜ 尚未核准／無法判定」、（圖 D）「是否惡化：⬜ 尚未定義」逐字 | 圖 A／圖 B 組／水位 tile／圖 D header |

- **F-1（設計發現，FACT：`compact` 驗證）**：同一 chip 列「最多一顆非 `readable` 的狀態類 chip」——`asof_missing`、`coverage`、`status_chip(idle)` 不能同列。故現行狀態行（更新時間＋覆蓋率＋資料日）拆成三處：資料日 chip 在頁級列、覆蓋率 chip 在風險 tile、更新時間在動作列旁。這是元件規則，不是偏好；若客戶要它們同列，需改 `compact` 規則（屬內部技術判斷，不建議）。
- **F-2**：風險 tile 內不能放 3 顆「風險項 chip」：tile chip 合計 ≤2（`TILE_CHIPS_MAX`）、契約 §6 的 META 表封閉、且風險燈 emoji 屬訊號文字通道（`assert_signal_text_clean`）。故以「≤3 行文字」承接契約 §12.1 的「≤3 chip」字面（Q6）。
- ⛔ 沒有第四套視覺語言；紅只給 `failed`；每個色塊有文字。

### 4.5 靜態示意的實測（FACT：`compact.py` 真產出；⚠ 靜態 HTML，非 Streamlit 真值）

| 量 | 桌機 1440（主欄 980） | 手機 390（內寬 358） | 上限 |
|---|---|---|---|
| tile 列高：W9-A（4 欄／2×2） | **163**（含更新 tile） | **356** | 桌 96～160／手 ≤340 |
| W9-B（3 tile＋動作列；手機 B1 單欄／B2 2＋1） | **145** | B1 **389**／B2 **299** | 同上 |
| W9-C（3＋1 窄 CTA 格／手機單欄＋CTA 整列） | **145** | **467** | 同上 |
| 結論句頂端（相對 H2） | 結論在 tile 後 **+312**／在 tile 前 **+151** | 後 **+612**／前 **+207** | 桌 ≤200／手 ≤260 |
| Primary header y | 628（第一屏內） | 997（第一屏外） | 第一屏內 |

> 這些是「compact 元件＋16px 間距」的靜態值；Streamlit 的真實元素容器、`st.form`＋`st.expander` 動作列、原生圖外框都會再加高，**Gate 實測才算數**。tile 列高 145 由「風險 tile 兩行縮短行＋指路句＋coverage chip」撐起——若維持現行整句（約 4 行），靜態高度 **>184px**，超過 160px 上限（見 Q6）。

### 4.6 與 Decision Digest／One AI Brain 的邊界（本頁）

- 本頁**不 import、不讀、不組** Decision Digest／Brain（Phase 7）。AI 投資總結維持一行佔位（P-09）。
- **顯示切片不是輸入**：風險 tile 的「前 3」、圖 B 小倍數格數、⚡ 摺疊與否、任何 expander 收合，**都不影響** Digest（Digest 由 canonical data＋正式規則結果建立，契約 §9／Digest §6 不變性測試；Brain §3 禁清單：⛔ 掃 UI 文字、⛔ 因收合少讀、⛔ 用 UI Top-N 當存在證明）。`hero_risk_items`＝`risks.risk_rows[:HERO_RISK_MAX_ITEMS]` 維持純顯示切片，⛔ 改排序／重算。
- 本頁**不新增** confidence／分數：下表六種投資語意各有獨立位置，⛔ 合併成單一分數／燈。

| 語意 | 本頁位置 | 備註 |
|---|---|---|
| Market Regime（市場位階） | 位階 tile（五態＋「市場位階，不是台股趨勢」） | DEC-105 2A，⛔ 映射偏多／中性／偏空 |
| Market Trend（台股／國際趨勢） | 圖 A／圖 B 護欄 `⬜ 尚未定義`；結論句「尚未定義」 | 正式定義另列 High Gate |
| Risk Level（指標危險度） | 風險 tile＋圖 D；「指標明細（16 項）」最上方 | DEC-105 3A、指路 |
| Risk Cap | 水位 tile：`⬜ 尚未核准／無法判定`＋Q2-2 逐字句 | ⛔ 本頁不顯示任何上限數字 |
| Confidence | **只在 L2「市場位階：為什麼？」的「信心度」列**（紅綠燈資料來源齊備程度） | ⛔ 不上 L1、⛔ 與 coverage 混 |
| Data Completeness（資料完整度） | 風險 tile 的 coverage chip、頁級 `⬜ 資料日未提供`、`⬜ 資料狀態：尚未彙總`、L2「資料來源與完整度」 | **Data Health 與 Investment Logic 分離**：覆蓋率只說「幾項有資料」，⛔ 說成「風險低」 |

---

## §5 Missing／unavailable 處理總表（D6=B；`UI_STATE_META` 十態不另造）

| 情境 | Primary（圖 A） | Secondary（國際組、圖 D、圖 C） | tile 主值 | 備註 |
|---|---|---|---|---|
| 未載入 | 同高槽內 `⬜ 尚未載入，請按更新`（灰） | **一行**同字（灰） | 留白＋`⬜` 狀態 chip | chip 與槽內文字二選一（契約 §6-5） |
| 無資料／缺系列 | 槽內 `▨ 無資料：<原因>` | 一行；缺格 `⬜ 本輪沒有這個系列` | 留白＋原因 chip | ⛔ 不畫線／點 |
| 取得失敗 | 槽內 `🔴 取得失敗`＋1 句 | 一行紅 | 留白＋`🔴` chip | 唯一紅；`repr(e)`→摺疊 |
| 過期 | 圖照畫＋`⚠ 過期 N 天`（琥珀） | 同左 | 值照畫＋`⚠` chip | ⛔ 塗紅 |
| 研究框架未啟用（圖 C） | — | 一行 `⬜ 需先核准：…`（零數值） | — | 本來就無資料 |
| 未評估 ≠ 安全 | 圖 D「N 項未評估」保留；結論句缺值照寫 | | | missing≠0≠neutral≠HOLD≠safe |

---

## §6 客戶決策表（Customer Decision Gate）

> 回覆方式：每題「選項字母」即可（例：`Q1 B／Q2 A′／Q3 A…`）；不裁示者依各題「不裁示預設」。**推薦方案是 AI 總管建議，客戶可推翻。** 每題列出會動到的檔與守衛（§7 有總表）。

### 6.0 題目總覽

| 題 | 一句話 | 推薦 |
|---|---|---|
| **Q1**（W9／CV1-DR-12） | 第一列核心狀態要幾欄？更新鈕放哪？手機怎麼排？ | **B**（3 欄＋更新鈕移到頁首動作列；手機 2＋1） |
| **Q2**（W2） | 「指標危險度」指路：維持說明句、縮短句、還是改 chip？ | **A′**（維持「句」，縮到 ≤32 字） |
| **Q3**（W3） | 摺疊標籤要不要統一成「▸ 為什麼／來源／限制／去哪補」？ | **A**（圖用新字樣；tile／⚡ 維持「🔍 查看依據」六欄） |
| **Q4** | 主圖長什麼樣：單圖＋切換列、台股主圖＋國際小倍數、還是全小倍數？ | **P-B**（台股主圖＋國際小倍數，不做切換列） |
| **Q5** | 今日結論句放在 tile 之前還是之後（DEC-105 1A 是之後）？ | **B**（移到 tile 之前、頁首下方） |
| **Q6** | 「今日主要風險」卡的風險項顯示整句還是縮短行？ | **A**（縮短行，整句進摺疊） |
| **Q7** | 手機第一屏看不到主圖（預測），接受還是要求提前？ | **A**（接受，Gate 登 🟡） |

### Q1｜W9／CV1-DR-12：第一列核心狀態欄數、更新鈕位置、手機排法

**背景（FACT）**：`CLAUDE.md` v3 §00 前端組寫「固定 3 欄自適應網格」（最高位階文件）；DEC-091 §四 客戶原文「第一列只放 **3～4** 個核心狀態：市場狀態／建議總持股水位／今日主要風險／更新（主 CTA）」；DEC-105 第 5 點維持現行 Hero `st.columns(4)`（P2 偏離）；blueprint（Visual SSOT）桌機 4 張 hero 卡、手機 2×2。三者在「欄數」上互相牴觸，`CLAUDE.md` 位階最高，**不得以 DEC 或內部讀法重新解釋**（BACKLOG `CV1-DR-12`）。

| 選項 | 內容 | 優點 | 缺點 | 風險／實測（靜態示意） |
|---|---|---|---|---|
| **A** 4 欄 | 桌機 4 欄（位階｜水位｜風險｜更新 tile）、手機 2×2（＝blueprint／現況） | 與 blueprint、DEC-105 一致；改動最小 | **與 `CLAUDE.md` v3 §00「固定 3 欄」字面牴觸**——選 A 需客戶**明示**「KPI 列不適用 3 欄」，並由有權限的一方在 `CLAUDE.md` 加註（本團隊不改）；更新 tile 只剩一顆按鈕卻占一整欄 | 桌機 tile 高 163（>160）、手機 2×2 高 356（>340） |
| **B**（推薦） | 桌機 **3 欄 tile**（位階｜水位｜風險）；「🚀 更新」改為**頁首動作列**（與 H2 同列右側／手機 H2 下一整列）；手機 tile 排法 **B2**：位階｜水位並排、風險整列 | 字面符合 `CLAUDE.md` §00「固定 3 欄」＋DEC-091 §四「3～4」（3 個核心狀態＋主 CTA）；Q2 手機 ≤340 ✅（299）；更新 tile 本來內容在 Q3 之後只剩一顆鍵（模式 radio、188 字說明進 expander），放動作列更合理；桌機 tile 145 ✅ | 與 blueprint「4 張 hero」不同（更新由 tile 變動作列）；動作列含 form＋expander，真高未驗 | 更新 form 位置改變（form 語意不變）；`test_market_blocks` 的 `st.columns(4)` 斷言（T23）要改寫 |
| **C** 3＋1 | 桌機 3 tile＋同列第 4 個窄 CTA 格；手機單欄＋CTA 整列 | 更新仍在第一列、視覺上接近 blueprint | 手機 467（>340）；第 4 格仍是「第 4 欄」，與「固定 3 欄」字面仍有爭議 | 需客戶判定「3＋1」算不算 3 欄 |

**AI 總管推薦：B（手機取 B2）。** 理由：(1) 是唯一不需要客戶修改或加註最高位階文件、也不用重新解釋條文的選項；(2) 滿足 DEC-091 §四「3～4」與「更新＝主 CTA」；(3) 靜態實測唯有 B2 同時滿足桌機 tile ≤160、手機 KPI 區塊 ≤340；(4) 更新卡經 Q3 瘦身後只剩一顆鍵，單獨占一欄是浪費。代價（據實）：偏離 blueprint 的「4 張 hero」。
**會動到**：`_market_blocks.render_hero`（`columns(4)`→3＋動作列）、`page_market.render_page_market` 頁首（→ **還原鏈新頭節**，見 §7）、`tests/test_market_blocks.py::TestStructure`（T23，改為欄數＋資訊守恆）；**不需動** `CLAUDE.md`、`z60 _BASE_DIGEST`（不在指紋範圍，§7）。若選 A：另需客戶就 `CLAUDE.md` §00 的明示處置（本團隊不處理）。
**不裁示預設**：維持現行 4 欄（Gate 不判欄數，Plan 既定）；但 Q4／Q5 的第一屏版面將無法落地——Phase 4 該區塊不開工。

### Q2｜W2：「指標危險度」指路——說明句、縮短句、chip

**背景（FACT）**：DEC-105 第 4 點（客戶）要求首屏「今日主要風險」與圖 D 必須指路到指標危險度、**字面含「指標危險度」**、目標 expander 標題「指標明細（16 項）」不改、冷／熱 session 皆有；現行是說明句 `DANGER_POINTER`（38 字（實測 `len`）：「指標危險度（整體危險度與五桶摘要）請展開下方「指標明細（16 項）」最上方。」）出現在風險卡與圖 D 兩處（圖 D 另有 `CHART_D_ALL_LAMPS_POINTER`）。契約 §22 W2：維持說明句 vs 改 chip（字面不變）。

| 選項 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A** 維持現句 | 兩處都用現行 `DANGER_POINTER`（38 字（實測 `len`）） | 零改字、零新 chip kind | 每處 ~2 行；外露 38 字 >32 的非客戶原句（Gate A8 🟡，兩處合計 1～2 段） | 與其他 🟡 累積達 4 項視為 ❌ |
| **A′**（推薦） | 仍是「句」，縮到 ≤32 字且保留三要素：含「指標危險度」、含「指標明細（16 項）」、指向「最上方」，例：`指標危險度：見下方「指標明細（16 項）」最上方`（※24 字，實測 `len`；字面由測試守 ≤32） | 不新增 chip kind；過 Gate A8；DEC-105 要求的字面與目標標題全保留 | 改了客戶核准過的「呈現文字」（但 DEC-105 只要求字面含詞與目標標題，**不是**逐字句） | 測試釘 `DANGER_POINTER` 常數字面處要改（冷／熱 session、expander 標題、第一張卡含「指標危險度」三條守衛照留） |
| **B** chip | 指路改成一顆 chip（字面不變） | 最省版面 | **`compact` 沒有「指路 chip」kind**：契約 §6 META 表封閉（新增 kind 須改契約表＋`compact._EXTRA_KINDS`＋M2 對帳測試）；借 `guard_chip` 會把「指路」冒充成語意護欄（家族錯置） | 動契約表＋元件＋守衛；不符 Phase 4 最小範圍 |

**AI 總管推薦：A′。** 理由：W2 的目的是「少占版面」，A′ 達成而不動元件／契約；B 的元件成本與家族錯置風險超過收益。若客戶要 chip，Phase 4 前需先另開小批擴 `compact`。
**會動到**：`_market_blocks.DANGER_POINTER`（A′ 改字；A 不動）、風險 tile／圖 D 渲染；守衛：`test_market_blocks`（指路句存在、expander 標題字面、首卡含「指標危險度」）。
**不裁示預設**：A（維持現句，契約 §22 既定「未拍板維持現行」）。

### Q3｜W3：摺疊標籤是否統一為「▸ 為什麼／來源／限制／去哪補」

**背景（FACT）**：契約 R7／DEC-109 五：**主圖 header 下方**用「▸ 為什麼／來源／限制／去哪補」（客戶明給）；卡片摺疊「▸ 詳細」（客戶 2026-09-25 核可線框逐字，`page_today` 卡片機制，在本頁只出現於 L2「指標明細」內，不動）與各處「🔍 查看依據」（六欄；blueprint 每張卡都有）**維持有效**；是否統一換字＝待拍板。本頁新自有摺疊：圖 A、國際組、圖 D（圖）＋水位／風險 tile、⚡（卡）。

| 選項 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A**（推薦） | **圖**（圖 A、國際組、圖 D）用新四段字樣；**tile／⚡** 維持「🔍 查看依據」六欄 | 符合客戶對「主圖」的明確字樣；tile 的六欄與原有出手區間等內容不重排；blueprint 對 tile 的六欄保留 | 一頁兩種摺疊標籤 | 六欄→四段映射（§3.5）要改測試；兩種標籤並存的認知成本 |
| **B** 全頁統一四段 | 圖與 tile／⚡ 全用新字樣；六欄併入四段 | 一致 | 六欄元件（`Basis`、欄標、`AI_NOT_INVOLVED`、`confidence／availability` 欄標）被測試釘字面，併入＝大改；偏離 blueprint 六欄 | 測試改寫量最大；水位 tile 的「原有出手區間（含 `risk_cap.v2`）」須放哪一段需另判 |
| **C** 全頁維持「🔍 查看依據」 | 圖也不用新字樣 | 零重排 | **與 DEC-109 五客戶明給字樣相左**（主圖） | 不建議 |

**AI 總管推薦：A。** 理由：客戶明確只就「主圖」給了字樣；tile 是不同物件（卡片詳細），且其六欄結構受 blueprint 與測試釘住。`▸ 詳細`（16 燈卡）本來不動。
**會動到**：`_market_blocks`（新增 `render_fold`＝`st.expander` 薄封裝，Phase 3 §17.1 預留；`Basis` 映射）、守衛 T25（`TestWaterAndBasis` 等改為資訊守恆）。
**不裁示預設**：A。

### Q4｜主圖形態（契約 §12.1「擇一」；屬版面異動，列客戶）

**背景**：契約 §12.1 把 Primary 描述為「市場環境主圖＋segmented 切換（台股｜海外市場｜利率｜美元）**或**改以 small multiples」，「Phase 4 依 Gate 決定」。這會改變客戶眼睛看到的畫面結構（圖 A／圖 B 是客戶 DEC-091 §四 明列的兩張圖），故送客戶。已裁示的約束：D5=A（迷你圖／小倍數不顯示數字）、D6=B、D8=B（切換鈕若用，須 floor 1.56 實跑、不成立退回圓點）。

| 選項 | 內容 | 優點 | 缺點 | 資訊影響／風險 |
|---|---|---|---|---|
| **P-A** 單圖＋切換列 | 一張主圖＋膠囊切換列（台股｜海外市場｜利率｜美元），預設台股；一次一張 | 所有選項都是帶軸的原生圖（軸數字保留）；非選中不畫（R10 省一點運算）；Secondary 只剩圖 D、圖 C | 圖 A／圖 B 的身份被合併（各有的標題、說明句、護欄要隨選項切換）；「海外市場」含 3 系列，**不得疊軸**（`CHART_B_NOTE`）→ 該選項內仍得做 3 格小倍數（無軸數字）；需 D8 五條硬約束（取消選取回退、form 內 `None`、44px、換行、options 型別）；手機 4 項切換列 | 國際資訊被藏在 3 次點擊後；切換狀態屬新互動 |
| **P-B**（推薦） | **圖 A＝Primary**（原生圖，保留 y 軸、MA 水平參考線、圖例）；**國際 5 系列＝Secondary small multiples 一組**（桌 3 欄／手 2 欄，≤96px，無數字）；圖 D、圖 C 為其餘 Secondary（圖 C 一行）；**不做切換列** | 圖 A／圖 B 各保身份與護欄（客戶 DEC-091 §四 兩張圖）；國際 5 系列同屏並列（「海外／利率／美元是否幫助或壓抑」本來就是跨系列比較）；不依賴 D8／floor 1.56 的 `st.segmented_control`；互動最少 | Secondary 總數達 3（上限 ≤3、建議 2；圖 C 為一行 placeholder，Gate 時登記）；**L1 失去國際 5 系列的 y 軸數值**（D5=A 必然結果；數值在 L2 既有「國際市場」表格＋走勢圖 gate） | 小倍數元件名稱上限 8 字 vs 現有 `納斯達克 IXIC`（9）、`費城半導體 SOX`（9）→ 顯示名對映（§7 F-3） |
| **P-C** 全小倍數 | 台股＋國際 5 系列 6 格小倍數當 Primary | 版面最小 | 台股的 MA 水平參考線與圖例無法放進 ≤96px 迷你圖且不得顯示數字 → **資訊直接丟失**（只能入摺疊）；Primary 失去「主圖」的辨識度 | 不建議 |

**AI 總管推薦：P-B。** 理由：(1) 不改圖 A／圖 B 的客戶定義與護欄結構；(2) 台股主圖資訊完整保留；(3) 國際系列同屏比較；(4) 零 D8 依賴；(5) 成本只是 Secondary 達 3 並使 L1 國際圖失軸數值（客戶已就迷你圖不顯示數字裁示 D5=A，且數值在 L2 保留）。若客戶更看重「國際圖保留軸數字」，選 P-A。
**會動到**：`_market_blocks.render_chart_a`／`render_chart_b`（重寫）、新增小倍數組裝（`compact.small_multiples_html`＋`sparkline_svg`，掛頁用 `st.markdown(unsafe_allow_html=True)`，⛔ `st.html`——會剝 svg，見 D8 驗證報告）；守衛：圖 A／B 護欄逐字、`⬜ 尚未定義` 位置、`INTL_GROUPS` 對帳、`CHART_B_NOTE` 不疊軸／不正規化。
**不裁示預設**：現況（圖 A、圖 B 各自照舊）——但 Primary 在第一屏的要求（契約 B1）不會達成；Phase 4 版面實作無法落地。

### Q5｜今日結論句位置（DEC-105 1A）

**背景（FACT）**：DEC-105 1A（客戶）：結論句維持在 Hero 四卡與「⚡ 需要處理」之間；DEC-109 部分取代：Hero／⚡ 相對順序可維持，但結論句**必須落在第一屏**（客戶「今日結論必須在第一屏可見」、DEC-108 ①「結論先行」）；契約 Q11（建議上限）：主要判讀句頂端相對 H2 桌機 ≤+200／手機 ≤+260。

| 選項 | 內容 | 靜態實測（相對 H2） | 風險 |
|---|---|---|---|
| **A** 維持在 tile 之後 | H2→chip→**tile 列**→結論句→⚡ | 桌機 **+312**（>200）、手機 **+612**（>260；手機結論句下緣 y≈863，已被第一屏裁切） | Q11／A10 不過；手機結論句在第一屏邊緣被截 |
| **B**（推薦） | H2→chip→**結論句**→tile 列→⚡ | 桌機 **+151** ✅、手機 **+207** ✅ | 改動 DEC-105 1A 的相對順序（結論句移到 Hero 之前）；契約 §16 只說「進第一屏」，沒要求在 Hero 之後 |

**AI 總管推薦：B。** 理由：這是唯一能同時達成 Q11 與「結論先行」（DEC-108 ①）的排法；A 的代價是手機第一屏看不完整結論句。
**會動到**：`page_market.render_page_market` 的區塊順序（還原鏈頭節；「今日結論原樣保留（parity 腳本逐字比對）」的 parity 比對仍成立，句子與標題不改）；守衛：`test_page_market`／`test_uim_market_page` 中關於區塊順序的斷言要改。
**不裁示預設**：A（維持 DEC-105 1A）。

### Q6｜「今日主要風險」卡：整句 vs 縮短行

**背景（FACT）**：現行每個風險項是整句（例 `① 🟡 📈 中期：台灣 PMI（局部走弱）｜方向：↗ 上升｜同級並列 2 項`，在 233px 欄寬折 2～3 行）。契約 §12.1 寫「≤3 chip」，但 chip 無對應 kind（見 F-2）。

| 選項 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A**（推薦） | ≤3 行**縮短行**：`🟡 📈 中期：台灣 PMI　↗ 上升`（燈色＋桶名＋燈名＋方向詞）；「（燈說明）」「｜方向：」標籤「｜同級並列 N 項」與 `HERO_RISK_NO_RANKING_NOTE` 進 tile 摺疊（整句原樣） | tile 高 145（≤160）；方向詞仍用 L2 原詞（⛔ 翻成惡化／好轉） | 外露字串形式改變 | `risk_item_text` 要新增縮短版（整句版保留於摺疊）；hero／圖 D 仍同源 |
| **B** 維持整句 | 與現況相同 | 零改字 | 靜態 tile 高 **>184**（>160，同列 3 欄全被拉高）；手機更長 | Gate A4／A5 🟡/❌ |
| **C** chip | ≤3 顆風險 chip | 契約字面 | 需新 kind（動契約表＋元件）；燈 emoji 屬訊號文字通道不得進 chip | 不建議 |

**AI 總管推薦：A。** 理由：資訊不減（整句在摺疊）、達成高度上限、不擴元件。
**會動到**：`_market_blocks.hero_risk_lines`／`risk_item_text`（新增縮短函式）、`test_market_blocks`（hero 文字斷言→資訊守恆）。
**不裁示預設**：B（維持整句；第一屏高度預算會超）。

### Q7｜手機第一屏不含主圖（預測偏離）

**背景（INFERENCE，靜態示意）**：手機第一屏（可用約 790px）依序要放頁首、結論句（4～5 行）、3 個 tile（B2＝299）——Primary 標題約在 y≈1000，**無論 Q1 選哪案都不在第一屏**。blueprint 手機框也把圖 A 放在「── 往下捲 ──」之後。契約 R2／B1 要求 Primary 在第一屏。

| 選項 | 內容 | 優點 | 缺點 |
|---|---|---|---|
| **A**（推薦） | 接受：手機第一屏＝頁首＋結論＋3 狀態＋更新鍵，主圖在其下；Gate A2 手機登 🟡 並寫理由（契約 §14.1「真資料／mobile 限制的合理調整」） | 與 blueprint 手機框一致；不犧牲五問（狀態、數字、行動、下一步）；不動結論先行 | 與契約「Primary 在第一屏」字面不符（需 Gate 理由） |
| **B** 手機把主圖提前 | 手機排序：結論→**主圖**→tile | 主圖在第一屏 | 3 個核心狀態被擠到第一屏之外，違反第一屏五問（狀態、重要數字） |
| **C** 手機壓縮 tile | tile 改單行 chip 列 | 主圖可能進第一屏 | 失去 tile 結構，風險行／水位／位階資訊密度被壓，需另開線框 |

**AI 總管推薦：A。** 理由：五問（狀態、數字、行動、下一步）比「主圖」更前；blueprint 本身即此排法。
**會動到**：僅 Gate 報告（登 🟡＋BACKLOG P2），不動程式。
**不裁示預設**：A。

### 6.1 W3 以外、W2／W9 以外的其他版面差異

已併入 Q4～Q7；其餘差異屬「已依契約定案」（§6.2）。

### 6.2 已依契約／既有 DEC 定案、本線框照辦（客戶可推翻；不另設題）

| # | 事項 | 依據 |
|---|---|---|
| D-1 | ⚡ 需要處理：一行 bar（計數）＋清單入摺疊；「沒有來源不寫沒事」不變 | 契約 §17；DEC-109 十二 Top-N |
| D-2 | 圖 C：Secondary 縮成一行 placeholder；`CHART_C_SAY`（客戶原句）、`CHART_C_BASIS` 入摺疊；零數值／零圖形不變 | DEC-115 D6=B；契約 §5 |
| D-3 | 圖 D：「是否惡化：⬜ 尚未定義」寫一次成 header 護欄 chip，表去重複欄 | 契約 §8-7；DEC-105 |
| D-4 | 位階 tile：「生效分支 warroom」「（總經契約）」、hover 出處入摺疊 | 契約 §11／§18 |
| D-5 | 更新動作：主鍵外露；模式 radio＋188 字說明入 form 內 expander（`options_label`）；form／gate 語意不變 | 契約 §17；Phase 2 步驟 1／D8 驗證 |
| D-6 | 圖 A chip：5 顆（兩護欄各自獨立＋資料日＋窗口＋可讀），來源入摺疊 | DEC-115 D10=(a) |
| D-7 | 新元件一律走 `compact.py`（chip 三族、護欄實線粗框、迷你圖無數字）；紅只給 `failed` | DEC-115 D3／D5 |
| D-8 | 11 個具名 L2 expander 原樣、原標籤、預設收合；`指標明細（16 項）`不改名 | 契約 R7；DEC-105 |

---

## §7 風險／守衛預估（INFERENCE，以當時 main 實測為基；實作前須重驗）

### 7.1 動檔清單（預測，依推薦方案 R）

| 檔 | 預測 | 守衛／鏈 |
|---|---|---|
| `src/ui/views/page_market.py` | **改**（頁首、區塊順序、Hero→3 tile＋動作列、L1 重組） | **還原鏈**：被 `tests/test_nav1_revert_chain.py`、`tests/test_uim_revert_chain.py` 以基底 sha 釘住；`test_xvext_revert_chain` 第一步呼叫 `uim_revert_for`。→ 須在鏈頭**再接一節**（比照 `test_uim_revert_chain`：基底＝Phase 4 開工前 main、pair 以 difflib 產生並驗「套用後逐字等於基底」），⛔ 動任何舊表／舊基底 sha。**FACT：掃描 `tests/**` 中形如 `'src/ui/views/<file>.py': '<sha256>'` 的表，`page_market.py` 只出現在上述兩條鏈（regex 粗掃，可能漏其他格式）。** |
| `src/ui/views/_market_blocks.py` | **大改**（`render_hero`／`render_alerts_block`／`render_chart_a–d`／`risk_panel_rows`／`Basis` 映射／縮短行） | **FACT：無 sha 鏈**（同上掃描 0 命中）；但被 `test_market_blocks`（58 tests）、`test_page_market`（46）、`test_uim_market_page`（21）等 AST／字串守衛釘住（含 `st.columns(4)`、hero 文字、首屏無 %） |
| `src/ui/views/_ui_kit.py` | 可能加 `render_fold`（薄封裝）／公開 `status_chip`（Phase 3 §17.1 預留） | **FACT：無 sha 鏈**；Phase 2 golden（`test_p2_step1_shared_optional_params`）釘 `render_card`／`single_submit_form` 輸出，只加不改即不影響；`page_today`／`page_hold` 共用，改前跑 `tests/test_p0*_*`、`ui_v2` |
| `src/ui_v2/compact.py` | 可能微調（小倍數名稱上限 F-3；若 Q2 選 B 則新 kind） | `tests/ui_v2/test_compact.py`（golden sha；Phase 3 已有 mutation M1～M20） |
| `src/ui/views/page_today.py` | **⛔ 不動**（Plan §7；多鏈釘住） | — |
| `app.py` | **不動**（掛載點 `_ia_view_market` 不變） | **`tests/test_batch_z60.py::TestOldFilesUntouched._BASE_DIGEST` 不需改**：FACT 指紋範圍＝`src/ui/{tabs,etf,pages,render}` ＋ `app.py`（91 檔），**不含** `src/ui/views/`、`src/ui_v2/`（讀測試內容＋本批實跑 z60 綠）。⚠️ 以上對本批當時 main 成立；若實作期改了 `app.py` 或上述四目錄，則須同步指紋 |
| `src/services/*`、`src/compute/*`、`shared/*` | **不動**（零資料語意變更；`build_market_risks`、`build_verdict_tiles`、`build_key_alert_tile` 等照舊被呼叫） | `tests/test_c3_layering_guard.py`（L5 不得 import L1；本頁 ⛔ 零 `src.data.*`） |
| `tests/*` | 改寫：`test_market_blocks`（T23／T25／hero／圖 D 欄）、`test_page_market`、`test_uim_market_page`、新鏈頭節測試；新增 Phase 4 mutation 與資訊守恆測試 | 按 Plan §3 T-表「等強替代」（資訊守恆，不降強度） |

> **`z60 _BASE_DIGEST`、`_ui_kit.py`、還原鏈覆蓋＝以當時 main 重測**（Plan §17.1 指示）：本批重測結論如上（FACT：z60 範圍不含 views；`_ui_kit.py` 無 sha 表；`page_market.py` 有兩條鏈）。**不沿用 Phase 2 步驟 0 的舊結論**——Phase 2 §12.2 當時寫「`_ui_kit.py` 是否受鏈待判」，本批已判：不受 sha 鏈，但受 Phase 2 golden 與 p0x 測試的 AST／輸出守衛。

### 7.2 技術發現（需在實作前處理；皆內部自決）

| # | 發現 | 處置建議 |
|---|---|---|
| F-1 | chip 列「最多一顆非 readable 狀態 chip」，狀態行三事實不能同列（§4.4） | 已拆三處；寫進元件使用規則 |
| F-2 | 風險 tile 不能用 chip 承接 ≤3 風險項（`TILE_CHIPS_MAX=2`、META 封閉、emoji 訊號通道） | Q6=A |
| F-3 | `SM_NAME_MAX_CHARS=8` vs `納斯達克 IXIC`、`費城半導體 SOX`（各 9 字） | 顯示名對映（不改 `INTL_MAP` 鍵）或調元件上限；內部拍板 |
| F-4 | `st.html` 剝行內 `<svg>`（Phase 3 §17.3） | 小倍數／sparkline 一律 `st.markdown(unsafe_allow_html=True)` 或 data-URI `<img>` |
| F-5 | 動作列內 form＋expander 實高 >40px、且 form 在 `st.columns` 的欄內 | Gate 實量；floor 1.56 form 內 expander 路徑 AppTest 已驗（D8 報告），**1.57～1.58 未驗** |
| F-6 | 兩個「資料日」語意（逐指標 vs 加權指數最後一根）可能不同值 | 各自 chip／各自摺疊，⛔ 互相替代 |
| F-7 | harness 的 cold 態 L3 仍被假資料取代 | 真冷啟動態需實機／真資料補驗；Gate 報告據實標 |
| F-8 | 還原鏈頭節 pair 的錨點必須在最終檔上產生（實作完成後最後一步） | 比照 UI-M 作法 |

### 7.3 mutation 預估（拔守衛必紅；沿用 Phase 3 M1～M20 手法，Phase 4 專屬）

結論句與標題逐字；Q2-2 逐字；`CHART_A_MA_DISCLAIMER` 與 `⬜ 尚未定義` 各自獨立 chip（不合併）；圖 A／圖 B 趨勢結論位置固定；水位主值留白不放 0／％；Primary 冷啟動同高、Secondary 一行；Missing 一行仍帶 `UI_STATE_META` 符號與原因；hero 與圖 D 同源（`risks`）；`HERO_RISK_MAX_ITEMS` 只切片；指路句三守衛（冷／熱、目標 expander 標題、首卡含「指標危險度」）；更新 form 單次 submit、radio 不即時 rerun；`⚡` 三態判別與「沒有來源不寫沒事」；無 `title=` hover-only；迷你圖無數字（D5）；紅只給 `failed`；`page_market`／`_market_blocks` 零 `src.data.*`、零 Decision Digest import；Top-N／收合不影響 Digest（呼叫 Phase 2 既有不變性守衛）。

### 7.4 Model×Effort 建議（Plan R19；開工前依 DEC-084／DEC-106 核對實際設定，符合即靜默繼續）

- **線框拍板後的實作**：頁面組裝（第一屏、風險 tile、Missing 路徑、還原鏈頭節）涉及**投資核心語意的位置搬移**（Q2-2 逐字句、結論句、missing≠0、未評估≠安全）與還原鏈產生——**建議 Opus 5.5＋High**；測試改寫、機械式搬字串、mutation 補齊、截圖／量測可切 **Sonnet 5.5＋Medium**（DEC-109 三十二）。是否需升級由實作時依 Gate 與守衛結果判斷；**本批（文件）已無需切換**。
- 拆 PR 建議：(i) 第一屏（頁首＋結論＋3 tile＋⚡ bar）＋還原鏈頭節；(ii) 圖區（圖 A Primary＋國際小倍數＋圖 D／圖 C）。⛔ 一次改一個模組（`CLAUDE.md` §8.5）。

### 7.5 Gate 預測（推薦方案 R；INFERENCE，待實作後由獨立 QA 判）

| 項 | 預測 |
|---|---|
| A1／A2／V1／V2 | 桌機 ✅（Primary 1、Secondary 3 含一行 placeholder）；手機 A2 🟡（Q7） |
| A3／A5／Q12 | 全頁高由 5575／7966 下降約 **>50%**（INFERENCE：6 張 350px 圖→1 張 ≤220＋5 格 ≤96，Hero 641→≈145，⚡ 313→≈44）；能否 ≤1.3× blueprint 未知，Gate 實量 |
| A4／A6 | tile ≤160 ✅（Q6=A）；Primary ≤220／140、mini ≤96 ✅ |
| A7／A8 | 風險 Top-3、圖 D 5 桶 ✅；外露非客戶原句 >32 字＝指路句 A′ 後 0～1 段 |
| A9／V9 | Missing 全為 chip／placeholder ✅；圖 D 重複 Missing 已去除 |
| A10／Q11 | 桌機 ✅；手機結論句 +207 ✅，主 CTA 第一屏 ✅（動作列） |
| V10／V11 | 工程字樣外露 0（`Gate`、`C2b` 為客戶例外）；hover-only 0 |

---

## §8 未驗與限制（誠實揭露）

- **全部單組撰寫、未經第二組驗證**；§3 的「能力對映」不證明「涵蓋所有能力」；§2.4／§7.5 的 Gate 判定是預估，非正式判定。
- 現況量測為**夾具**；真資料態、真冷啟動、真過期／失敗態、Streamlit **floor 1.56**（本批只用 1.59.2 量；D8 驗證報告在 1.56.0 驗過 segmented／form 內 expander 的 AppTest／Playwright，**未含本頁**）、手機實機、Streamlit Cloud、Safari／Firefox **未驗**。
- §4.5 的 px 是靜態 HTML 示意值，**不是** Streamlit 渲染值（原生圖外框、form＋expander 動作列、元素容器間距都未含實測）。
- 「`_ui_kit.py` 無 sha 鏈」「`page_market.py` 只有兩條鏈」來自**對 `tests/**` 以 regex 掃 `'path': 'sha256'` 表**，可能漏其他表達格式（Plan §5 同限制）；實作前須再跑全套鏈守衛。
- 未驗：A8 精確計數、V3／V4 精確計數、各 chip 在 Streamlit 下的實際換行、`compact.kpi_tile_html` 在「風險 tile 自訂內容」下是否需新增 helper（本示意以自訂 `cp-tile` 容器近似，真實作可能要新增元件函式）。
- 本批**沒有**跑全套 pytest（僅 §0 的 1348 項相關子集）。

## §9 落點

- 本檔；量測腳本與原始 JSON／截圖＝`docs/vnext/phase4_market/baseline/`；離線示意＝`docs/vnext/phase4_market/wireframe_preview/`（`gen_p4_preview.py`＋`shoot_p4.js`，⛔ 不被 app／test import）。
- 同步：`docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md` §19（Phase 4 步驟 0）；`docs/HANDOFF.md`（下一個唯一安全接手點）；`docs/PROJECT_STATE.md`；`docs/BACKLOG.md`（`P1R-PHASE4-MARKET`／`CV1-DR-12`／`P1R-P4-WF-POINTS`／`P1R-WF-FOLD-LABEL` 狀態＋本批新登 P2）。
- **拍板前禁止**：⛔ 任何 Phase 4 UI code（`src/ui/views/page_market.py`、`_market_blocks.py`、`_ui_kit.py`、`compact.py` 的頁面掛載、`app.py`、tests 的 Phase 4 改寫）；⛔ 以「本檔推薦」視為已核准；⛔ 提前處理 Phase 5～7、W4～W8；⛔ 動 `page_today.py`；⛔ 提高 Streamlit floor。
