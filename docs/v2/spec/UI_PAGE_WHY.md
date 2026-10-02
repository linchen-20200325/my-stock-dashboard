# UI_PAGE_WHY —— 「📖 憑什麼」頁完整版面（第 7 份）

**基準**：線框 `docs/v2/wireframe/wf_page_why.js`＝版面來源；元件一律引用第 2 份 `UI_COMPONENTS.md`、token 一律引用第 1 份 `UI_TOKENS.md`（⛔ 本檔不改這兩份、⛔ 不新造元件、⛔ 不動線框、⛔ 不動任何 token）。
實作對照 `src/ui/views/page_why.py::render_page_why()`（`:2189`，全檔 2217 行）。斷點沿用第 2 份 `≤640 / 641–880 / ≥881`；`n→t` 自動對映與 `grid(MAX_COLS=3)` 見第 2 份 §1 與第 3~6 份，⛔ 本檔不重述。
⚠️ 本檔為 UI 設計組 WP 單組產出，未經第二組複驗（§-2 規則 6）；**全檔免責只講這一次**。⛔ **客戶尚未看過本份** —— 全檔無「已核准／已拍板／已同意」字樣，除非該處另註出處。
🔴 **本頁是五頁唯一沒有主 CTA 的一頁**（線框 `mainCTA` 欄位存在、值為 JS `null`，WP node 實查）：⛔ **不得為它發明一顆按鈕**（客戶硬規則），按鈕位一律走第 2 份 §3「**停用態（無主 CTA 時）**」。

## ① 客戶四層 vs 線框 6 層 —— 三處對不上（⛔ 不得為了湊四層而改結構）

線框實測（WP node）：**6 層 22 block、3 葉**（`l1` 教學／`l2` 資料體檢／`l3` AI 問答）—— **五頁唯一的三葉頁**（`leaves[l3].note` 逐字，出處記為核准線框 DECISIONS #8 把它從頂層分頁降為本頁的葉）。

| 客戶說的層 | 線框層（block 數） | 對得上嗎 |
|---|---|---|
| （四層未涵蓋） | **n=0** 葉外｜全域 chrome（3）`why.statusbar`／`why.asof`／`why.footer`，`leaf:null` | 🔴 **差異 3** |
| 第一層 教學（四張說明卡） | **n=1** 葉1 教學 · 上半（4） | ✅ 一致 |
| 第三層 逐盞門檻對照表 | **n=2** 葉1 教學 · **下半**（**5**） | 🔴 **差異 2** |
| 第二層 資料體檢 | **n=3** 使用者版（6，**常駐**）＋ **n=4** 工程師版（3，**gate 後**） | 🔴 **差異 1** |
| 第四層 AI 問答 | **n=5** 葉3（1）`why.qa` | ✅ 一致 |

**🔴 差異 1｜「資料體檢」在線框是兩層，⛔ 不得合併寫。** n=3 的層標逐字「使用者版｜⭐ **常駐，不藏在 gate 後面**（全站指路句的終點）」、`leaves[l2].note` 逐字「**使用者版必須常駐，⛔ 不得藏在 gate 後面**；只有工程師版有 gate」；n=4 逐字「工程師版｜維持現行單一 gate」。**兩者可見性完全相反** —— 合併寫會讓「常駐」這個線框重點消失，而那正是另外四頁「去哪補」指路句的終點（⇒ 藏起來等於把四頁的指路句指到一個看不見的地方）。
**🔴 差異 2｜門檻對照表住在葉1 之內，而且是 5 塊不是 3 塊。** n=2 的層標逐字「**葉1 教學 · 下半**｜逐盞門檻對照表（切成三塊，各自有標題與各自的欄位）」⇒ ⛔ **不是獨立一葉**、⛔ 不得抽出葉1。⚠️ 層標自己寫「三塊」，但該層**實為 5 block**（WP node）：⑤-a 總經燈（16 盞）／⑤-b 參考走勢（2 條 · 不算燈）／⑤-c 持股燈（12 盞）／**⑤-d 被降級的門檻**／**⑤-e 依規格就不出等級的燈**。多出來的兩塊是「表格**下方**逐列」的說明區（⑤-d 的 `name` 逐字即「表格下方逐列」），不是第 4、5 張表 —— **「三塊」指的是三張表，「5 塊」指的是五個線框區塊，兩個數字各自都對**。⚠️ 客戶把它排在「資料體檢」之後（第三層），線框把它排在資料體檢**之前**（葉1 內）；**以線框為準**。
**🔴 差異 3｜客戶四層未涵蓋 n=0 葉外三塊。** 三塊 `cols` 皆 1/1/1、`leaf:null`（＝畫在分頁列之上、三葉共用）。其中 **`why.footer`（頁尾免責，`D-1`「每一頁都要有」）是本頁 chrome 三條裡唯一已經在畫面上的** —— 線框 `evidence` 逐字記載文字 SSOT 在 `app.py:514-517 _render_footer()`、新五頁分支於 `app.py:604` 在 `st.stop()` **之前**呼叫 ⇒ **本頁不重複第 2 份的 INSPECT 待修登記**（上一份是該頁 0 命中；本頁由 `app.py` 統一出）。`why.statusbar` 與 `why.asof` 則線框自標 `unwired`「**本頁目前沒有這一條**」。

## ② 六層結構（每層：用了第 2 份哪些元件／三斷點排列／首屏）

| 層 | n | block key（leaf・cols D/T/P） | 卡密度 | 主徽章 | 卡標字級 |
|---|---|---|---|---|---|
| 葉外 chrome | n0 | `why.statusbar`／`why.asof`／`why.footer`（**leaf `null`**，全 1/1/1） | `t3` `6px 9px` | `.sbadge b3` `11px`／`2px 10px`／min-h 28 | `13px/700` |
| **第一層** 四張說明卡 | n1 | `why.edu.lights`／`.health6`／`.scales`／`.legacy`（l1，**四塊全 3/2/1**） | `t1` `15px 17px`；border **2px** | `.sbadge b1` `14.5px`／`10px 22px`／min-h 46／border 2px | `17.5px/700` |
| **第二層** 逐盞門檻表 | n2 | `why.edu.table.macro`／`.reference`／`.hold`／`.caveat`／`.nolevel`（l1，**全 1/1/1**） | `t2` `10px 12px` | `.sbadge b2` `12.5px`／`5px 13px`／min-h 36 | `14.5px/700` |
| **第三層** 資料體檢 · 使用者版 | n3 | `why.source.wall`(3/2/1)／`.named`／`.cache_semantics`／`.unmeasured.finmind_quota`(3/2/1)／`why.spec.flags`(3/2/1)／`.coverage`（全 l2） | `t3` `6px 9px` | `.sbadge b3` | `13px/700` |
| **第四層** 資料體檢 · 工程師版 | n4 | `why.engineer.gate`／`.monitor`／`.panels`(3/2/1)（全 l2） | `t4` `5px 9px`；border 1px **dashed** | `.sbadge b4` `10.5px`／`2px 5px`／min-h 26／border 0 | `12.5px/700` `--ink-2` |
| 葉3 | n5 | `why.qa`（l3，1/1/1） | `t2`（**沿用 `UI_PAGE_FIND` 對 `n5` 的新訂**：超出 `n1~n4` 自動對映時取「核心卡」，⛔ 非本組發明） | `.sbadge b2` | `14.5px/700` |

**卡密度由 `layers[].n` 自動掛**（`UI_COMPONENTS.md:18` 逐字「⛔ 非逐塊手選」）；`n0→t3` 沿用第 3~5 份先例。
**按鈕（一律取第 2 份 §3，⛔ 不新造、⛔ 不發明主 CTA）**
- **本頁 0 顆主 CTA、0 顆「次級（說明）」** —— WP AST 全檔實測：`st.button`／`st.form`／`form_submit_button`／`st.download_button`／`st.link_button`／`st.radio`／`st.selectbox`／`st.text_input`／`st.text_area`／`st.number_input`／`st.slider`／`st.toggle`／`st.data_editor` **全部 0**。⇒ 按鈕位**直接對映 §3「停用態（無主 CTA 時）」**：`min-height:40px`／`6px 16px`／`13.5px/500`／`radius:3px`／`transparent` 底／**1px dashed `--rule-2`**／字 `--sig-grey`／無 hover。⚠️ **該列的「範例」欄逐字就是「本頁目前沒有主 CTA」**（`UI_COMPONENTS.md:81`，WP 實查命中）⇒ 本頁是那一列唯一的實例。
- ⚠️ **「§3 主 CTA 同款」那條先例（第 4~6 份）本頁無適用對象** —— 沒有任何 `type="primary"` 可對映。
- **次級（展開佐證）44×44**（`min-height/width:44px`／`7px 9px`／`12.5px/600`／框 `1px solid transparent`／hover 底 `--panel-2`）→ 線框全頁「展開佐證」**8 處**（WP `grep -o` 逐個計），其中**逐字作〔展開佐證 ▸〕的 7 處**、另 1 處為行文提及（`why.edu.lights`／`why.source.wall`／`why.spec.flags`／`why.engineer.gate`／`why.qa` 等）。
- **全頁使用者可互動元件只有兩個**（WP AST）：`st.checkbox`（`:2121`，工程師 gate，key `p05v_engineer_gate`）與 `st.chat_input`（`:2169`，key `p05v_qa_input` —— inline literal，非常數）。容器：`st.tabs`×1（`:2203`）、`st.expander`×1（`:2119`）、`st.dataframe`×**3 個呼叫點**（`:2050`／`:2062`／`:2141`）。
**排列（三斷點）**：欄數一律取線框 `cols`，硬夾 `MAX_COLS＝3`（`_ui_kit.py:99` 由 `tab_today.MAX_COLS` import，本檔不另立 3）。**裸 `st.columns` 全檔 0 處**（WP AST），唯一 `grid()` 呼叫點在 `_render_row()`（`:1958`），docstring 逐字「格子超過 3 個就換行排第二排，**不是加欄**」。⚠️ `3/2/1` 的 `tablet=2` 未落地（`641–880` 仍恆 3 欄）—— 此為 `UI_PAGE_FIND:29` 的 WJ 實測，WP 未重驗、照此打折，**沿用該份的「實作待修」登記**，⛔ 本頁不另開一筆。
⚠️ **斷點：本頁 0 塊需要改。** WP node 實測 22 block 的 `cols` **全為 `desktop/tablet/phone` 三鍵**、`1280` 在線框與實作**皆 0 命中** ⇒ **沒有第 6 份 HOLD 的四段制問題**，⛔ 不要沿用那邊的待修。
**表格（第 2 份 §4，三斷點全用）**：三張門檻表（⑤-a 總經 **7 欄**「這一盞／分組／方向／門檻／值從哪來／在防什麼／已知限制」＝ `_spec_table_rows()` `:1964`；⑤-c 持股燈**共用同一支**；⑤-b 參考走勢 **4 欄**「這一條／單位／這條線在說什麼／值從哪來」＝ `_reference_table_rows()` `:2003`）＋ 工程師 **8 欄**表（`:2141`：fetcher／分類／更新頻率／最後一次真實抓取／回了幾列／耗時(ms)／錯誤／本頁看不懂的狀態）。⇒ **執行時 4 張表、3 個呼叫點**（⑤-a 與 ⑤-c 共用 `:2050` 那一個呼叫點，`for _family` 迴圈跑兩次 —— WP 實查）。桌機／平板：表頭 `min-height:36px`／`12px/700 --ink-2`／底 `--panel-2`、列高 `38px`、`table{min-width:460px}`、**數值欄 `text-align:end` ＋ `--mono` ＋ tabular-nums ＋ nowrap**；`641–880` 容器不足時 `.tw` 橫向捲動（**頁面本體不得橫捲**）；**≤640 轉 §4 卡片流**（一列＝一張 `.blk.t3`、每卡至多 **4 對** key/value，其餘收進 44×44〔展開佐證〕；key 走 `--ink-3` 新值，六格 WCAG 已於 `UI_COMPONENTS` §4 實算全 PASS）。
**圖表容器：本頁 0 需求** —— 22 block 無任何圖表，`st.plotly_chart`／`st.line_chart` AST 皆 0。⛔ 不得預先把 §5 的容器畫成佔位。
**首屏可見範圍**：**三個斷點一律「需實機量測」**（比照第 3~6 份）。本頁 `var(--`／`<style>`／`@media`／`unsafe_allow_html` **各 0 命中**（WP 實測）⇒ 排版全由 Streamlit 自身 CSS 決定；另有 `st.tabs` 頭高與 `st.expander` 邊框高兩個 repo 反解不出的高度來源（由 Streamlit 版本決定，floor 見 `requirements.txt`）。⛔ **不猜、⛔ 不得寫推導值冒充量測。**
**唯一可宣稱的是順序（不含高度）**：`## 📖 憑什麼` → `st.caption` → 三葉 tab 頭（`:2203`）→〔葉1〕`section_header` → 四張說明卡 → 逐盞門檻表 → 降級說明 → 參考走勢表 → 不出等級的燈；〔葉2〕使用者版牆 → 三段常駐 caption → 工程師摺疊區；〔葉3〕狀態卡 → 對話區。⚠️ **三葉 body 同一輪都會跑完**（`:2206-2209` 註解逐字「本頁的三葉之間沒有任何 gate 依賴，所以顯示順序 = 執行順序」）。**預設葉＝第一葉「教學」**（`LEAF_EDU_TITLE`／`LEAF_DATA_HEALTH_TITLE`／`LEAF_QA_TITLE`，`:330-332`）。

## ③ 🔴 客戶三條特殊規則 —— 逐條查證（**兩條不完全成立**）

> ⛔ **每一條分三段寫：(a) 應然／(b) 現況實測／(c) 要做到需要什麼。⛔ 不得只讀 (a)。** 判準沿用客戶對本益比的裁示逐字 ——「**不要假裝做得到**」。

### 規則一｜「零取數，全葉只讀 L0 常數表」→ **部分成立**

- **(a) 應然**：線框 `leaves[l1].note` 逐字「**零取數：全葉只讀 L0 `@dataclass` 常數表**」（⚠️ 這句的主詞是**葉1**，不是全頁；客戶轉述與逐字略有出入，**以線框逐字為準**）。
- **(b) 現況實測（WP AST 全檔）**：**零 `src/data/**` import、零 `requests`／`yfinance`／FinMind、零 `@st.cache_data`** ✅；模組級 import 只有 L0（`shared/{ia_nav,fetch_monitor,macro_buckets,station_specs,ui_state}`）＋**兩支 L5**（`:283 src.ui.tabs.tab_today`、`:289 src.ui.views._ui_kit`）；另有**兩支 L3 late import**（`:1835 app_ai_service.get_gemini_api_key`、`:1843 ai_qa_service.run_agent`）**均在 `load_qa()` 內、且被 `:1832 if not req.asked: return` 擋在前面**。資料體檢牆讀的 `get_monitor_registry()`（`shared/fetch_monitor.py`）是**純 in-process dict**，不外抓。
- **(c) 據實寫成「未提問前零取數」** —— **葉1／葉2 確實零取數；葉3 送出問題後會走 L3 打外部 API**。⛔ 不得寫成「全頁零取數」。✅ 這與畫面承諾一致：`why.qa.idle` 逐字「**送出本身就是啟動**」、`build_qa_card` docstring 逐字「在問之前先亮紅燈，等於替一個**還沒發生的失敗**製造一次假警報」。

### 規則二｜「靜態內容，永遠可讀，這頁沒有灰態」→ ⛔ **實作不成立**

- **(a) 應然**：線框 `leaves[l1].note` 逐字「靜態內容，永遠可讀 —— **這頁沒有灰態**」；源頭 `S1-3B_FULL_DRAFT_SPEC.md §3.5.7` 矩陣「葉1 教學／③ 未載入」格逐字「⛔ **這頁沒有灰態**（靜態內容，永遠可讀）」（WP 實查命中）。線框把 `idle`／`loading` 兩格**填文字而非留 null**，`why.edu.lights.idle` 逐字「**這一葉沒有灰態** —— 它讀的是一份固定的門檻對照表，沒有『還沒載入』這回事。」
- **(b) 現況實測 —— ⛔ 這是執行結果，不是推論。** WP 實跑 `build_edu_cards(load_specs(), build_scale_disclosure())`（與總管同一支，兩組各自跑、結果一致）：
  `why.edu.lights` ＝ **`live`**／`why.edu.health6` ＝ **`unwired`**／`why.edu.scales` ＝ **`degraded`**／`why.edu.legacy` ＝ **`unwired`** ⇒ **四張教學卡有三張是灰的或橘的。**
  **原因**：「靜態」的落實方式**不是**把 state 寫死 `UI_LIVE`，而是傳 `requested=True`（`:758`）後**仍交給 `classify_ui_state()` 判**（全檔 4 個呼叫點：`:758`／`:934`／`:1645`／`:1870`），照樣會依 `wired`／`discriminative` 掉進 `unwired`／`degraded`。`wired=False` **AST kwarg 9 處**（`:578`／`:1005`／`:1467`／`:1581`／`:1681`／`:1693`／`:1706`／`:1719`／`:1731`；**字串出現 11 處**，多出的 2 處在註解／docstring —— 兩個數字都對，差在方法）。
  ⚠️ `_render_edu_leaf()`（`:2024`）docstring 與其 `section_header` 副標**逐字轉述線框那句**（「靜態 · 無 gate」「**這一葉不取任何數，所以它永遠可讀，也永遠不會因為『還沒載入』而空掉**」），而同一支函式產生的四張卡有三張不是 live —— **又一次註解與實作相反**（本 repo 既有前例：`page_inspect.py:50`、`page_hold.py DEEP_CAPTION`）。
- **(c) 要做到需要什麼**：讓那三張卡的 `wired`／`discriminative` 為真（＝**真的把內容接上**：六因子配分 SSOT、既有 📚 教學搬遷、兩套刻度中已失準的那一側），**或**改變「靜態卡也走 `classify_ui_state`」的做法。⛔ **不得用「把 state 寫死 live」來假裝** —— 那會把「這項還沒做」畫成「正常」，違 `CLAUDE.md §1`，也正是第 2 份 §2 對 #9 寫死的 fail-safe 方向（缺資訊往保守側退，⛔ 不得退回 #1）。

### 規則三｜「本頁目前沒有主 CTA」→ ✅ **完全成立**

線框 `mainCTA: null`（WP node：欄位 `hasOwnProperty` 為真、值 `=== null`）；`UI_COMPONENTS.md:81` §3「停用態（無主 CTA 時）」該列**範例欄逐字就是這句**（WP 實查）。實作：上列 13 種互動 widget **AST 全 0**。⛔ **本份不發明主 CTA。**
⚠️ **線框自己另有一項提案**：`why.statusbar.evidence` 記載客戶回饋「有些頁面寫『本頁目前沒有主 CTA』，新手會迷失」，線框的做法是**不新增按鈕**、改在 `subtitle` 加一句白話指路（「這一頁是用來查的，沒有『開始』按鈕 —— 想知道今天能不能出手，到『🚦 今天』…」），並自標 `★待拍板`（`flags` 含「★待拍板／偏離核准線框／單組結論」）⇒ **登記為未決，⛔ 本份不代決、⛔ 不得寫成已生效。**

## ④ 狀態覆蓋 —— 「這頁幾乎不會遇到灰態」的例外（⛔ 先讀這一段）

🔴 **例外不是少數：葉1 四張說明卡就中了三張**（③ 規則二 (b) 實跑）。「這頁沒有灰態」在**線框文字**上成立、在**實作**上不成立 ⇒ **畫版面時必須同時畫得出 `unwired`（#5）與 `degraded`（#4）**，⛔ 不得只畫 live 版。
其餘三個例外（皆線框自己就寫了灰態，**不是**違反規則二）：(i) **葉2 使用者版**牆上的 `idle`「⬜ 未檢查」是**本頁最常見的一態** —— WP 實跑：乾淨 process 下 `load_sources()` 回 `readable=True` 但 `probes=0`（「登錄表讀得到、裡面一支都沒有」）⇒ 走 `build_empty_registry_card()`，線框 `why.source.wall.empty` 逐字「**這是正常的，不是壞掉**」並要求 ⛔ 不得顯示成一片空白；(ii) **葉2 工程師版**未勾 checkbox 時整區 `idle`（`:2126` 未勾則 **一次 L0 登錄表都不讀**）；(iii) **葉3** 冷啟動 `idle`「⬜ 尚未提問」。
線框十態鍵 **22 塊全同序** `live|idle|loading|empty|missing|na|partial|degraded|unwired|error`；**220 格中 114 有值、106 為 null**（WP node 實測）。⚠️ **與 INV-9B 轉述的「112 有值／108 null」差 2 格** —— WP 以「值 `=== null` 為 null，其餘皆為非空字串（無 undefined、無空字串）」計；**兩組數字不一致，本項待第三方裁定，⛔ 不得引用任一數字當前提。** `null` ＝「這塊在該情況下結構上不存在」，⛔ 不得畫成空卡。

| 線框鍵 | 常數（`shared/ui_state.py`） | 徽章 | 本頁實作現況（WP AST／實跑） |
|---|---|---|---|
| `live` | `UI_LIVE` | **#1** 🟢 | ✅ Name **8 處**（＋import） |
| `idle` | `UI_IDLE` | **#3** ⬜ | ✅ Name **3 處**（＋import） |
| `loading` | `UI_LOADING` | **#2** ⏳ | ❌ Name **0**、`st.spinner` **0** ⇒ 未落地，⛔ 不得拿 #3 冒充載入中（線框三處要求「骨架」：`engineer.gate`／`.monitor`／`.panels`；`source.wall.loading` 逐字「固定高骨架」） |
| `degraded` | `UI_DEGRADED` | **#4** 🟠 | ⚠️ **常數名 0 處，但該態確實會出現** —— `why.edu.scales` 實跑即 `degraded`；線框實況另指名 **融資餘額**（總經燈）與 **財報趨勢**（持股燈）兩盞 |
| `unwired` | `UI_UNWIRED` | **#5** ⛔ | ⚠️ **常數名 0 處，該態會出現** —— 經 `classify_ui_state(..., wired=False)` 間接產生（AST 9 處）；線框實況指名 **外資現貨淨買賣** |
| `error` | `UI_FAILED` | **#6** 🔴 | ✅ Name **2 處**（＋import） |
| `empty`／`missing` | `UI_EMPTY` ＋ `MISS_*` | **#7** `⚠︎ —` | ⚠️ 常數名 0 處但該態會出現（QA 空回答分支）；`MISS_NO_INPUT` 5／`MISS_FETCH_FAILED` 2 |
| `na` | `UI_EMPTY` ＋ `MISS_NOT_APPLICABLE` | **#8** `N/A` | ❌ `MISS_NOT_APPLICABLE` **0 命中**；`N/A` 唯一命中在 `:837` docstring「`None` → 空字串（**不寫 0、不寫「N/A」**）」⇒ **#8 未落地**，⛔ 不得把 `missing` 畫成 #8（重跑無效，畫錯＝給錯指引） |
| `partial` | **七態無**（第 2 份新訂） | **#9** `◧` | ❌ `◧` 0、「已檢查」0 ⇒ 未落地。線框要求：`why.source.wall.partial` 逐字「`已檢查 N / M 源*`」＋「**不會只寫『部分資料』** —— 一定列出缺的是哪幾筆」；`why.asof.partial` 同。⚠️ 依第 2 份 fail-safe：**分子分母拿不到 → 一律降 #7，⛔ 不得退回 #1** |
| （線框無此鍵） | `emits_level=False` | **#10** `◆` | ⭐ **本頁是前六份中第一個有適用對象的**：`emits_level` 在本頁 **4 處**（`:1119` 欄位／`:1209` 判斷／`:1307` 讀 L0／`:1357 no_level`），WP 實跑 `specs.no_level` ＝ **1 項「KD 指標」**（L0 出處 `shared/station_specs.py:383 emits_level=False`）。⚠️ 但**現況以 `st.caption` 逐列呈現、`◆` 0 命中** ⇒ 徽章化為待補 |

⇒ **會出現在畫面上的是 6 態：#1／#3／#4／#5／#6／#7**；#2 未落地、#8／#9 待接線、**#10 有對象但尚未徽章化**。
⚠️ **⑤-e 的三句反面話必須照登**（`why.edu.table.nolevel.na` 逐字，實作 `:2068-2074`（`_render_edu_leaf` 段內）同義）：`unwired` 說它沒接（假的）、`degraded` 說它門檻失準（假的，它從來沒有門檻）、`empty` 說它沒資料（假的，K、D 都抓得到）—— **三句都不是實情** ⇒ ⛔ **不得把 #10 併進 #5／#4／#7 任何一種。**
⚠️ **`▨` 待同步（⛔ 本份不改線框）**：`▨` 在 `wf_page_why.js` **11 處**（WP `grep -o` 逐個計；10 在物件內、1 在檔頭註解），但依 `UI_COMPONENTS.md:150` 撤銷紀錄，`▨` 已自 #7／#8 撤掉、改 `⚠︎ —` 與 `N/A` ⇒ **凡屬 #7／#8 語意者一律改用第 2 份符號**。⚠️ 線框 `why.asof.na` 自己已逐字寫「這一格寫 `N/A` 而**不帶** ⚠︎：不適用 ≠ 壞掉」—— **方向一致，只是符號沒換**。`⚠︎` 必須是 `U+26A0 U+FE0E` 兩碼；⛔ **缺值不得顯示成 `0`**（`:837` 已寫死「不寫 0」）。

## ⑤ 反例自檢 —— AI 問答失敗時顯示什麼（六條分支，逐字）

`load_qa()`（`:1816-1859`）＋ `build_qa_card()`（`:1862-1907`）WP 實查，六條互斥分支：
- **(a) 未提問** → `asked=False` 早退 → `classify_ui_state(requested=False)` ＝ **#3 ⬜「尚未提問」**＋`QA_IDLE_WHERE`「**送出本身就是啟動**（不需要再按別的鈕）」。⭐ **冷啟動不預先讀金鑰**（`:1832` 先 return）⇒ **沒問過就不會紅**（線框 `idle` 逐字「第一次進來時是灰的，不是紅的 —— **即使根本沒有金鑰**」）。
- **(b) 讀金鑰拋例外** → `print` ＋ **#6 🔴** 帶 `repr(e)`（⛔ 不吞）。
- **(c) 無金鑰** → **#6 🔴「AI 問答未啟用」**＋ `NO_KEY_ERROR` 逐字「未偵測到 Gemini API 金鑰（部署端沒有設，或這個環境讀不到）」。
- **(d) `run_agent` 拋例外** → `print` ＋ **#6 🔴「這一輪問答失敗了」**＋ 錯誤原文 ＋「可以換個問法再送一次…**其他分頁的功能完全不受影響**」。
- **(e) 回來了但 `ok=False`／有 `error`** → **#6 🔴**，訊息空時用 `UNKNOWN_ERROR_TEXT`＝「**（上游沒有給訊息）**」（⛔ 不留白、⛔ 不編一句）。
- **(f) `ok=True` 但 text 空** → **#7 灰**「**這一輪沒有回答內容**」＋「上游沒有回報錯誤，但也沒有給任何文字 —— 這是一個**有效結果**（模型真的沒話說），**不是故障**」。⇒ **(f) 與 (d)(e) 的分色是本段最重要的一刀**：⛔ 不得把「模型沒話說」畫成紅色（違 `CLAUDE.md §1.A` 第 4 點「假警報」）。
**錯誤路徑體質（WP AST）**：`try` **6 處**、**`except: pass` 0**、**裸 `except:` 0**，錯誤一律 `print` ＋ 轉 `repr(e)` 上畫面 —— 與 `CLAUDE.md §1` 同向，⛔ 接線時不得改成靜默吞掉。**每張卡各自隔離**（`render_card_isolated`，`:1943`）⇒ 一張卡拋例外不會炸掉整頁；線框 `why.source.wall.error` 逐字「**一源紅不會把另外兩源一起染色**」＋第四種紅「**這一盞的狀態本頁看不懂** → ⚠️ **看不懂一律當紅，絕不當綠**」。
🔴 **線框在 (c) 自標「偏離規格 · ★待拍板」，兩邊並陳、⛔ 本份不代決**：`S1-3B_FULL_DRAFT_SPEC.md §3.5.6`（`:2249-2255`）逐字要求「去哪補：**本頁就地顯示設定入口與步驟**」＋ ⛔「**不得把使用者指去改 `.streamlit/secrets.toml`**」（WP 實查命中）；線框與實作則寫 `NO_KEY_WHERE`（`:1767`）——「金鑰目前由部署端提供（`st.secrets` 或環境變數的 `GEMINI_API_KEY`）；〈沒有你可以執行的出口〉在這一頁就地設定，**因為那等於在畫面上收憑證** —— 要開這個入口必須先由客戶拍板『這一頁可以收金鑰』，本批不做」。⇒ **兩者都沒有把使用者指去改 toml（規格的 ⛔ 沒有被違反）**，分歧只在「要不要就地給入口」，⇒ **登記為未決**。
⛔ **全頁禁止買賣建議**：本頁只解釋**門檻怎麼判、資料新不新鮮**；⑤-a~⑤-c 三張表的「門檻」欄是**判燈邊界**，⛔ 不得標成進出場點；AI 回答一律加 **🧬** 前綴（線框 `why.qa.live` 逐字，讓使用者一眼看出那是模型寫的、不是本站算出來的數字）。

---
⚠️ **複驗分級**

**總管實查**＝線框 **6 層 22 block** 與 **`mainCTA: null`**（node）；**四張教學卡實跑狀態**（`live`／`unwired`／`degraded`／`unwired`）；`page_why.py` 的 `st.button`／`form_submit_button` **0 處**。
**INV-9A 單組（實作面，未複驗，⛔ 不得當前提）**＝`page_why.py` 的全部 AST 盤點。⚠️ **WP 已自行重跑並確認一致**：13 種互動 widget 全 0；`st.checkbox` 1（`:2121`）／`st.chat_input` 1（`:2169`）／`st.tabs` 1／`st.expander` 1／`st.dataframe` 3／裸 `st.columns` 0／`grid` 1（`:1958`）／`classify_ui_state` 4（`:758`·`:934`·`:1645`·`:1870`）；`try` 6、`except: pass` 0、裸 `except:` 0；零 `src.data` 與 `requests` import、兩支 L5 module-level（`:283`／`:289`）、兩支 L3 late import（`:1835`／`:1843`，被 `:1834` 早退擋住）。**其餘未重跑者照單組打折。**
**INV-9B 單組（線框面，未複驗，⛔ 不得當前提）**＝`wf_page_why.js` 解析。⚠️ **WP node 重跑一致者**：3 葉、22 block 的 `leaf`／`cols`／`name`、十態鍵 22 塊同序、`mainCTA` 欄位存在且值為 `null`、`▨` 11 處。🔴 **WP 重跑不一致者一項**：**十態格 114 有值／106 null**（INV-9B 轉述為 112／108）—— 差 2 格，**兩個數字都不得當前提**，須第三組裁定。
**WP 本組實查（2026-09-16）**＝上兩段標「已重跑」者，另加：**實跑** `len(BUCKET_DANGER_SPECS)=16`／`len(REFERENCE_TREND_SPECS)=2`（新台幣匯率·加權指數）／`len(STATION_SPECS)=12`／`REFERENCE_BUCKET="reference"` **不在** `BUCKET_ORDER`（＝`long·mid·short·chips·news`）／`specs.rows` 28 列（macro 16＋hold 12）／`threshold_caveat_lines()` **3 行**／`no_level` **1 項（KD 指標）**／`load_sources()` 在乾淨 process 回 `readable=True`·`probes=0`；表格欄名逐字（7 欄／4 欄／工程師 8 欄）；`MONITORED_FETCHER_COUNT=9` ＝ `grep -rn "^@monitored" src/` **9**；`emits_level` 本頁 4 處＋`shared/station_specs.py:383`；`wired=False` AST kwarg **9**／字串 **11**；`var(--`·`<style>`·`@media`·`unsafe_allow_html`·`1280`·`◧`·`◆`·`⚠︎`·`▨`·「已檢查」·`MISS_NOT_APPLICABLE`·`UI_EMPTY`·`UI_DEGRADED`·`UI_UNWIRED`·`UI_LOADING` 在 `page_why.py` **各 0**；`N/A` **僅 `:837` docstring**；`S1-3B §3.5.6`（`:2249-2255`）與 §3.5.7 矩陣逐字；`UI_COMPONENTS.md:18`／`:81`／`:150` 三處逐字。
**WP 本組判定（⛔ 不是量測、⛔ 不是客戶裁示，全部須覆核）**＝(1) **① 三處差異的處置**（以線框 6 層為骨架、⛔ 不合併 n3／n4、⛔ 不抽出 n2）；(2) **① 差異 2 的「三塊 vs 5 塊」調和**（三張表 vs 五個線框區塊，兩數各自都對）；(3) **① 差異 3 對 `why.footer` 的判定**（本頁**不**沿用第 5 份 INSPECT 的頁尾待修登記，因本頁由 `app.py:604` 統一出）；(4) **③ 規則二 (c)** 的兩條達成路徑與「⛔ 不得寫死 live」；(5) **④ 對 #10 的判定**（本頁有適用對象、但徽章化待補，⛔ 不得併進 #5／#4／#7）；(6) **④ 對 #4／#5 的判定**（常數名 0 處但該態確實會出現，版面必須畫得出來）；(7) **⑤ 對 (c) 規格偏離的判定**（兩邊都沒違反 ⛔ 指去改 toml，分歧只在就地入口 ⇒ 未決）；(8) `n5→t2` 沿用 `UI_PAGE_FIND` 先例、`n0→t3` 沿用第 3~5 份先例。
**轉錄（非本組實測，引用時照此標明）**＝`641–880` 的 `tablet=2` 未落地與 Streamlit bundle 的 `columns:640px` 斷點（`UI_PAGE_FIND:29` WJ 實測，WP 未重驗）；`UI_COMPONENTS`／`UI_TOKENS` 的幾何值與 WCAG 實算（WC／WB／WD-1／WK 各組產出）。
**窮舉宣稱的方法（逐項標明）**＝凡「0 處／恰 N 處」涉及 `page_why.py` 的 **widget 呼叫、常數 Name 用法、kwarg、try/except、import** 者，一律 **Python `ast` 全檔掃描**；涉及**字面符號**（`▨`·`◧`·`◆`·`N/A`·「已檢查」）者為 **單次 `grep`**，⛔ 非 AST、⛔ 不得當窮舉；線框計數一律 **node 解析** `wf_page_why.js`；`16`／`2`／`12`／`3 行`／`1 項`／`probes=0` 一律 **import 後實跑**，⛔ 非讀 code 推論。
